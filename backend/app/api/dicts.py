from fastapi import APIRouter, Depends
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


@router.post("", summary="新增字典分类", dependencies=[Depends(get_current_user_id)])
def create_dict(data: DictCreate, db: Session = Depends(get_db)):
    return dict_service.create_dict(db, data)


@router.put("/{dict_id}", summary="编辑字典分类", dependencies=[Depends(get_current_user_id)])
def update_dict(dict_id: int, data: DictUpdate, db: Session = Depends(get_db)):
    return dict_service.update_dict(db, dict_id, data)


@router.delete("/{dict_id}", summary="删除字典分类", dependencies=[Depends(get_current_user_id)])
def delete_dict(dict_id: int, db: Session = Depends(get_db)):
    return dict_service.delete_dict(db, dict_id)


# ==================== 字典项 ====================
@router.get("/{dict_id}/items", summary="获取枚举项列表", dependencies=[Depends(get_current_user_id)])
def list_dict_items(dict_id: int, db: Session = Depends(get_db)):
    return dict_service.get_dict_items(db, dict_id)


@router.post("/{dict_id}/items", summary="新增枚举项", dependencies=[Depends(get_current_user_id)])
def create_dict_item(dict_id: int, data: DictItemCreate, db: Session = Depends(get_db)):
    return dict_service.create_dict_item(db, dict_id, data)


@router.put("/items/{item_id}", summary="编辑枚举项", dependencies=[Depends(get_current_user_id)])
def update_dict_item(item_id: int, data: DictItemUpdate, db: Session = Depends(get_db)):
    return dict_service.update_dict_item(db, item_id, data)


@router.delete("/items/{item_id}", summary="删除枚举项", dependencies=[Depends(get_current_user_id)])
def delete_dict_item(item_id: int, db: Session = Depends(get_db)):
    return dict_service.delete_dict_item(db, item_id)


# ==================== 按编码查询（供前端表单下拉使用） ====================
@router.get("/code/{dict_code}", summary="按编码查询枚举值")
def get_dict_by_code(dict_code: str, db: Session = Depends(get_db)):
    """公开接口，前端表单下拉框读取枚举值"""
    result = dict_service.get_dict_by_code(db, dict_code)
    if not result:
        return {"dict_code": dict_code, "dict_name": "", "items": []}
    return result
