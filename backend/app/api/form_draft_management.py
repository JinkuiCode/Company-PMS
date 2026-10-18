from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.authorization import get_current_user_context
from app.schemas.form_draft import DraftVersion
from app.services import form_draft_management as service

router=APIRouter(prefix='/api/archive-draft-management',tags=['草稿管理'])

@router.get('')
def list_drafts(page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=500),
                project_code:str|None=Query(None,max_length=64),project_name:str|None=Query(None,max_length=128),
                owner_id:int|None=Query(None,gt=0),product_line_id:int|None=Query(None,gt=0),
                db:Session=Depends(get_db),context:dict=Depends(get_current_user_context)):
    return service.list_drafts(db,context,page=page,page_size=page_size,project_code=project_code,
        project_name=project_name,owner_id=owner_id,product_line_id=product_line_id)

@router.get('/{draft_id}')
def get_draft(draft_id:UUID,db:Session=Depends(get_db),context:dict=Depends(get_current_user_context)):
    return service.view(db,service.require_draft(db,context,draft_id),True)

@router.get('/{draft_id}/history')
def history(draft_id:UUID,page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=500),action:str|None=None,
            db:Session=Depends(get_db),context:dict=Depends(get_current_user_context)):
    from app.services.document_history import get_document_history
    return get_document_history(db,'draft_management',str(draft_id),context,page=page,page_size=page_size,action=action)

@router.delete('/{draft_id}')
def delete_draft(draft_id:UUID,data:DraftVersion,request:Request,
                 db:Session=Depends(get_db),context:dict=Depends(get_current_user_context)):
    return service.delete_draft(db,context,draft_id,data.expected_version,request)
