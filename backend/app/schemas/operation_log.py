from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OperationLogDiffItem(BaseModel):
    field_key: str
    field_label: str
    field_group: str | None = None
    before: Any = None
    after: Any = None
    before_display: str = "-"
    after_display: str = "-"


class OperationLogResponse(BaseModel):
    id: int
    module: str
    action: str
    entity_type: str
    entity_id: str | None = None
    entity_name: str | None = None
    operator_id: int | None = None
    operator_name: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_path: str | None = None
    request_method: str | None = None
    status: str
    summary: str
    error_msg: str | None = None
    before_data: str | None = None
    after_data: str | None = None
    diff_data: str | None = None
    diff_items: list[OperationLogDiffItem] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class OperationLogListResponse(BaseModel):
    total: int
    items: list[OperationLogResponse]
