from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.authorization import require_permission
from app.services import business_notices as service

router = APIRouter(prefix='/api/business-notices', tags=['业务通知'])

@router.get('')
def list_notices(page:int=Query(1,ge=1), page_size:int=Query(50,ge=1,le=500), unread_only:bool=False,
                 db:Session=Depends(get_db), ctx:dict=Depends(require_permission(service.VIEW))):
    return service.list_notices(db,ctx,page=page,page_size=page_size,unread_only=unread_only)

@router.get('/{notice_id}')
def get_notice(notice_id:int,db:Session=Depends(get_db),ctx:dict=Depends(require_permission(service.VIEW))):
    return service.get_notice(db,ctx,notice_id)

@router.post('/{notice_id}/read')
def mark_read(notice_id:int,request:Request,db:Session=Depends(get_db),ctx:dict=Depends(require_permission(service.VIEW))):
    return service.mark_read(db,ctx,notice_id,request)

from pydantic import BaseModel, Field, StrictBool
from app.services import business_notice_mail as mail_service

class RetryInput(BaseModel):
    reason: str = Field(min_length=1,max_length=500)
    checked_not_received: StrictBool = False

@router.get('/requests/{change_id}/deliveries')
def deliveries(change_id:int,db:Session=Depends(get_db),ctx:dict=Depends(require_permission(service.MANAGE))):
    return mail_service.list_deliveries(db,ctx,change_id)

@router.post('/deliveries/{mail_id}/retry')
def retry_mail(mail_id:int,data:RetryInput,request:Request,db:Session=Depends(get_db),ctx:dict=Depends(require_permission(service.RETRY))):
    return mail_service.retry(db,ctx,mail_id,reason=data.reason,checked_not_received=data.checked_not_received,request=request)
