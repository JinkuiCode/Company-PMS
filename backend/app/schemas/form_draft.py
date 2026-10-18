from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class DraftVersion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1, strict=True)

class DraftSave(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    expected_version: int | None = Field(None, ge=1, strict=True)
    payload: dict[str, Any] = Field(default_factory=dict, max_length=60)
