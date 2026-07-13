from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.authorization import require_any_permission, require_permission
from app.schemas.user import UserCreate, UserUpdate
from app.services import rbac as rbac_service

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("", summary="用户列表", dependencies=[Depends(require_permission("system:user:view"))])
def list_users(page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=10000),
               dept_id: int | None = Query(None, description="按部门过滤"),
               db: Session = Depends(get_db)):
    return rbac_service.get_user_list(db, page, page_size, dept_id=dept_id)


@router.post("", summary="创建用户")
def create_user(
    data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:user:add")),
):
    return rbac_service.create_user(db, data, operator_id=scope_ctx["user_id"], request=request)


@router.get("/options", summary="用户下拉选项")
def user_options(
    db: Session = Depends(get_db),
    _scope_ctx: dict = Depends(require_any_permission(
        "project:list:view", "project:list:add", "project:list:edit",
        "project:archive:view", "project:archive:add", "project:archive:edit",
        "system:user:view",
    )),
):
    return rbac_service.get_user_options(db)


@router.put("/{user_id}", summary="更新用户")
def update_user(
    user_id: int,
    data: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:user:edit")),
):
    return rbac_service.update_user(db, user_id, data, operator_id=scope_ctx["user_id"], request=request)


@router.delete("/{user_id}", summary="删除用户")
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:user:delete")),
):
    return rbac_service.delete_user(db, user_id, operator_id=scope_ctx["user_id"], request=request)
