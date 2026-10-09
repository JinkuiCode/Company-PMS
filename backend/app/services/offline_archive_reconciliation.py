"""Approved fill-only reconciliation; identifiers and ERP state are immutable here."""
from app.models.project import PmsProjectArchive
from app.models.erp_task import ErpSyncTask
from app.services.offline_archive_fields import OFFLINE_FIELDS
from app.services.operation_log import serialize_model

FILLABLE_FIELDS=set(OFFLINE_FIELDS)|{'project_name','customer','equipment_series','serial_no','address_detail','project_contact','contact_phone'}

def identity(value):
    return str(value or '').strip().casefold()

def is_blank(value):
    return value is None or isinstance(value,str) and not value.strip()

def fill_patch(archive,values):
    return {k:v for k,v in values.items() if k in FILLABLE_FIELDS and not is_blank(v) and is_blank(getattr(archive,k))}

def bind_existing_targets(db,payload):
    from app.schemas.offline_archive import ImportPayload
    from app.services.offline_archive_import import digest
    data=ImportPayload.model_validate(payload).model_dump(mode='json')
    existing={identity(a.project_code):a for a in db.query(PmsProjectArchive).populate_existing()}
    data['reconcile_existing']=True
    data['targets']={r['source_id']:{'archive_id':existing[identity(r['values']['project_code'])].id,
                    'snapshot_hash':digest(serialize_model(existing[identity(r['values']['project_code'])]))}
                    for r in data['rows'] if identity(r['values']['project_code']) in existing}
    return data

def build_import_plan(db,data):
    from app.services.offline_archive_import import digest
    archives=db.query(PmsProjectArchive).populate_existing().all()
    bycode={identity(a.project_code):a for a in archives}
    serials={identity(a.serial_no):a.id for a in archives if identity(a.serial_no)}
    busy={v for (v,) in db.query(ErpSyncTask.archive_id).filter(ErpSyncTask.status.in_(['queued','running','review']))}
    errors=[];plan=[];codes=set();source_ids=set()
    targets=data.get('targets',{})
    for row in data['rows']:
        values=row['values'];code=identity(values['project_code']);source=row['source_id']
        def error(message,field=None):errors.append({'source_id':source,'project_code':values['project_code'],'field':field,'message':message})
        if code in codes:error('项目编号在本批次中重复','project_code')
        codes.add(code)
        if source in source_ids:error('来源ID在本批次中重复')
        source_ids.add(source)
        obj=bycode.get(code);target=targets.get(source)
        if obj and not data.get('reconcile_existing'):error('项目编号与现有档案重复','project_code')
        if data.get('reconcile_existing'):
            if obj:
                if not target or target['archive_id']!=obj.id or target['snapshot_hash']!=digest(serialize_model(obj)):
                    error('线上档案已变化，请重新上传修订表预检')
                if not obj.is_enabled or obj.id in busy or obj.erp_sync_status in ['queued','pending','review']:
                    error('线上档案已禁用或正在同步，请处理后重新预检')
            elif target:error('预检对应的线上档案已删除或改号，请重新预检')
        updates=fill_patch(obj,values) if obj else {k:v for k,v in values.items() if k!='product_line_id'}
        serial=identity(updates.get('serial_no'))
        if serial:
            owner=serials.get(serial)
            if owner is not None and (obj is None or owner!=obj.id):error('序列号与本批或现有档案重复','serial_no')
            serials[serial]=obj.id if obj else source
        plan.append((row,obj,updates))
    if set(targets)-source_ids:errors.append({'message':'目标快照包含不属于本批次的来源ID'})
    if targets and not data.get('reconcile_existing'):errors.append({'message':'仅同号补充模式可以携带目标快照'})
    return plan,errors
