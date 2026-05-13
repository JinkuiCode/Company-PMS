from pydantic import BaseModel, Field
from datetime import date, datetime


# ========== 项目 ==========
class ProjectCreate(BaseModel):
    project_code: str = Field(..., max_length=32)
    project_name: str = Field(..., max_length=128)
    dept_id: int
    pm_id: int
    status: int = 1
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = None
    description: str | None = None


class ProjectUpdate(BaseModel):
    project_name: str | None = None
    dept_id: int | None = None
    pm_id: int | None = None
    status: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = None
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
    dept_name: str = ""    # 关联查询
    pm_name: str = ""      # 关联查询
    task_count: int = 0    # 任务数
    total_progress: float = 0  # 总进度
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}


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
