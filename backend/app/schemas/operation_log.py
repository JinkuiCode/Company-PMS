from datetime import datetime

from pydantic import BaseModel


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
    created_at: datetime

    model_config = {"from_attributes": True}


class OperationLogListResponse(BaseModel):
    total: int
    items: list[OperationLogResponse]
