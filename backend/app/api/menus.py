from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import get_current_user_id
from app.schemas.rbac import MenuCreate, MenuUpdate
from app.services import rbac as rbac_service

router = APIRouter(prefix="/api/menus", tags=["菜单管理"])


@router.get("/tree", summary="菜单树", dependencies=[Depends(get_current_user_id)])
def menu_tree(db: Session = Depends(get_db)):
    return rbac_service.get_menu_tree(db)


@router.post("", summary="创建菜单")
def create_menu(
    data: MenuCreate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return rbac_service.create_menu(db, data, operator_id=user_id, request=request)


@router.put("/{menu_id}", summary="更新菜单")
def update_menu(
    menu_id: int,
    data: MenuUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return rbac_service.update_menu(db, menu_id, data, operator_id=user_id, request=request)


@router.delete("/{menu_id}", summary="删除菜单")
def delete_menu(
    menu_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return rbac_service.delete_menu(db, menu_id, operator_id=user_id, request=request)
