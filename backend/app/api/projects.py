from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import get_current_user_id, get_current_user_context
from app.schemas.project import ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate, ProjectSheetDetailUpdate
from app.schemas.project import ArchiveCreate, ArchiveUpdate
from app.services import project as project_service

router = APIRouter(prefix="/api/projects", tags=["项目管理"])


@router.get("", summary="项目列表")
def list_projects(
    page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=10000),
    dept_id: int | None = Query(None), status: int | None = Query(None),
    sheet_field_keys: str | None = Query(None, description="逗号分隔的动态列表字段 key"),
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(get_current_user_context),
):
    return project_service.get_project_list(
        db,
        page,
        page_size,
        dept_id,
        status,
        sheet_field_keys=sheet_field_keys,
        scope_context=scope_ctx,
    )


@router.get("/sheet-fields", summary="项目进度动态列表字段元数据")
def get_project_sheet_fields(
    _scope_ctx: dict = Depends(get_current_user_context),
):
    return project_service.get_project_sheet_field_metadata()


@router.post("", summary="创建项目")
def create_project(
    data: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return project_service.create_project(db, data, operator_id=user_id, request=request)


@router.put("/{project_id}", summary="更新项目")
def update_project(
    project_id: int,
    data: ProjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return project_service.update_project(db, project_id, data, user_id, request=request)


@router.delete("/{project_id}", summary="删除项目")
def delete_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return project_service.delete_project(db, project_id, operator_id=user_id, request=request)


@router.get("/{project_id}/sheet-detail", summary="项目总表详情")
def get_project_sheet_detail(
    project_id: int,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(get_current_user_context),
):
    return project_service.get_project_sheet_detail(db, project_id, scope_context=scope_ctx)


@router.put("/{project_id}/sheet-detail", summary="更新项目总表详情")
def update_project_sheet_detail(
    project_id: int,
    data: ProjectSheetDetailUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    scope_ctx: dict = Depends(get_current_user_context),
):
    return project_service.update_project_sheet_detail(
        db,
        project_id,
        data,
        operator_id=user_id,
        request=request,
        scope_context=scope_ctx,
    )


# ==================== 项目档案 ====================
@router.get("/archives/list", summary="项目档案列表")
def list_archives(
    page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=10000),
    keyword: str | None = Query(None), status: int | None = Query(None),
    product_line: str | None = Query(None),
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(get_current_user_context),
):
    allowed_lines = scope_ctx.get("product_lines")
    return project_service.get_archive_list(db, page, page_size, keyword, status, product_line, allowed_lines)


@router.get("/archives/options", summary="项目档案下拉选项")
def archive_options(db: Session = Depends(get_db), _user_id: int = Depends(get_current_user_id)):
    return project_service.get_archive_options(db)


@router.post("/archives", summary="创建项目档案")
def create_archive(
    data: ArchiveCreate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return project_service.create_archive(db, data, user_id, request=request)


@router.put("/archives/{archive_id}", summary="更新项目档案")
def update_archive(
    archive_id: int,
    data: ArchiveUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return project_service.update_archive(db, archive_id, data, user_id, request=request)


@router.delete("/archives/{archive_id}", summary="删除项目档案")
def delete_archive(
    archive_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return project_service.delete_archive(db, archive_id, operator_id=user_id, request=request)


# ==================== 项目任务 ====================
@router.get("/{project_id}/tasks", summary="项目任务列表")
def list_tasks(
    project_id: int,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(get_current_user_context),
):
    return project_service.get_tasks(db, project_id, scope_context=scope_ctx)


@router.post("/{project_id}/tasks", summary="创建任务")
def create_task(
    project_id: int,
    data: TaskCreate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    data.project_id = project_id
    return project_service.create_task(db, data, operator_id=user_id, request=request)


@router.put("/{project_id}/tasks/{task_id}", summary="更新任务（含进度自动记录）")
def update_task(
    project_id: int, task_id: int, data: TaskUpdate,
    request: Request,
    user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db),
):
    return project_service.update_task(db, task_id, data, user_id, request=request)


@router.delete("/{project_id}/tasks/{task_id}", summary="删除任务")
def delete_task(
    project_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return project_service.delete_task(db, task_id, operator_id=user_id, request=request)
