from pydantic import BaseModel, Field
from datetime import datetime


# ========== 字典分类 ==========
class DictCreate(BaseModel):
    dict_code: str = Field(..., max_length=64)
    dict_name: str = Field(..., max_length=64)
    table_name: str | None = None
    field_name: str | None = None
    page_name: str | None = None
    description: str | None = None
    sort: int = 0
    status: int = 1


class DictUpdate(BaseModel):
    dict_code: str | None = None
    dict_name: str | None = None
    table_name: str | None = None
    field_name: str | None = None
    page_name: str | None = None
    description: str | None = None
    sort: int | None = None
    status: int | None = None


class DictResponse(BaseModel):
    id: int
    dict_code: str
    dict_name: str
    table_name: str | None
    field_name: str | None
    page_name: str | None
    description: str | None
    sort: int
    status: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ========== 字典项 ==========
class DictItemCreate(BaseModel):
    item_value: str = Field(..., max_length=64)
    item_label: str = Field(..., max_length=64)
    field_type: str | None = None
    description: str | None = None
    sort: int = 0
    status: int = 1


class DictItemUpdate(BaseModel):
    item_value: str | None = None
    item_label: str | None = None
    field_type: str | None = None
    description: str | None = None
    sort: int | None = None
    status: int | None = None


class DictItemResponse(BaseModel):
    id: int
    dict_id: int
    item_value: str
    item_label: str
    field_type: str | None
    description: str | None
    sort: int
    status: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
