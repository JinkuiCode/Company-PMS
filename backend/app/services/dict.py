"""业务枚举维护与兼容查询服务。"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, Request

from app.models.dict import SysDict, SysDictItem
from app.schemas.dict import DictItemCreate, DictItemUpdate
from app.services.enum_registry import (
    ENUM_REGISTRY,
    MANAGED_ENUM_CODES,
    count_enum_references,
    get_enum_definition,
)
from app.services.operation_log import record_operation_log, serialize_model


def _normalize_item_value(dict_code: str, value: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="枚举存储值不能为空")
    if dict_code == "product_line" and "," in normalized:
        raise HTTPException(status_code=400, detail="产品线存储值不能包含逗号")
    return normalized


def get_dict_list(db: Session) -> list[dict]:
    """只返回开发注册且允许维护的业务枚举。"""
    definitions = db.query(SysDict).filter(
        SysDict.dict_code.in_(MANAGED_ENUM_CODES)
    ).order_by(SysDict.sort, SysDict.id).all()
    result = []
    for definition in definitions:
        config = ENUM_REGISTRY[definition.dict_code]
        result.append({
            "id": definition.id,
            "dict_code": definition.dict_code,
            "dict_name": definition.dict_name,
            "description": definition.description,
            "sort": definition.sort,
            "status": definition.status,
            "mode": config["mode"],
            "allow_add": config["mode"] == "configurable",
            "allow_value_edit": config["mode"] == "configurable",
            "bindings": config["bindings"],
            "item_count": db.query(SysDictItem).filter(SysDictItem.dict_id == definition.id).count(),
        })
    return result


# ==================== 字典项 ====================
def get_dict_items(db: Session, dict_id: int) -> list[dict]:
    """获取枚举值及引用数量。"""
    definition = db.query(SysDict).filter(SysDict.id == dict_id).first()
    if not definition or definition.dict_code not in MANAGED_ENUM_CODES:
        raise HTTPException(status_code=404, detail="枚举定义不存在或未开放维护")
    config = get_enum_definition(definition.dict_code, managed_only=True)
    items = db.query(SysDictItem).filter(SysDictItem.dict_id == dict_id).order_by(SysDictItem.sort, SysDictItem.id).all()
    result = []
    for item in items:
        reference_count = count_enum_references(db, definition.dict_code, item.item_value)
        result.append({
            "id": item.id,
            "dict_id": item.dict_id,
            "item_value": item.item_value,
            "item_label": item.item_label,
            "description": item.description,
            "sort": item.sort,
            "status": item.status,
            "reference_count": reference_count,
            "value_locked": config["mode"] != "configurable" or reference_count > 0,
            "deletable": config["mode"] == "configurable" and reference_count == 0,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        })
    return result


def create_dict_item(db: Session, dict_id: int, data: DictItemCreate, operator_id: int | None = None, request: Request | None = None):
    """新增枚举项"""
    d = db.query(SysDict).filter(SysDict.id == dict_id).first()
    if not d or d.dict_code not in MANAGED_ENUM_CODES:
        raise HTTPException(status_code=404, detail="枚举定义不存在或未开放维护")
    config = get_enum_definition(d.dict_code, managed_only=True)
    if config["mode"] != "configurable":
        raise HTTPException(status_code=400, detail="固定流程枚举不允许新增存储值")
    item_value = _normalize_item_value(d.dict_code, data.item_value)
    # 检查同分类下 value 唯一性
    existing = db.query(SysDictItem).filter(
        SysDictItem.dict_id == dict_id,
        SysDictItem.item_value == item_value,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该分类下已存在相同的存储值")
    item_data = data.model_dump()
    item_data["item_value"] = item_value
    item = SysDictItem(dict_id=dict_id, **item_data)
    db.add(item)
    db.flush()
    record_operation_log(
        db,
        module="系统管理",
        action="create",
        entity_type="sys_enum_item",
        entity_id=item.id,
        entity_name=item.item_label,
        operator_id=operator_id,
        request=request,
        summary=f"创建枚举值：{d.dict_name} / {item.item_label}",
        after_data=serialize_model(item, extra={"dict_name": d.dict_name}),
    )
    db.commit()
    db.refresh(item)
    return {"msg": "创建成功", "id": item.id}


def update_dict_item(db: Session, item_id: int, data: DictItemUpdate, operator_id: int | None = None, request: Request | None = None):
    """更新枚举项"""
    item = db.query(SysDictItem).filter(SysDictItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="枚举项不存在")
    d = db.query(SysDict).filter(SysDict.id == item.dict_id).first()
    if not d or d.dict_code not in MANAGED_ENUM_CODES:
        raise HTTPException(status_code=404, detail="枚举定义不存在或未开放维护")
    config = get_enum_definition(d.dict_code, managed_only=True)
    before = serialize_model(item)
    update_data = data.model_dump(exclude_unset=True)
    if "item_value" in update_data:
        update_data["item_value"] = _normalize_item_value(d.dict_code, update_data["item_value"])
    reference_count = count_enum_references(db, d.dict_code, item.item_value)
    if "item_value" in update_data and update_data["item_value"] != item.item_value:
        if config["mode"] != "configurable":
            raise HTTPException(status_code=400, detail="固定流程枚举不允许修改存储值")
        if reference_count > 0:
            raise HTTPException(status_code=409, detail="该枚举值已被引用，不可修改存储值")
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
    record_operation_log(
        db,
        module="系统管理",
        action="update",
        entity_type="sys_enum_item",
        entity_id=item.id,
        entity_name=item.item_label,
        operator_id=operator_id,
        request=request,
        summary=f"更新枚举值：{d.dict_name} / {item.item_label}",
        before_data=before,
        after_data=serialize_model(item),
    )
    db.commit()
    return {"msg": "更新成功"}


def delete_dict_item(db: Session, item_id: int, operator_id: int | None = None, request: Request | None = None):
    """删除字典项（枚举定义且被引用时拒绝）"""
    item = db.query(SysDictItem).filter(SysDictItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="字典项不存在")
    d = db.query(SysDict).filter(SysDict.id == item.dict_id).first()
    if not d or d.dict_code not in MANAGED_ENUM_CODES:
        raise HTTPException(status_code=404, detail="枚举定义不存在或未开放维护")
    config = get_enum_definition(d.dict_code, managed_only=True)
    if config["mode"] != "configurable":
        raise HTTPException(status_code=400, detail="固定流程枚举不可删除，只能调整显示名、排序或启停")
    count = count_enum_references(db, d.dict_code, item.item_value)
    if count > 0:
        raise HTTPException(status_code=409, detail=f"该枚举值已被 {count} 条数据引用，不可删除，可改为禁用")
    before = serialize_model(item)
    db.delete(item)
    record_operation_log(
        db,
        module="系统管理",
        action="delete",
        entity_type="sys_enum_item",
        entity_id=item_id,
        entity_name=item.item_label,
        operator_id=operator_id,
        request=request,
        summary=f"删除枚举值：{d.dict_name} / {item.item_label}",
        before_data=before,
    )
    db.commit()
    return {"msg": "删除成功"}


# ==================== 按编码查询枚举值 ====================
def get_dict_by_code(db: Session, dict_code: str) -> dict | None:
    """按字典编码获取枚举值列表（供前端下拉使用）"""
    d = db.query(SysDict).filter(SysDict.dict_code == dict_code, SysDict.status == 1).first()
    if not d:
        return None
    all_items = db.query(SysDictItem).filter(
        SysDictItem.dict_id == d.id,
    ).order_by(SysDictItem.sort, SysDictItem.id).all()
    active_items = [item for item in all_items if item.status == 1]
    return {
        "dict_code": d.dict_code,
        "dict_name": d.dict_name,
        "items": [
            {"value": i.item_value, "label": i.item_label}
            for i in active_items
        ],
        "all_items": [
            {"value": i.item_value, "label": i.item_label, "status": i.status}
            for i in all_items
        ],
        "label_map": {i.item_value: i.item_label for i in all_items},
    }
