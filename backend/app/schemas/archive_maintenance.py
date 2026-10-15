from pydantic import BaseModel, Field, field_validator
from app.schemas.project import ArchiveUpdate


class ArchiveMaintenancePreview(BaseModel):
    model_config = {'extra': 'forbid'}
    updates: ArchiveUpdate
    expected_version: str = Field(min_length=64, max_length=64)


class ArchiveMaintenanceRequest(ArchiveMaintenancePreview):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator('reason')
    @classmethod
    def nonblank_reason(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('请填写维护原因')
        return value
