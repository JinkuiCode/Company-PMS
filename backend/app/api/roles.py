from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.authorization import require_any_permission, require_permission
from app.schemas.rbac import RoleCreate, RoleUpdate
from app.services import rbac as rbac_service

router = APIRouter(prefix="/api/roles", tags=["角色管理"])


@router.get("", summary="角色列表", dependencies=[Depends(require_permission("system:role:view"))])
def list_roles(db: Session = Depends(get_db)):
    return rbac_service.get_role_list(db)


@router.post("", summary="创建角色")
def create_role(
    data: RoleCreate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:role:add")),
):
    return rbac_service.create_role(db, data, operator_id=scope_ctx["user_id"], request=request)


@router.get("/options", summary="角色下拉选项")
def role_options(
    db: Session = Depends(get_db),
    _scope_ctx: dict = Depends(require_any_permission(
        "system:user:view", "system:user:add", "system:user:edit", "system:role:view"
    )),
):
    return rbac_service.get_role_options(db)


@router.put("/{role_id}", summary="更新角色")
def update_role(
    role_id: int,
    data: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:role:edit")),
):
    return rbac_service.update_role(db, role_id, data, operator_id=scope_ctx["user_id"], request=request)


@router.delete("/{role_id}", summary="删除角色")
def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:role:delete")),
):
    return rbac_service.delete_role(db, role_id, operator_id=scope_ctx["user_id"], request=request)


@router.get("/{role_id}/menus", summary="获取角色菜单权限")
def get_role_menus(
    role_id: int,
    _scope_ctx: dict = Depends(require_permission("system:role:view")),
    db: Session = Depends(get_db),
):
    return {"menu_ids": rbac_service.get_role_menu_ids(db, role_id)}
