from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.archive_change import ArchiveChangePreview, ArchiveChangeSubmit, ArchiveChangeDecision, ArchiveChangeVersion
from app.services.authorization import require_permission
from app.services import archive_change as service

router=APIRouter(prefix='/api/projects/archive-changes',tags=['档案变更审批'])

from app.api.business_exports import BusinessExportRequest, BusinessExportFileResponse

@router.post('/export')
def export_changes(data:BusinessExportRequest,request:Request,db:Session=Depends(get_db),ctx:dict=Depends(require_permission('project:archive:export'))):
    from app.services.archive_change_export import create_archive_change_export
    path,filename=create_archive_change_export(db,data,ctx,request)
    return BusinessExportFileResponse(path,filename=filename,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@router.get('')
def list_changes(page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=500),status:int|None=Query(None,ge=1,le=5),
                 filters:str|None=None,sort:str|None=None,
                 db:Session=Depends(get_db),ctx:dict=Depends(require_permission('project:archive:view'))):
    return service.list_archive_changes(db,ctx,page=page,page_size=page_size,status=status,filters=filters,sort=sort)

@router.post('/requests/{change_id}/decide')
def decide(change_id:int,data:ArchiveChangeDecision,request:Request,db:Session=Depends(get_db),ctx:dict=Depends(require_permission('project:archive:edit'))):
    return service.decide_archive_change(db,change_id,data,ctx['user_id'],request=request,scope_context=ctx)

@router.post('/requests/{change_id}/withdraw')
def withdraw(change_id:int,data:ArchiveChangeVersion,request:Request,db:Session=Depends(get_db),ctx:dict=Depends(require_permission('project:archive:edit'))):
    return service.withdraw_archive_change(db,change_id,data,ctx['user_id'],request=request,scope_context=ctx)

@router.post('/{archive_id}/preview')
def preview(archive_id:int,data:ArchiveChangePreview,db:Session=Depends(get_db),ctx:dict=Depends(require_permission('project:archive:edit'))):
    return service.preview_archive_change(db,archive_id,data,ctx['user_id'],scope_context=ctx)

@router.post('/{archive_id}/submit')
def submit(archive_id:int,data:ArchiveChangeSubmit,request:Request,db:Session=Depends(get_db),ctx:dict=Depends(require_permission('project:archive:edit'))):
    return service.submit_archive_change(db,archive_id,data,ctx['user_id'],request=request,scope_context=ctx)
