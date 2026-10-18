from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.authorization import get_current_user_context
from app.schemas.form_draft import DraftSave, DraftVersion
from app.services import form_drafts as service

router = APIRouter(prefix='/api/form-drafts/archive-create',tags=['本人档案草稿'])

@router.get('/product-lines')
def draft_product_lines(db:Session=Depends(get_db),context:dict=Depends(get_current_user_context)):
    return service.product_line_options(db,context)

@router.get('')
def list_drafts(page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=500),db:Session=Depends(get_db),context:dict=Depends(get_current_user_context)):
    return service.list_drafts(db,context,page,page_size)

@router.post('')
def save_draft(data:DraftSave,request:Request,db:Session=Depends(get_db),context:dict=Depends(get_current_user_context)):
    return service.save_draft(db,context,data,request)

@router.get('/{draft_id}')
def get_draft(draft_id:UUID,db:Session=Depends(get_db),context:dict=Depends(get_current_user_context)):
    return service.get_draft(db,context,draft_id)

@router.delete('/{draft_id}')
def delete_draft(draft_id:UUID,data:DraftVersion,request:Request,db:Session=Depends(get_db),context:dict=Depends(get_current_user_context)):
    return service.delete_draft(db,context,draft_id,data.expected_version,request)

@router.post('/{draft_id}/submit')
def submit_draft(draft_id:UUID,data:DraftVersion,request:Request,db:Session=Depends(get_db),context:dict=Depends(get_current_user_context)):
    return service.submit_draft(db,context,draft_id,data.expected_version,request)
