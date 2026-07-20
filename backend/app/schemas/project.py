from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Any


# ========== 项目档案 ==========
class ArchiveCreate(BaseModel):
    project_code: str = Field(..., max_length=32)
    project_name: str = Field(..., max_length=128)
    manager_id: int | None = None
    customer: str | None = Field(None, max_length=128)
    product_category: int | None = None
    equipment_series: int | None = None
    serial_no: str | None = Field(None, max_length=64)
    plan_start_date: datetime | None = None
    plan_end_date: datetime | None = None


class ArchiveUpdate(BaseModel):
    project_code: str | None = Field(None, max_length=32)
    project_name: str | None = Field(None, max_length=128)
    manager_id: int | None = None
    customer: str | None = Field(None, max_length=128)
    product_category: int | None = None
    equipment_series: int | None = None
    serial_no: str | None = Field(None, max_length=64)
    plan_start_date: datetime | None = None
    plan_end_date: datetime | None = None


class ArchiveDeleteBlocker(BaseModel):
    type: str
    source: str
    label: str
    count: int


class ArchiveBatchDelete(BaseModel):
    archive_ids: list[int] = Field(..., min_length=1)


class ArchiveEnabledUpdate(BaseModel):
    enabled: bool


class ArchiveBatchEnabledUpdate(ArchiveEnabledUpdate):
    archive_ids: list[int] = Field(..., min_length=1)


class ArchiveResponse(BaseModel):
    id: int
    project_code: str
    project_name: str
    status: int
    manager_id: int | None = None
    customer: str | None = None
    product_category: int | None = None
    equipment_series: int | None = None
    serial_no: str | None = None
    plan_start_date: datetime | None = None
    plan_end_date: datetime | None = None
    manager_name: str = ""    # 关联查询
    created_by_name: str = ""   # 创建人
    updated_by_name: str = ""   # 最后编辑人
    # ERP 同步字段
    erp_synced: int = 0
    erp_sync_time: datetime | None = None
    erp_sync_by_name: str = ""      # 最后同步人姓名
    erp_sync_status: str | None = None
    erp_error_msg: str | None = None
    is_enabled: int = 1
    can_delete: bool = True
    delete_blockers: list[ArchiveDeleteBlocker] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}


class ArchiveOption(BaseModel):
    """下拉选项（精简版）"""
    id: int
    project_code: str
    project_name: str
    model_config = {"from_attributes": True}


# ========== 项目 ==========
class ProjectCreate(BaseModel):
    archive_id: int
    project_code: str = Field(..., max_length=32)
    project_name: str = Field(..., max_length=128)
    dept_id: int
    pm_id: int
    product_category: int | None = None
    status: int = 1
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = None
    design_progress: int | None = Field(default=None, ge=0, le=100)
    order_progress: int | None = Field(default=None, ge=0, le=100)
    kit_progress: int | None = Field(default=None, ge=0, le=100)
    frame_progress: int | None = Field(default=None, ge=0, le=100)
    dryer_progress: int | None = Field(default=None, ge=0, le=100)
    assembly_progress: int | None = Field(default=None, ge=0, le=100)
    test_progress: int | None = Field(default=None, ge=0, le=100)
    description: str | None = None
    sheet_values: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    project_name: str | None = None
    product_category: int | None = None
    dept_id: int | None = None
    pm_id: int | None = None
    status: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = None
    design_progress: int | None = Field(default=None, ge=0, le=100)
    order_progress: int | None = Field(default=None, ge=0, le=100)
    kit_progress: int | None = Field(default=None, ge=0, le=100)
    frame_progress: int | None = Field(default=None, ge=0, le=100)
    dryer_progress: int | None = Field(default=None, ge=0, le=100)
    assembly_progress: int | None = Field(default=None, ge=0, le=100)
    test_progress: int | None = Field(default=None, ge=0, le=100)
    description: str | None = None


class ProjectResponse(BaseModel):
    id: int
    project_code: str
    project_name: str
    dept_id: int
    pm_id: int
    status: int
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = None
    description: str | None = None
    design_progress: int | None = None
    order_progress: int | None = None
    kit_progress: int | None = None
    frame_progress: int | None = None
    dryer_progress: int | None = None
    assembly_progress: int | None = None
    test_progress: int | None = None
    dept_name: str = ""    # 关联查询
    pm_name: str = ""      # 关联查询
    product_category: int | None = None  # 从档案关联
    task_count: int = 0    # 任务数
    total_progress: float = 0  # 总进度
    sheet_fields: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}


# ========== 项目总表详情 ==========
class ProjectSheetField(BaseModel):
    sort: int
    key: str
    label: str
    group: str
    value_type: str
    source_type: str
    editable: bool
    visible: bool = True
    required: bool = False
    computed: bool = False
    list_available: bool = False
    quick_addable: bool = False
    enum_code: str | None = None
    value: Any = None


class ProjectSheetGroup(BaseModel):
    key: str
    label: str
    fields: list[ProjectSheetField]


class ProjectSheetDetailResponse(BaseModel):
    project_id: int
    groups: list[ProjectSheetGroup]
    updated_at: datetime | None = None


class ProjectProgressDrawerUpdate(BaseModel):
    """项目进度抽屉可维护的项目主表字段。"""
    status: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    design_progress: int | None = Field(default=None, ge=0, le=100)
    order_progress: int | None = Field(default=None, ge=0, le=100)
    kit_progress: int | None = Field(default=None, ge=0, le=100)
    frame_progress: int | None = Field(default=None, ge=0, le=100)
    dryer_progress: int | None = Field(default=None, ge=0, le=100)
    assembly_progress: int | None = Field(default=None, ge=0, le=100)
    test_progress: int | None = Field(default=None, ge=0, le=100)

    model_config = {"extra": "forbid"}


class ProjectSheetDetailUpdate(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    project_values: ProjectProgressDrawerUpdate = Field(default_factory=ProjectProgressDrawerUpdate)


# ========== 任务 ==========
class TaskCreate(BaseModel):
    project_id: int
    task_name: str = Field(..., max_length=256)
    assignee_id: int | None = None
    progress: int = Field(default=0, ge=0, le=100)
    status: int = 1
    start_date: date | None = None
    due_date: date | None = None
    parent_id: int = 0
    sort: int = 0


class TaskUpdate(BaseModel):
    task_name: str | None = None
    assignee_id: int | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    status: int | None = None
    start_date: date | None = None
    due_date: date | None = None
    parent_id: int | None = None
    sort: int | None = None


class TaskResponse(BaseModel):
    id: int
    project_id: int
    task_name: str
    assignee_id: int | None = None
    progress: int
    status: int
    start_date: date | None = None
    due_date: date | None = None
    parent_id: int
    sort: int
    assignee_name: str = ""  # 关联
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}
