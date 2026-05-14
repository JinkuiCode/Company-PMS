from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import get_current_user_id, get_current_user_context
from app.schemas.project import ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate
from app.services import project as project_service

router = APIRouter(prefix="/api/projects", tags=["项目管理"])


@router.get("", summary="项目列表")
def list_projects(
    page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=10000),
    dept_id: int | None = Query(None), status: int | None = Query(None),
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(get_current_user_context),
):
    return project_service.get_project_list(db, page, page_size, dept_id, status, scope_context=scope_ctx)


@router.post("", summary="创建项目", dependencies=[Depends(get_current_user_id)])
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    return project_service.create_project(db, data)


@router.put("/{project_id}", summary="更新项目", dependencies=[Depends(get_current_user_id)])
def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    return project_service.update_project(db, project_id, data)


@router.delete("/{project_id}", summary="删除项目", dependencies=[Depends(get_current_user_id)])
def delete_project(project_id: int, db: Session = Depends(get_db)):
    return project_service.delete_project(db, project_id)


# ==================== 任务 ====================
@router.get("/{project_id}/tasks", summary="项目任务列表")
def list_tasks(
    project_id: int,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(get_current_user_context),
):
    return project_service.get_tasks(db, project_id, scope_context=scope_ctx)


@router.post("/{project_id}/tasks", summary="创建任务", dependencies=[Depends(get_current_user_id)])
def create_task(project_id: int, data: TaskCreate, db: Session = Depends(get_db)):
    data.project_id = project_id
    return project_service.create_task(db, data)


@router.put("/{project_id}/tasks/{task_id}", summary="更新任务（含进度自动记录）")
def update_task(
    project_id: int, task_id: int, data: TaskUpdate,
    user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db),
):
    return project_service.update_task(db, task_id, data, user_id)


@router.delete("/{project_id}/tasks/{task_id}", summary="删除任务", dependencies=[Depends(get_current_user_id)])
def delete_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    return project_service.delete_task(db, task_id)
