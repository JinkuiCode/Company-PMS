"""Offline archive actions reuse normal scope, locks, queue and audit."""
from fastapi import HTTPException
from app.services.project import _claim_enabled_archive_for_write, validate_archive_for_business_operation
from app.services.erp_queue import enqueue
from app.services.operation_log import record_operation_log, serialize_model
from app.services.product_line_scope import require_line_access

def request_archive_sync(db, archive_id, user_id, scope_context, request=None):
    try:
        archive=_claim_enabled_archive_for_write(db,archive_id,scope_context,action_label="同步金蝶",reject_pending=True)
        before=serialize_model(archive)
        if archive.business_product_line_id is None:
            raise HTTPException(422,"请先分配产品线后再同步")
        line=require_line_access(db,scope_context,archive.business_product_line_id,selectable=True,lock=True)
        if line.source_key != "kingdee" or not line.organization_id or line.organization_id <= 0:
            raise HTTPException(422,"产品线尚未关联有效金蝶组织，不能同步")
        validate_archive_for_business_operation(db,archive)
        task=enqueue(db,archive,user_id,explicit=True)
        record_operation_log(db,module="项目档案",action="sync",entity_type="pms_project_archive",
            entity_id=archive.id,entity_name=archive.project_name,operator_id=user_id,request=request,
            summary="手动提交金蝶同步",before_data=before,after_data=serialize_model(archive))
        db.commit()
        return {"msg":"已提交同步，可在同步管理查看结果","task_id":task.id}
    except Exception:
        db.rollback()
        raise
