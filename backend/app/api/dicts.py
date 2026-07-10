from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import get_current_user_id
from app.schemas.dict import DictCreate, DictUpdate, DictItemCreate, DictItemUpdate
from app.services import dict as dict_service

router = APIRouter(prefix="/api/dicts", tags=["数据字典"])


# ==================== 字典分类 ====================
@router.get("", summary="字典分类列表", dependencies=[Depends(get_current_user_id)])
def list_dicts(db: Session = Depends(get_db)):
    return dict_service.get_dict_list(db)


@router.post("", summary="新增字典分类")
def create_dict(
    data: DictCreate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return dict_service.create_dict(db, data, operator_id=user_id, request=request)


@router.put("/{dict_id}", summary="编辑字典分类")
def update_dict(
    dict_id: int,
    data: DictUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return dict_service.update_dict(db, dict_id, data, operator_id=user_id, request=request)


@router.delete("/{dict_id}", summary="删除字典分类")
def delete_dict(
    dict_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return dict_service.delete_dict(db, dict_id, operator_id=user_id, request=request)


# ==================== 字典项 ====================
@router.get("/{dict_id}/items", summary="获取枚举项列表", dependencies=[Depends(get_current_user_id)])
def list_dict_items(dict_id: int, db: Session = Depends(get_db)):
    return dict_service.get_dict_items(db, dict_id)


@router.post("/{dict_id}/items", summary="新增枚举项")
def create_dict_item(
    dict_id: int,
    data: DictItemCreate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return dict_service.create_dict_item(db, dict_id, data, operator_id=user_id, request=request)


@router.put("/items/{item_id}", summary="编辑枚举项")
def update_dict_item(
    item_id: int,
    data: DictItemUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return dict_service.update_dict_item(db, item_id, data, operator_id=user_id, request=request)


@router.delete("/items/{item_id}", summary="删除枚举项")
def delete_dict_item(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return dict_service.delete_dict_item(db, item_id, operator_id=user_id, request=request)


# ==================== 按编码查询（供前端表单下拉使用） ====================
@router.get("/code/{dict_code}", summary="按编码查询枚举值")
def get_dict_by_code(dict_code: str, db: Session = Depends(get_db)):
    """公开接口，前端表单下拉框读取枚举值"""
    result = dict_service.get_dict_by_code(db, dict_code)
    if not result:
        return {"dict_code": dict_code, "dict_name": "", "items": []}
    return result
