from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.services.authorization import require_permission
from app.core.database import get_db
from app.schemas.operation_log import OperationLogListResponse
from app.services import operation_log as operation_log_service


router = APIRouter(prefix="/api/operation-logs", tags=["操作日志"])


@router.get("", response_model=OperationLogListResponse, summary="操作日志列表")
def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=10000),
    module: str | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    operator_id: int | None = Query(None),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    _scope_ctx: dict = Depends(require_permission("system:operation-log:view")),
    db: Session = Depends(get_db),
):
    return operation_log_service.get_operation_logs(
        db,
        page=page,
        page_size=page_size,
        module=module,
        action=action,
        entity_type=entity_type,
        operator_id=operator_id,
        status=status,
        keyword=keyword,
        start_time=start_time,
        end_time=end_time,
    )
