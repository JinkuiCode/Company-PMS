from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.authorization import require_any_permission, require_permission
from app.schemas.project import ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate, ProjectSheetDetailUpdate
from app.schemas.project import (
    ArchiveBatchDelete,
    ArchiveBatchEnabledUpdate,
    ArchiveCreate,
    ArchiveEnabledUpdate,
    ArchiveUpdate,
)
from app.services import project as project_service

router = APIRouter(prefix="/api/projects", tags=["项目管理"])


@router.get("", summary="项目列表")
def list_projects(
    page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=10000),
    dept_id: int | None = Query(None), status: int | None = Query(None),
    sheet_field_keys: str | None = Query(None, description="逗号分隔的动态列表字段 key"),
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:list:view")),
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
    db: Session = Depends(get_db),
    _scope_ctx: dict = Depends(require_permission("project:list:view")),
):
    return project_service.get_project_sheet_field_metadata(db)


@router.get("/archives/fields", summary="项目档案生效字段元数据")
def get_archive_fields(
    db: Session = Depends(get_db),
    _scope_ctx: dict = Depends(require_permission("project:archive:view")),
):
    return project_service.get_archive_field_metadata(db)


@router.post("", summary="创建项目")
def create_project(
    data: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:list:add")),
):
    return project_service.create_project(
        db, data, operator_id=scope_ctx["user_id"], request=request, scope_context=scope_ctx
    )


@router.put("/{project_id}", summary="更新项目")
def update_project(
    project_id: int,
    data: ProjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:list:edit")),
):
    return project_service.update_project(
        db, project_id, data, scope_ctx["user_id"], request=request, scope_context=scope_ctx
    )


@router.delete("/{project_id}", summary="删除项目")
def delete_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:list:delete")),
):
    return project_service.delete_project(
        db, project_id, operator_id=scope_ctx["user_id"], request=request, scope_context=scope_ctx
    )


@router.get("/{project_id}/sheet-detail", summary="项目总表详情")
def get_project_sheet_detail(
    project_id: int,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:list:view")),
):
    return project_service.get_project_sheet_detail(db, project_id, scope_context=scope_ctx)


@router.put("/{project_id}/sheet-detail", summary="更新项目总表详情")
def update_project_sheet_detail(
    project_id: int,
    data: ProjectSheetDetailUpdate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:list:edit")),
):
    return project_service.update_project_sheet_detail(
        db,
        project_id,
        data,
        operator_id=scope_ctx["user_id"],
        request=request,
        scope_context=scope_ctx,
    )


# ==================== 项目档案 ====================
@router.get("/archives/list", summary="项目档案列表")
def list_archives(
    page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=10000),
    keyword: str | None = Query(None), status: int | None = Query(None),
    product_category: int | None = Query(None),
    enabled: bool | None = Query(True),
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:archive:view")),
):
    return project_service.get_archive_list(
        db, page, page_size, keyword, status, product_category, enabled=enabled, scope_context=scope_ctx
    )


@router.get("/archives/options", summary="项目档案下拉选项")
def archive_options(
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_any_permission("project:list:view", "project:list:add")),
):
    return project_service.get_archive_options(db, scope_context=scope_ctx)


@router.post("/archives", summary="创建项目档案")
def create_archive(
    data: ArchiveCreate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:archive:add")),
):
    return project_service.create_archive(
        db, data, scope_ctx["user_id"], request=request, scope_context=scope_ctx
    )


@router.post("/archives/batch-delete", summary="批量删除项目档案")
def batch_delete_archives(
    data: ArchiveBatchDelete,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:archive:delete")),
):
    return project_service.batch_delete_archives(
        db,
        data.archive_ids,
        operator_id=scope_ctx["user_id"],
        request=request,
        scope_context=scope_ctx,
    )


@router.put("/archives/batch-enabled", summary="批量启用或禁用项目档案")
def batch_set_archives_enabled(
    data: ArchiveBatchEnabledUpdate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:archive:toggle")),
):
    return project_service.batch_change_archives_enabled(
        db,
        data.archive_ids,
        data.enabled,
        operator_id=scope_ctx["user_id"],
        request=request,
        scope_context=scope_ctx,
    )


@router.put("/archives/{archive_id}/enabled", summary="启用或禁用项目档案")
def set_archive_enabled_route(
    archive_id: int,
    data: ArchiveEnabledUpdate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:archive:toggle")),
):
    return project_service.change_archive_enabled(
        db,
        archive_id,
        data.enabled,
        operator_id=scope_ctx["user_id"],
        request=request,
        scope_context=scope_ctx,
    )


@router.put("/archives/{archive_id}", summary="更新项目档案")
def update_archive(
    archive_id: int,
    data: ArchiveUpdate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:archive:edit")),
):
    return project_service.update_archive(
        db, archive_id, data, scope_ctx["user_id"], request=request, scope_context=scope_ctx
    )


@router.delete("/archives/{archive_id}", summary="删除项目档案")
def delete_archive(
    archive_id: int,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:archive:delete")),
):
    return project_service.delete_archive(
        db, archive_id, operator_id=scope_ctx["user_id"], request=request, scope_context=scope_ctx
    )


# ==================== 项目任务 ====================
@router.get("/{project_id}/tasks", summary="项目任务列表")
def list_tasks(
    project_id: int,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:list:view")),
):
    return project_service.get_tasks(db, project_id, scope_context=scope_ctx)


@router.post("/{project_id}/tasks", summary="创建任务")
def create_task(
    project_id: int,
    data: TaskCreate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:list:add")),
):
    data.project_id = project_id
    return project_service.create_task(
        db, data, operator_id=scope_ctx["user_id"], request=request, scope_context=scope_ctx
    )


@router.put("/{project_id}/tasks/{task_id}", summary="更新任务（含进度自动记录）")
def update_task(
    project_id: int, task_id: int, data: TaskUpdate,
    request: Request,
    scope_ctx: dict = Depends(require_permission("project:list:edit")), db: Session = Depends(get_db),
):
    return project_service.update_task(
        db, task_id, data, scope_ctx["user_id"], request=request,
        scope_context=scope_ctx, expected_project_id=project_id,
    )


@router.delete("/{project_id}/tasks/{task_id}", summary="删除任务")
def delete_task(
    project_id: int,
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:list:delete")),
):
    return project_service.delete_task(
        db, task_id, operator_id=scope_ctx["user_id"], request=request,
        scope_context=scope_ctx, expected_project_id=project_id,
    )
