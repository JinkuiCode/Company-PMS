from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrganizationOption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_key: Literal['kingdee'] = 'kingdee'
    organization_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    active: bool


class ProductLineCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    organization_id: int = Field(gt=0)
    display_name: str | None = Field(default=None, max_length=128)
    sort: int = Field(default=0, ge=0, le=1000000)


class ProductLineUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    expected_updated_at: datetime
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    sort: int | None = Field(default=None, ge=0, le=1000000)
    is_enabled: bool | None = None

    @field_validator('display_name', 'sort', 'is_enabled')
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError('不能设为空值')
        return value
