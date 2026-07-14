from datetime import datetime

from pydantic import BaseModel, Field


class FieldPolicyUpdateItem(BaseModel):
    field_key: str = Field(..., min_length=1, max_length=128)
    visible: bool
    editable: bool
    required: bool
    list_available: bool
    expected_updated_at: datetime | None = None


class FieldPolicyBatchUpdate(BaseModel):
    items: list[FieldPolicyUpdateItem] = Field(default_factory=list, max_length=500)
