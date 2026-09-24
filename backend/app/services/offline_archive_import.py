"""Transactional, manual-only imports. No external system calls."""
import hashlib,json
from datetime import datetime
from decimal import Decimal
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from app.models.project import PmsProjectArchive,PmsProject,ErpSyncLog
from app.models.erp_task import ErpSyncTask
from app.models.archive_import import ArchiveImportBatch,ArchiveImportRow
from app.schemas.offline_archive import ImportPayload,ProductLineAssignment
from app.services.business_data_scope import has_all_business_data
from app.services.operation_log import record_operation_log,serialize_model
from app.services.offline_archive_fields import OFFLINE_FIELDS
from app.services.enum_registry import validate_enum_value
from app.services.project import get_scoped_archive_query
from app.services.project_archive_lifecycle import claim_archive_lifecycle_rows,archive_not_pending_condition
from app.services.product_line_scope import require_line_access
from app.services.field_policy import validate_business_field_write,MODULE_PROJECT_ARCHIVE

def require_import_scope(scope):
    if not has_all_business_data(scope):
        raise HTTPException(403,"期初资料整理需要明确的全部业务数据权限")

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

def _parse(payload):
    return ImportPayload.model_validate(payload).model_dump(mode="json")

def preview_import(db,payload,scope):
    require_import_scope(scope)
    try:data=_parse(payload)
    except ValidationError as exc:
        return {"total":len(payload.get("rows",[])),"errors":[{"row":list(e["loc"]),"message":e["msg"]} for e in exc.errors()],"content_hash":None,"already_imported":False}
    fingerprint=digest(data)
    existing=db.query(ArchiveImportBatch).filter_by(content_hash=fingerprint).first()
    if existing:
        return {"total":len(data["rows"]),"errors":[] if existing.status=="applied" else [{"message":"此批次已回退，不允许重复执行"}],"content_hash":fingerprint,"already_imported":existing.status=="applied","batch_id":existing.id}
    # Read one identity snapshot instead of one query per row.
    codes={str(c).casefold() for (c,) in db.query(PmsProjectArchive.project_code)}
    serials={str(c).strip().casefold() for (c,) in db.query(PmsProjectArchive.serial_no).filter(PmsProjectArchive.serial_no.isnot(None))}
    ids={v for (v,) in db.query(ArchiveImportRow.source_id)};errors=[]
    for row in data["rows"]:
        values=row["values"];code=values["project_code"].strip()
        def error(message,field=None):
            errors.append({"source_id":row["source_id"],"project_code":code,"field":field,"message":message})
        if not code:error("项目编号不能为空","project_code")
        if code.casefold() in codes:error("项目编号与本批或现有档案重复","project_code")
        codes.add(code.casefold())
        if row["source_id"] in ids:error("来源ID重复")
        ids.add(row["source_id"])
        serial=(values.get("serial_no") or "").strip().casefold()
        if serial:
            if serial in serials:error("序列号与本批或现有档案重复","serial_no")
            serials.add(serial)
        if values.get("product_line_id") is not None:error("期初产品线必须留空","product_line_id")
        quantity=values.get("quantity")
        if quantity is not None:
            q=Decimal(str(quantity))
            if abs(q)>=Decimal("1e12") or q.as_tuple().exponent < -8:error("数量超出12位整数或8位小数精度","quantity")
        for key,meta in {**OFFLINE_FIELDS,"equipment_series":{"enum_code":"equipment_series"}}.items():
            if meta["enum_code"] and values.get(key) is not None:
                try:validate_enum_value(db,meta["enum_code"],values[key])
                except HTTPException:error("枚举选项不存在或已停用",key)
        # Historical import may leave missing legacy values but cannot write read-only fields.
        try:
            validate_business_field_write(db,MODULE_PROJECT_ARCHIVE,current_values={},updates={k:v for k,v in values.items() if v is not None},
                entity_created_at=None,is_create=False,historical_import=True)
        except HTTPException as exc:error(str(exc.detail))
    return {"total":len(data["rows"]),"errors":errors,"content_hash":fingerprint,"already_imported":False}

def _log(db,action,obj,user_id,request,before=None):
    record_operation_log(db,module="项目档案",action=action,entity_type="pms_project_archive",entity_id=obj.id,
        entity_name=obj.project_name or obj.project_code,operator_id=user_id,request=request,
        summary={"import":"期初档案导入","update":"批量分配产品线","delete":"回退期初档案"}[action],
        before_data=before,after_data=None if action=="delete" else serialize_model(obj))

def apply_import(db,payload,user_id,scope,request=None,*,source_file_hash=None):
    try:
        result=preview_import(db,payload,scope)
        if result["errors"]:raise HTTPException(422,{"message":"预检未通过，未导入任何记录","errors":result["errors"]})
        if result["already_imported"]:return {"batch_id":result["batch_id"],"created":0,"msg":"该批次已导入"}
        rows=ImportPayload.model_validate(payload).rows
        batch=ArchiveImportBatch(content_hash=result["content_hash"],source_file_hash=source_file_hash,row_count=len(rows),created_by=user_id,status="applied")
        db.add(batch);db.flush()
        for row in rows:
            values=row.values.model_dump(exclude={"product_line_id"})
            values["project_code"]=values["project_code"].strip()
            values["project_name"]=(values["project_name"] or "").strip() or None
            obj=PmsProjectArchive(**values,data_origin="offline_initial",erp_sync_policy="manual",erp_sync_status=None,
                created_by=user_id,updated_by=user_id,business_product_line_id=None)
            db.add(obj);db.flush();db.refresh(obj)
            db.add(ArchiveImportRow(batch_id=batch.id,source_id=row.source_id,source_sheet=row.source_sheet,source_row=row.source_row,
                archive_id=obj.id,original_code=row.original_code or obj.project_code,snapshot_hash=digest(serialize_model(obj))))
            _log(db,"import",obj,user_id,request)
        record_operation_log(db,module="项目档案",action="import",entity_type="pms_archive_import_batch",entity_id=batch.id,
            entity_name="期初导入批次",operator_id=user_id,request=request,summary="期初档案整批导入完成",
            after_data={"row_count":len(rows),"status":"applied","source_file_hash":source_file_hash})
        db.commit()
        return {"batch_id":batch.id,"created":len(rows),"msg":"已归档，未发送金蝶"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"导入内容与并发写入记录冲突，整批已回滚，请重新预检")
    except Exception:
        db.rollback();raise

def rollback_import(db,batch_id,user_id,scope,request=None):
    require_import_scope(scope)
    try:
        batch=db.query(ArchiveImportBatch).filter_by(id=batch_id).with_for_update().first()
        if not batch or batch.status!="applied":raise HTTPException(409,"批次不存在或已回退")
        records=db.query(ArchiveImportRow).filter_by(batch_id=batch.id).all()
        objects=claim_archive_lifecycle_rows(get_scoped_archive_query(db,scope),[r.archive_id for r in records],archive_not_pending_condition())
        byid={a.id:a for a in objects}
        blocked=[]
        for row in records:
            a=byid.get(row.archive_id)
            if not a or digest(serialize_model(a))!=row.snapshot_hash:
                blocked.append(row.source_id);continue
            referenced=(db.query(PmsProject.id).filter_by(archive_id=a.id).first() or
                db.query(ErpSyncTask.id).filter_by(archive_id=a.id).first() or
                db.query(ErpSyncLog.id).filter_by(source_id=a.id).first())
            if a.erp_synced or referenced:blocked.append(row.source_id)
        if blocked:raise HTTPException(409,{"message":"部分档案已修改、被引用或同步，整批未回退","source_ids":blocked})
        for a in objects:
            _log(db,"delete",a,user_id,request,before=serialize_model(a));db.delete(a)
        batch.status="rolled_back"
        record_operation_log(db,module="项目档案",action="delete",entity_type="pms_archive_import_batch",entity_id=batch.id,
            entity_name="期初导入批次",operator_id=user_id,request=request,summary="期初档案整批回退完成",
            before_data={"status":"applied"},after_data={"status":"rolled_back","row_count":len(objects)})
        db.commit()
        return {"deleted":len(objects),"batch_id":batch.id}
    except Exception:db.rollback();raise

def assign_product_line(db,payload,user_id,scope,request=None):
    require_import_scope(scope)
    data=ProductLineAssignment.model_validate(payload)
    if len({v.id for v in data.items})!=len(data.items):raise HTTPException(422,"选择的档案重复")
    try:
        objects=claim_archive_lifecycle_rows(get_scoped_archive_query(db,scope),[v.id for v in data.items],archive_not_pending_condition())
        byid={a.id:a for a in objects}
        if len(objects)!=len(data.items):raise HTTPException(409,"部分档案不可访问或正在同步，请刷新")
        require_line_access(db,scope,data.product_line_id,selectable=True,lock=True)
        for item in data.items:
            a=byid[item.id]
            if a.updated_at!=item.expected_updated_at.replace(tzinfo=None):raise HTTPException(409,"档案已被修改，请刷新后重新选择")
            if not a.is_enabled:raise HTTPException(409,"禁用档案不能分配产品线")
            if a.erp_synced or a.data_origin=="kingdee_initial":raise HTTPException(409,"已同步或金蝶期初档案不可批量更换产品线")
            before=serialize_model(a)
            validate_business_field_write(db,MODULE_PROJECT_ARCHIVE,current_values={**serialize_model(a), "product_line_id":a.business_product_line_id},
                updates={"product_line_id":data.product_line_id},entity_created_at=a.created_at,is_create=False,
                historical_import=a.data_origin=="offline_initial")
            a.business_product_line_id=data.product_line_id;a.updated_by=user_id;a.updated_at=datetime.now()
            _log(db,"update",a,user_id,request,before=before)
        db.commit();return {"updated":len(objects),"msg":"产品线已分配，未触发金蝶同步"}
    except Exception:db.rollback();raise


def get_import_source(db,archive_id,scope):
    if not get_scoped_archive_query(db,scope).filter(PmsProjectArchive.id==archive_id).first():
        raise HTTPException(404,"档案不存在或无权访问")
    row=db.query(ArchiveImportRow).filter_by(archive_id=archive_id).first()
    if row is None:return None
    batch=db.get(ArchiveImportBatch,row.batch_id)
    return {"batch_id":row.batch_id,"source_id":row.source_id,"source_sheet":row.source_sheet,
            "source_row":row.source_row,"original_code":row.original_code,
            "imported_at":batch.created_at,"source_file_hash":batch.source_file_hash}
