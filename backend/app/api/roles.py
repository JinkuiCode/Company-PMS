from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import get_current_user_id
from app.schemas.rbac import RoleCreate, RoleUpdate
from app.services import rbac as rbac_service

router = APIRouter(prefix="/api/roles", tags=["角色管理"])


@router.get("", summary="角色列表", dependencies=[Depends(get_current_user_id)])
def list_roles(db: Session = Depends(get_db)):
    return rbac_service.get_role_list(db)


@router.post("", summary="创建角色", dependencies=[Depends(get_current_user_id)])
def create_role(data: RoleCreate, db: Session = Depends(get_db)):
    return rbac_service.create_role(db, data)


@router.put("/{role_id}", summary="更新角色", dependencies=[Depends(get_current_user_id)])
def update_role(role_id: int, data: RoleUpdate, db: Session = Depends(get_db)):
    return rbac_service.update_role(db, role_id, data)


@router.delete("/{role_id}", summary="删除角色", dependencies=[Depends(get_current_user_id)])
def delete_role(role_id: int, db: Session = Depends(get_db)):
    return rbac_service.delete_role(db, role_id)


@router.get("/{role_id}/menus", summary="获取角色菜单权限")
def get_role_menus(role_id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return {"menu_ids": rbac_service.get_role_menu_ids(db, role_id)}
