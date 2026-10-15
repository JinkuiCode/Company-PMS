from datetime import datetime
from pydantic import BaseModel
from app.schemas.operation_log import OperationLogDiffItem


class DocumentEvent(BaseModel):
    id: int
    actor: str
    created_at: datetime
    action: str
    action_label: str
    status: str
    status_label: str
    source: str
    summary: str
    diff_items: list[OperationLogDiffItem]


class DocumentHistoryResponse(BaseModel):
    total: int
    items: list[DocumentEvent]
    actions: list[dict[str, str]]
