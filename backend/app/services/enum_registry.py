"""业务枚举注册表、初始化和运行时校验。"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.dict import SysDict, SysDictItem
from app.models.project import PmsProject, PmsProjectArchive, PmsTask
from app.models.rbac import SysRole


LEGACY_DICT_CODES = {
    "user_manage",
    "role_manage",
    "project_list",
    "project_archive",
    "project_task",
}


ENUM_REGISTRY: dict[str, dict[str, Any]] = {
    "archive_status": {
        "name": "档案状态",
        "description": "项目档案生命周期状态",
        "mode": "workflow",
        "visible": True,
        "sort": 10,
        "table_name": "pms_project_archive",
        "field_name": "status",
        "bindings": ["项目档案.status"],
        "items": [("1", "未启动"), ("2", "进行中"), ("3", "已完结"), ("4", "暂停")],
    },
    "project_status": {
        "name": "项目状态",
        "description": "项目进度当前节点状态",
        "mode": "workflow",
        "visible": True,
        "sort": 11,
        "table_name": "pms_project",
        "field_name": "status",
        "bindings": ["项目进度.status", "项目总表.node_status"],
        "items": [("1", "进行中"), ("2", "已完结"), ("3", "暂停")],
    },
    "product_line": {
        "name": "产品线",
        "description": "档案、项目进度及角色范围共用产品线",
        "mode": "configurable",
        "visible": True,
        "sort": 12,
        "table_name": "pms_project_archive",
        "field_name": "product_line",
        "bindings": ["项目档案.product_line", "项目进度.product_line", "角色.product_lines"],
        "items": [("Bench", "Bench"), ("光伏", "光伏"), ("Single", "Single"), ("HOTSPM", "HOTSPM")],
    },
    "product_type": {
        "name": "产品类型",
        "description": "项目档案产品类型",
        "mode": "configurable",
        "visible": True,
        "sort": 13,
        "table_name": "pms_project_archive",
        "field_name": "product_type",
        "bindings": ["项目档案.product_type"],
        "items": [("链式", "链式"), ("槽式", "槽式")],
    },
    "task_status": {
        "name": "任务状态",
        "description": "项目任务执行状态",
        "mode": "workflow",
        "visible": True,
        "sort": 14,
        "table_name": "pms_task",
        "field_name": "status",
        "bindings": ["任务进度.status"],
        "items": [("1", "未开始"), ("2", "进行中"), ("3", "已完成")],
    },
    "erp_sync_status": {
        "name": "ERP 同步状态",
        "description": "金蝶同步系统语义，不开放维护",
        "mode": "system",
        "visible": False,
        "sort": 15,
        "table_name": "pms_project_archive",
        "field_name": "erp_sync_status",
        "bindings": ["项目档案.erp_sync_status"],
        "items": [("success", "成功"), ("failed", "失败"), ("pending", "待同步")],
    },
    "data_scope": {
        "name": "数据权限",
        "description": "RBAC 数据范围系统语义，不开放维护",
        "mode": "system",
        "visible": False,
        "sort": 16,
        "table_name": "sys_role",
        "field_name": "data_scope",
        "bindings": ["角色.data_scope"],
        "items": [("1", "本人"), ("2", "本部门"), ("3", "本部门及子部门"), ("4", "全部")],
    },
}


MANAGED_ENUM_CODES = {
    code for code, definition in ENUM_REGISTRY.items() if definition["visible"]
}
SYSTEM_ENUM_CODES = {
    code for code, definition in ENUM_REGISTRY.items() if definition["mode"] == "system"
}


def initialize_enum_definitions(db: Session) -> list[str]:
    """迁移旧混合分类并初始化注册枚举；返回未注册历史分类编码。"""
    legacy = db.query(SysDict).filter(SysDict.dict_code.in_(LEGACY_DICT_CODES)).all()
    for definition in legacy:
        db.query(SysDictItem).filter(SysDictItem.dict_id == definition.id).delete()
        db.delete(definition)
    if legacy:
        db.flush()

    for code, config in ENUM_REGISTRY.items():
        definition = db.query(SysDict).filter(SysDict.dict_code == code).first()
        created = definition is None
        if created:
            definition = SysDict(dict_code=code, dict_name=config["name"])
            db.add(definition)
            db.flush()

        definition.dict_name = config["name"]
        definition.page_name = "枚举管理" if config["visible"] else "系统固定"
        definition.table_name = config["table_name"]
        definition.field_name = config["field_name"]
        definition.description = config["description"]
        definition.sort = config["sort"]
        definition.status = 1

        existing_items = db.query(SysDictItem).filter(SysDictItem.dict_id == definition.id).all()
        existing_values = {item.item_value for item in existing_items}
        should_restore_fixed = config["mode"] in {"workflow", "system"}
        if created or should_restore_fixed:
            for sort, (value, label) in enumerate(config["items"], 1):
                if value not in existing_values:
                    db.add(SysDictItem(
                        dict_id=definition.id,
                        item_value=value,
                        item_label=label,
                        sort=sort,
                        status=1,
                    ))

        if config["mode"] == "workflow":
            registered_values = {value for value, _label in config["items"]}
            for item in existing_items:
                if item.item_value in registered_values:
                    continue
                if count_enum_references(db, code, item.item_value) > 0:
                    item.status = 0
                    item.description = "历史流程值，已停用，仅用于保留历史数据显示"
                else:
                    db.delete(item)

    db.commit()
    known_codes = set(ENUM_REGISTRY) | LEGACY_DICT_CODES
    unknown_codes = [
        code for (code,) in db.query(SysDict.dict_code).filter(~SysDict.dict_code.in_(known_codes)).all()
    ]
    if unknown_codes:
        print(f"枚举迁移提示：以下历史自建分类已隐藏，未删除：{', '.join(sorted(unknown_codes))}")
    return sorted(unknown_codes)


def get_enum_definition(code: str, *, managed_only: bool = False) -> dict[str, Any]:
    definition = ENUM_REGISTRY.get(code)
    if not definition or (managed_only and code not in MANAGED_ENUM_CODES):
        raise HTTPException(status_code=404, detail="枚举定义不存在或未开放维护")
    return definition


def count_enum_references(db: Session, code: str, value: str) -> int:
    """按注册绑定统计精确引用数量。"""
    integer_value = None
    if code in {"archive_status", "project_status", "task_status"}:
        try:
            integer_value = int(value)
        except (TypeError, ValueError):
            return 0
    if code == "archive_status":
        return db.query(PmsProjectArchive).filter(PmsProjectArchive.status == integer_value).count()
    if code == "project_status":
        return db.query(PmsProject).filter(PmsProject.status == integer_value).count()
    if code == "task_status":
        return db.query(PmsTask).filter(PmsTask.status == integer_value).count()
    if code == "product_type":
        return db.query(PmsProjectArchive).filter(PmsProjectArchive.product_type == value).count()
    if code == "product_line":
        archive_count = db.query(PmsProjectArchive).filter(PmsProjectArchive.product_line == value).count()
        project_count = db.query(PmsProject).filter(PmsProject.product_line == value).count()
        role_count = sum(
            1
            for (raw_lines,) in db.query(SysRole.product_lines).filter(SysRole.product_lines.isnot(None)).all()
            if value in {line.strip() for line in (raw_lines or "").split(",") if line.strip()}
        )
        return archive_count + project_count + role_count
    return 0


def validate_enum_value(
    db: Session,
    code: str,
    value: Any,
    *,
    current_value: Any = None,
) -> str | None:
    """校验新增/变更使用的枚举；未改变的历史禁用值继续有效。"""
    if value is None or value == "":
        return None
    normalized = str(value)
    if current_value is not None and normalized == str(current_value):
        return normalized

    get_enum_definition(code)
    definition = db.query(SysDict).filter(
        SysDict.dict_code == code,
        SysDict.status == 1,
    ).first()
    item = None
    if definition:
        item = db.query(SysDictItem).filter(
            SysDictItem.dict_id == definition.id,
            SysDictItem.item_value == normalized,
            SysDictItem.status == 1,
        ).first()
    if not item:
        raise HTTPException(status_code=422, detail=f"枚举 {code} 的值 {normalized} 不存在或已禁用")
    return normalized
