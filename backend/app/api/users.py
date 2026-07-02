from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import get_current_user_id
from app.schemas.user import UserCreate, UserUpdate
from app.services import rbac as rbac_service

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("", summary="用户列表", dependencies=[Depends(get_current_user_id)])
def list_users(page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=10000),
               dept_id: int | None = Query(None, description="按部门过滤"),
               db: Session = Depends(get_db)):
    return rbac_service.get_user_list(db, page, page_size, dept_id=dept_id)


@router.post("", summary="创建用户", dependencies=[Depends(get_current_user_id)])
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    return rbac_service.create_user(db, data)


@router.put("/{user_id}", summary="更新用户", dependencies=[Depends(get_current_user_id)])
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    return rbac_service.update_user(db, user_id, data)


@router.delete("/{user_id}", summary="删除用户", dependencies=[Depends(get_current_user_id)])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    return rbac_service.delete_user(db, user_id)
