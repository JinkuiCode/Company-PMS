from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.project import ArchiveBusinessFields
class ImportValues(ArchiveBusinessFields):
    model_config=ConfigDict(extra="forbid",allow_inf_nan=False)
    project_code: str=Field(min_length=1,max_length=32)
    project_name: str|None=Field(None,max_length=128)
    customer: str|None=Field(None,max_length=128)
    equipment_series: int|None=None
    serial_no: str|None=Field(None,max_length=64)
class ImportRow(BaseModel):
    model_config=ConfigDict(extra="forbid")
    source_id: str=Field(min_length=1,max_length=64)
    source_sheet: str=Field(min_length=1,max_length=128)
    source_row: int=Field(ge=2)
    original_code: str|None=Field(None,max_length=32)
    values: ImportValues
class ImportPayload(BaseModel):
    model_config=ConfigDict(extra="forbid")
    rows: list[ImportRow]=Field(min_length=1,max_length=10000)
class ApprovedImportPayload(ImportPayload):
    file_hash: str = Field(min_length=64,max_length=64)
    approval_signature: str = Field(min_length=64,max_length=64)
class AssignmentItem(BaseModel):
    id: int=Field(gt=0)
    expected_updated_at: datetime
class ProductLineAssignment(BaseModel):
    items: list[AssignmentItem]=Field(min_length=1,max_length=10000)
    product_line_id: int=Field(gt=0)
