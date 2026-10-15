from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.authorization import get_current_user_context
from app.services.document_history import get_document_history
from app.schemas.document_history import DocumentHistoryResponse

router = APIRouter(prefix='/api/document-history', tags=['单据操作记录'])


@router.get('/{resource}/{entity_id}', response_model=DocumentHistoryResponse)
def history(resource: Literal['archive', 'project', 'task', 'feedback'], entity_id: int,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    action: str | None = Query(None, max_length=32), db: Session = Depends(get_db),
    scope: dict = Depends(get_current_user_context)):
    return get_document_history(db, resource, entity_id, scope, page=page, page_size=page_size, action=action)
