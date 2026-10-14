from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from app.schemas.project import ArchiveUpdate


class ArchiveChangePreview(BaseModel):
    updates: ArchiveUpdate
    expected_version: str = Field(..., min_length=64, max_length=64)


class ArchiveChangeSubmit(ArchiveChangePreview):
    submission_id: UUID
    reason: str = Field(..., min_length=1, max_length=1024)

    @field_validator('reason')
    @classmethod
    def trim_reason(cls, value):
        if not value.strip():
            raise ValueError('请填写变更原因')
        return value.strip()


class ArchiveChangeVersion(BaseModel):
    expected_version: int = Field(..., ge=1)


class ArchiveChangeDecision(ArchiveChangeVersion):
    decision: Literal['approve', 'reject']
    opinion: str = Field('', max_length=1024)
