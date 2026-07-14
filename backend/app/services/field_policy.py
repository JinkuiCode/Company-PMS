"""项目档案与项目进度的统一字段治理。"""
from __future__ import annotations

import datetime
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models.field_policy import SysBusinessFieldPolicy
from app.schemas.field_policy import FieldPolicyBatchUpdate
from app.services.operation_log import record_operation_log, serialize_model
from app.services.project_sheet_fields import PROJECT_SHEET_FIELDS, PROJECT_SHEET_GROUPS


MODULE_PROJECT_ARCHIVE = "project_archive"
MODULE_PROJECT_PROGRESS = "project_progress"
SUPPORTED_MODULES = {MODULE_PROJECT_ARCHIVE, MODULE_PROJECT_PROGRESS}


def _registry_field(
    key: str,
    label: str,
    group: str,
    *,
    value_type: str = "text",
    source_type: str = "detail",
    visible: bool = True,
    editable: bool = True,
    required: bool = False,
    list_available: bool = True,
    visible_locked: bool = False,
    editable_locked: bool = False,
    required_locked: bool = False,
    list_available_locked: bool = False,
    enum_code: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "field_key": key,
        "label": label,
        "group": group,
        "value_type": value_type,
        "source_type": source_type,
        "enum_code": enum_code,
        "default_visible": visible,
        "default_editable": editable,
        "default_required": required,
        "default_list_available": list_available,
        "visible_cap": True,
        "editable_cap": editable,
        "required_cap": bool(required or editable),
        "list_available_cap": list_available,
        "visible_locked": visible_locked,
        "editable_locked": editable_locked or not editable,
        "required_locked": required_locked,
        "list_available_locked": list_available_locked or not list_available,
    }


ARCHIVE_GROUPS = [
    {"key": "basic", "label": "基础信息"},
    {"key": "plan", "label": "计划信息"},
    {"key": "erp", "label": "ERP 同步"},
    {"key": "system", "label": "系统信息"},
]

ARCHIVE_FIELDS = [
    _registry_field("project_code", "项目编号", "basic", required=True, visible_locked=True, editable_locked=True, required_locked=True),
    _registry_field("project_name", "项目名称", "basic", required=True, visible_locked=True, editable_locked=True, required_locked=True),
    _registry_field("product_line", "产品线", "basic", value_type="select", enum_code="product_line"),
    _registry_field(
        "status",
        "状态",
        "basic",
        value_type="select",
        required=True,
        visible_locked=True,
        editable_locked=True,
        required_locked=True,
        enum_code="archive_status",
    ),
    _registry_field("manager_id", "负责人", "basic", value_type="user"),
    _registry_field("product_type", "产品类型", "basic", value_type="select", enum_code="product_type"),
    _registry_field("plan_start_date", "计划开始", "plan", value_type="date"),
    _registry_field("plan_end_date", "计划结束", "plan", value_type="date"),
    _registry_field("erp_sync_status", "同步状态", "erp", source_type="system", editable=False),
    _registry_field("erp_sync_time", "最后同步时间", "erp", value_type="datetime", source_type="system", editable=False),
    _registry_field("erp_sync_by_name", "最后同步人", "erp", source_type="system", editable=False),
    _registry_field("created_by_name", "创建人", "system", source_type="system", editable=False),
    _registry_field("updated_by_name", "最后编辑人", "system", source_type="system", editable=False),
    _registry_field("created_at", "创建时间", "system", value_type="datetime", source_type="system", editable=False),
    _registry_field("updated_at", "最后编辑时间", "system", value_type="datetime", source_type="system", editable=False),
]


def _progress_fields() -> list[dict[str, Any]]:
    fields = [
        _registry_field("archive_id", "项目档案", "basic", source_type="archive", editable=False, required=True, visible_locked=True, required_locked=True, list_available=False),
        _registry_field("dept_id", "负责人部门", "basic", value_type="department", source_type="project", required=True, visible_locked=True, editable_locked=True, required_locked=True, list_available=False),
        _registry_field("pm_id", "项目经理", "people", value_type="user", source_type="project", required=True, visible_locked=True, editable_locked=True, required_locked=True, list_available=False),
        _registry_field("budget", "预算", "basic", value_type="number", source_type="project", list_available=False),
        _registry_field("description", "项目描述", "progress_notes", value_type="long_text", source_type="project", list_available=False),
    ]
    existing = {field["key"] for field in fields}
    for sheet in PROJECT_SHEET_FIELDS:
        if sheet["key"] in existing:
            continue
        editable = bool(sheet["editable"] and sheet["source_type"] in {"detail", "project"})
        fields.append(_registry_field(
            sheet["key"],
            sheet["label"],
            sheet["group"],
            value_type=sheet["value_type"],
            source_type=sheet["source_type"],
            editable=editable,
            list_available=bool(sheet["list_available"]),
            enum_code=sheet.get("enum_code"),
        ))
    return fields


PROGRESS_FIELDS = _progress_fields()
GROUPS_BY_MODULE = {
    MODULE_PROJECT_ARCHIVE: ARCHIVE_GROUPS,
    MODULE_PROJECT_PROGRESS: PROJECT_SHEET_GROUPS,
}
FIELDS_BY_MODULE = {
    MODULE_PROJECT_ARCHIVE: ARCHIVE_FIELDS,
    MODULE_PROJECT_PROGRESS: PROGRESS_FIELDS,
}


def _ensure_module(module_code: str) -> None:
    if module_code not in SUPPORTED_MODULES:
        raise HTTPException(status_code=404, detail="字段规则模块不存在")


def get_business_field_registry(module_code: str) -> list[dict[str, Any]]:
    _ensure_module(module_code)
    return [dict(field) for field in FIELDS_BY_MODULE[module_code]]


def _row_snapshot(row: SysBusinessFieldPolicy | None) -> dict[str, Any] | None:
    return serialize_model(row) if row else None


def get_effective_field_policies(db: Session, module_code: str) -> dict[str, Any]:
    _ensure_module(module_code)
    rows = {
        row.field_key: row
        for row in db.query(SysBusinessFieldPolicy).filter(
            SysBusinessFieldPolicy.module_code == module_code
        ).all()
    }
    items: list[dict[str, Any]] = []
    for base in FIELDS_BY_MODULE[module_code]:
        row = rows.get(base["key"])
        visible = base["default_visible"] if not row or base["visible_locked"] else bool(row.visible)
        editable = base["default_editable"] if not row or base["editable_locked"] else bool(row.editable)
        required = base["default_required"] if not row or base["required_locked"] else bool(row.required)
        list_available = (
            base["default_list_available"]
            if not row or base["list_available_locked"]
            else bool(row.list_available)
        )
        editable = bool(editable and base["editable_cap"])
        list_available = bool(list_available and base["list_available_cap"] and visible)
        item = {
            **base,
            "module_code": module_code,
            "visible": bool(visible),
            "editable": editable,
            "required": bool(required),
            "list_available": list_available,
            "required_effective_at": row.required_effective_at if row else None,
            "updated_at": row.updated_at if row else None,
        }
        items.append(item)

    group_labels = {group["key"]: group["label"] for group in GROUPS_BY_MODULE[module_code]}
    return {
        "module_code": module_code,
        "groups": GROUPS_BY_MODULE[module_code],
        "items": [{**item, "group_label": group_labels.get(item["group"], item["group"])} for item in items],
    }


def _raise_invalid(field_key: str, message: str) -> None:
    raise HTTPException(
        status_code=422,
        detail={"code": "FIELD_POLICY_INVALID", "fields": [{"field_key": field_key, "message": message}]},
    )


def update_field_policies(
    db: Session,
    module_code: str,
    data: FieldPolicyBatchUpdate,
    *,
    operator_id: int | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    _ensure_module(module_code)
    registry = {field["key"]: field for field in FIELDS_BY_MODULE[module_code]}
    existing = {
        row.field_key: row
        for row in db.query(SysBusinessFieldPolicy).filter(
            SysBusinessFieldPolicy.module_code == module_code
        ).all()
    }
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    now = datetime.datetime.now()

    for item in data.items:
        base = registry.get(item.field_key)
        if not base:
            _raise_invalid(item.field_key, "未知字段")
        desired = item.model_dump(exclude={"expected_updated_at"})
        for flag in ("visible", "editable", "required", "list_available"):
            if base[f"{flag}_locked"] and desired[flag] != base[f"default_{flag}"]:
                _raise_invalid(item.field_key, f"{flag} 由代码规则锁定")
            if desired[flag] and not base[f"{flag}_cap"]:
                _raise_invalid(item.field_key, f"{flag} 超出字段技术上限")
        if desired["required"] and (not desired["visible"] or not desired["editable"]):
            _raise_invalid(item.field_key, "必填字段必须可见且可编辑")
        if desired["list_available"] and not desired["visible"]:
            _raise_invalid(item.field_key, "隐藏字段不能加入列表")

        row = existing.get(item.field_key)
        if row:
            expected_updated_at = item.expected_updated_at.replace(tzinfo=None) if item.expected_updated_at else None
            if not expected_updated_at or not row.updated_at or row.updated_at != expected_updated_at:
                raise HTTPException(status_code=409, detail="字段规则已被其他用户修改，请刷新后重试")
        elif item.expected_updated_at:
            raise HTTPException(status_code=409, detail="字段规则已被其他用户重置，请刷新后重试")

        before[item.field_key] = _row_snapshot(row)
        previous_required = bool(row.required) if row else bool(base["default_required"])
        if not row:
            row = SysBusinessFieldPolicy(
                module_code=module_code,
                field_key=item.field_key,
                created_by=operator_id,
            )
            db.add(row)
            existing[item.field_key] = row
        row.visible = desired["visible"]
        row.editable = desired["editable"]
        row.required = desired["required"]
        row.list_available = desired["list_available"]
        if desired["required"] and not previous_required:
            row.required_effective_at = now
        elif not desired["required"]:
            row.required_effective_at = None
        row.updated_by = operator_id
        db.flush()
        after[item.field_key] = _row_snapshot(row)

    if data.items:
        record_operation_log(
            db,
            module="字段规则",
            action="update",
            entity_type="sys_business_field_policy",
            entity_id=module_code,
            entity_name=module_code,
            operator_id=operator_id,
            request=request,
            summary=f"批量更新字段规则：{module_code}",
            before_data=before,
            after_data=after,
        )
    db.commit()
    return get_effective_field_policies(db, module_code)


def reset_field_policies(
    db: Session,
    module_code: str,
    *,
    operator_id: int | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    _ensure_module(module_code)
    rows = db.query(SysBusinessFieldPolicy).filter(
        SysBusinessFieldPolicy.module_code == module_code
    ).all()
    before = {row.field_key: serialize_model(row) for row in rows}
    for row in rows:
        db.delete(row)
    record_operation_log(
        db,
        module="字段规则",
        action="reset",
        entity_type="sys_business_field_policy",
        entity_id=module_code,
        entity_name=module_code,
        operator_id=operator_id,
        request=request,
        summary=f"恢复字段代码默认值：{module_code}",
        before_data=before,
        after_data={},
    )
    db.commit()
    return get_effective_field_policies(db, module_code)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def validate_business_field_write(
    db: Session,
    module_code: str,
    *,
    current_values: dict[str, Any],
    updates: dict[str, Any],
    entity_created_at: datetime.datetime | None,
    is_create: bool,
) -> dict[str, Any]:
    """校验用户写入与当前字段规则，返回合并后的业务值。"""
    effective = get_effective_field_policies(db, module_code)
    policies = {item["field_key"]: item for item in effective["items"]}
    errors: list[dict[str, str]] = []
    merged = {**current_values, **updates}

    for key, value in updates.items():
        policy = policies.get(key)
        if not policy:
            errors.append({"field_key": key, "message": "未知字段"})
            continue
        if not policy["editable"] and current_values.get(key) != value:
            errors.append({"field_key": key, "message": "字段已设为只读"})

    for policy in effective["items"]:
        if not policy["required"]:
            continue
        effective_at = policy.get("required_effective_at")
        # 代码级结构必填继续由 Pydantic/数据库负责；这里仅执行后来启用的业务必填。
        applies = bool(effective_at) and (
            is_create or bool(entity_created_at and entity_created_at >= effective_at)
        )
        if applies and _is_empty(merged.get(policy["field_key"])):
            errors.append({"field_key": policy["field_key"], "message": "此字段为必填项"})

    if errors:
        raise HTTPException(
            status_code=422,
            detail={"code": "FIELD_POLICY_VALIDATION_FAILED", "fields": errors},
        )
    return merged
