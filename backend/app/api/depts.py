from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.authorization import require_any_permission, require_permission
from app.schemas.rbac import DeptCreate, DeptUpdate
from app.services import rbac as rbac_service

router = APIRouter(prefix="/api/depts", tags=["部门管理"])


@router.get("/tree", summary="部门树", dependencies=[Depends(require_permission("system:user:view"))])
def dept_tree(db: Session = Depends(get_db)):
    return rbac_service.get_dept_tree(db)


@router.post("", summary="创建部门")
def create_dept(
    data: DeptCreate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:user:add")),
):
    return rbac_service.create_dept(db, data, operator_id=scope_ctx["user_id"], request=request)


@router.get("/options", summary="部门下拉选项")
def dept_options(
    db: Session = Depends(get_db),
    _scope_ctx: dict = Depends(require_any_permission(
        "project:list:view", "project:list:add", "project:list:edit", "system:user:view"
    )),
):
    return rbac_service.get_dept_options(db)


@router.put("/{dept_id}", summary="更新部门")
def update_dept(
    dept_id: int,
    data: DeptUpdate,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:user:edit")),
):
    return rbac_service.update_dept(db, dept_id, data, operator_id=scope_ctx["user_id"], request=request)


@router.delete("/{dept_id}", summary="删除部门")
def delete_dept(
    dept_id: int,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("system:user:delete")),
):
    return rbac_service.delete_dept(db, dept_id, operator_id=scope_ctx["user_id"], request=request)
