"""数据字典 CRUD 业务逻辑"""
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.dict import SysDict, SysDictItem
from app.schemas.dict import (
    DictCreate, DictUpdate, DictResponse,
    DictItemCreate, DictItemUpdate, DictItemResponse,
)


# ==================== 字典分类 ====================
def get_dict_list(db: Session) -> list[DictResponse]:
    """获取所有字典分类"""
    dicts = db.query(SysDict).order_by(SysDict.sort, SysDict.id).all()
    return [DictResponse.model_validate(d) for d in dicts]


def create_dict(db: Session, data: DictCreate):
    """创建字典分类"""
    if db.query(SysDict).filter(SysDict.dict_code == data.dict_code).first():
        raise HTTPException(status_code=400, detail="字典编码已存在")
    d = SysDict(**data.model_dump())
    db.add(d)
    db.commit()
    db.refresh(d)
    return {"msg": "创建成功", "id": d.id}


def update_dict(db: Session, dict_id: int, data: DictUpdate):
    """更新字典分类"""
    d = db.query(SysDict).filter(SysDict.id == dict_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="字典分类不存在")
    update_data = data.model_dump(exclude_unset=True)
    # 检查编码唯一性
    if "dict_code" in update_data:
        existing = db.query(SysDict).filter(
            SysDict.dict_code == update_data["dict_code"],
            SysDict.id != dict_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="字典编码已存在")
    for key, val in update_data.items():
        setattr(d, key, val)
    db.commit()
    return {"msg": "更新成功"}


def delete_dict(db: Session, dict_id: int):
    """删除字典分类（有子项时不允许）"""
    d = db.query(SysDict).filter(SysDict.id == dict_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="字典分类不存在")
    item_count = db.query(SysDictItem).filter(SysDictItem.dict_id == dict_id).count()
    if item_count > 0:
        raise HTTPException(status_code=400, detail="该分类下还有枚举项，请先删除所有枚举项")
    db.delete(d)
    db.commit()
    return {"msg": "删除成功"}


# ==================== 字典项 ====================
def get_dict_items(db: Session, dict_id: int) -> list[DictItemResponse]:
    """获取某分类下的所有枚举项"""
    items = db.query(SysDictItem).filter(SysDictItem.dict_id == dict_id).order_by(SysDictItem.sort, SysDictItem.id).all()
    return [DictItemResponse.model_validate(i) for i in items]


def create_dict_item(db: Session, dict_id: int, data: DictItemCreate):
    """新增枚举项"""
    d = db.query(SysDict).filter(SysDict.id == dict_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="字典分类不存在")
    # 检查同分类下 value 唯一性
    existing = db.query(SysDictItem).filter(
        SysDictItem.dict_id == dict_id,
        SysDictItem.item_value == data.item_value
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该分类下已存在相同的存储值")
    item = SysDictItem(dict_id=dict_id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"msg": "创建成功", "id": item.id}


def update_dict_item(db: Session, item_id: int, data: DictItemUpdate):
    """更新枚举项"""
    item = db.query(SysDictItem).filter(SysDictItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="枚举项不存在")
    update_data = data.model_dump(exclude_unset=True)
    # 检查同分类下 value 唯一性
    if "item_value" in update_data:
        existing = db.query(SysDictItem).filter(
            SysDictItem.dict_id == item.dict_id,
            SysDictItem.item_value == update_data["item_value"],
            SysDictItem.id != item_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="该分类下已存在相同的存储值")
    for key, val in update_data.items():
        setattr(item, key, val)
    db.commit()
    return {"msg": "更新成功"}


def delete_dict_item(db: Session, item_id: int):
    """删除字典项（枚举定义且被引用时拒绝）"""
    item = db.query(SysDictItem).filter(SysDictItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="字典项不存在")
    # 仅对枚举定义（有 field_name 的分类）做引用检查
    d = db.query(SysDict).filter(SysDict.id == item.dict_id).first()
    if d and d.field_name and d.table_name:
        from sqlalchemy import text
        try:
            sql = text(f"SELECT COUNT(*) FROM {d.table_name} WHERE {d.field_name} = :val")
            result = db.execute(sql, {"val": item.item_value})
            count = result.scalar()
            if count and count > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"该枚举值已被 {count} 条数据引用，不可删除，可改为禁用"
                )
        except HTTPException:
            raise
        except Exception:
            pass
    db.delete(item)
    db.commit()
    return {"msg": "删除成功"}


# ==================== 按编码查询枚举值 ====================
def get_dict_by_code(db: Session, dict_code: str) -> dict | None:
    """按字典编码获取枚举值列表（供前端下拉使用）"""
    d = db.query(SysDict).filter(SysDict.dict_code == dict_code, SysDict.status == 1).first()
    if not d:
        return None
    items = db.query(SysDictItem).filter(
        SysDictItem.dict_id == d.id,
        SysDictItem.status == 1
    ).order_by(SysDictItem.sort, SysDictItem.id).all()
    return {
        "dict_code": d.dict_code,
        "dict_name": d.dict_name,
        "items": [
            {"value": i.item_value, "label": i.item_label}
            for i in items
        ]
    }
