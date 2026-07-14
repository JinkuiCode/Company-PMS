"""统一操作日志服务。"""
from __future__ import annotations

import datetime
import decimal
import json
from typing import Any

from fastapi import Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.operation_log import SysOperationLog
from app.models.user import SysUser
from app.services.enum_registry import ENUM_REGISTRY
from app.services.field_catalog import build_field_catalog


SENSITIVE_KEYWORDS = (
    "password",
    "password_hash",
    "token",
    "remember_token",
    "secret",
    "sign",
    "key",
)
MASK_VALUE = "***"

ENTITY_CATALOG_MODULES = {
    "sys_user": "user",
    "sys_role": "role",
    "sys_menu": "permission_menu",
    "sys_dept": "department",
    "sys_enum_item": "enum_item",
    "pms_project": "project_progress",
    "pms_project_archive": "project_archive",
    "pms_task": "task",
}

FIELD_LABEL_OVERRIDES = {
    "archive_id": "项目档案",
    "created_at": "创建时间",
    "created_by": "创建人",
    "created_by_name": "创建人",
    "dept_id": "所属部门",
    "detail_data": "人工维护字段",
    "dict_id": "枚举分类",
    "dict_name": "枚举名称",
    "erp_sync_by": "最后同步人",
    "erp_sync_time": "最后同步时间",
    "erp_synced": "是否已同步 ERP",
    "field_key": "字段编码",
    "item_label": "显示名称",
    "item_value": "存储值",
    "leader_id": "部门负责人",
    "manager_id": "项目负责人",
    "menu_ids": "权限配置",
    "module_code": "业务模块",
    "parent_id": "上级节点",
    "password_hash": "密码",
    "pm_id": "项目经理",
    "product_lines": "产品线范围",
    "role_ids": "角色",
    "sheet_values": "项目总表字段",
    "sort": "排序",
    "updated_at": "最后更新时间",
    "updated_by": "最后编辑人",
}

POLICY_FIELD_LABELS = {
    "visible": "业务显示",
    "editable": "允许编辑",
    "required": "必填",
    "list_available": "列表可选",
    "required_effective_at": "必填生效时间",
}

SYSTEM_VALUE_LABELS = {
    ("sys_user", "status"): {"0": "禁用", "1": "启用"},
    ("sys_role", "status"): {"0": "禁用", "1": "启用"},
    ("sys_dept", "status"): {"0": "禁用", "1": "启用"},
    ("sys_menu", "status"): {"0": "禁用", "1": "启用"},
    ("sys_menu", "visible"): {"0": "隐藏", "1": "显示"},
    ("sys_menu", "menu_type"): {"M": "目录", "C": "页面", "B": "按钮权限"},
    ("sys_enum_item", "status"): {"0": "禁用", "1": "启用"},
    ("pms_project_archive", "erp_synced"): {"0": "否", "1": "是"},
}


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(word in lowered for word in SENSITIVE_KEYWORDS)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value


def sanitize_data(data: Any) -> Any:
    """递归脱敏并转换为可 JSON 化的数据。"""
    if data is None:
        return None
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            result[key] = MASK_VALUE if _is_sensitive_key(str(key)) else sanitize_data(value)
        return result
    if isinstance(data, (list, tuple, set)):
        return [sanitize_data(item) for item in data]
    return _normalize_value(data)


def serialize_model(model: Any, exclude: set[str] | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """把 SQLAlchemy 模型快照为字典，供 before/after 使用。"""
    if model is None:
        return {}
    exclude = exclude or set()
    result: dict[str, Any] = {}
    for column in model.__table__.columns:
        if column.name in exclude:
            continue
        result[column.name] = _normalize_value(getattr(model, column.name))
    if extra:
        result.update({key: _normalize_value(value) for key, value in extra.items()})
    return result


def diff_data(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """计算字段级差异。"""
    before_raw = before or {}
    after_raw = after or {}
    diff: dict[str, dict[str, Any]] = {}
    for key in sorted(set(before_raw.keys()) | set(after_raw.keys())):
        old_raw = before_raw.get(key)
        new_raw = after_raw.get(key)
        if old_raw != new_raw:
            diff[key] = {
                "before": sanitize_data({key: old_raw})[key],
                "after": sanitize_data({key: new_raw})[key],
            }
    return diff


def _catalog_index() -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (item["module"], item["field_code"]): item
        for item in build_field_catalog()
    }


def _flatten_diff_pair(path: str, before: Any, after: Any) -> list[tuple[str, Any, Any]]:
    if isinstance(before, dict) or isinstance(after, dict):
        before_dict = before if isinstance(before, dict) else {}
        after_dict = after if isinstance(after, dict) else {}
        child_keys = sorted(set(before_dict) | set(after_dict))
        if child_keys:
            rows: list[tuple[str, Any, Any]] = []
            for key in child_keys:
                rows.extend(_flatten_diff_pair(
                    f"{path}.{key}",
                    before_dict.get(key),
                    after_dict.get(key),
                ))
            return rows
    return [(path, before, after)]


def _flatten_diff_entries(diff: dict[str, Any] | None) -> list[tuple[str, Any, Any]]:
    rows: list[tuple[str, Any, Any]] = []
    for field_key, item in (diff or {}).items():
        if not isinstance(item, dict) or "before" not in item or "after" not in item:
            continue
        rows.extend(_flatten_diff_pair(field_key, item.get("before"), item.get("after")))
    return rows


def _field_metadata(
    catalog: dict[tuple[str, str], dict[str, Any]],
    *,
    entity_type: str,
    entity_id: str | None,
    field_path: str,
) -> tuple[str, str | None, str | None, str]:
    parts = field_path.split(".")
    module = ENTITY_CATALOG_MODULES.get(entity_type)
    field_code = parts[-1]
    policy_suffix = None

    if entity_type == "sys_business_field_policy":
        module = entity_id if entity_id in {"project_archive", "project_progress"} else None
        field_code = parts[0]
        policy_suffix = parts[-1] if len(parts) > 1 else None
    elif parts[0] in {"project", "detail", "sheet_values"}:
        module = "project_progress"
        field_code = parts[1] if len(parts) > 1 else parts[0]

    metadata = catalog.get((module, field_code), {}) if module else {}
    base_label = metadata.get("field_name") or FIELD_LABEL_OVERRIDES.get(field_code) or field_code
    if base_label == field_code:
        base_label = FIELD_LABEL_OVERRIDES.get(field_code, field_code)
    if policy_suffix in POLICY_FIELD_LABELS:
        base_label = f"{base_label} / {POLICY_FIELD_LABELS[policy_suffix]}"

    group = metadata.get("group")
    enum_code = metadata.get("enum_code")
    return base_label, group, enum_code, field_code


def _enum_label_maps(db: Session | None = None) -> dict[str, dict[str, str]]:
    maps = {
        code: {str(value): label for value, label in config["items"]}
        for code, config in ENUM_REGISTRY.items()
    }
    if db is None:
        return maps

    from app.models.dict import SysDict, SysDictItem

    rows = (
        db.query(SysDict.dict_code, SysDictItem.item_value, SysDictItem.item_label)
        .join(SysDictItem, SysDictItem.dict_id == SysDict.id)
        .all()
    )
    for code, value, label in rows:
        maps.setdefault(code, {})[str(value)] = label
    return maps


def _display_value(
    value: Any,
    *,
    entity_type: str,
    field_code: str,
    enum_code: str | None,
    enum_maps: dict[str, dict[str, str]],
) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "是" if value else "否"
    if enum_code:
        mapped = enum_maps.get(enum_code, {}).get(str(value))
        if mapped is not None:
            return mapped
    system_mapped = SYSTEM_VALUE_LABELS.get((entity_type, field_code), {}).get(str(value))
    if system_mapped is not None:
        return system_mapped
    if isinstance(value, list):
        if not value:
            return "-"
        if all(not isinstance(item, (dict, list)) for item in value):
            return "、".join(str(item) for item in value)
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return str(_normalize_value(value))


def build_operation_log_diff_items(
    diff: dict[str, Any] | None,
    *,
    entity_type: str,
    entity_id: str | None = None,
    db: Session | None = None,
    catalog: dict[tuple[str, str], dict[str, Any]] | None = None,
    enum_maps: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """把原始差异转换为面向业务人员的中文字段变更项。"""
    catalog = catalog or _catalog_index()
    enum_maps = enum_maps or _enum_label_maps(db)
    items: list[dict[str, Any]] = []
    for field_key, before, after in _flatten_diff_entries(diff):
        field_label, field_group, enum_code, field_code = _field_metadata(
            catalog,
            entity_type=entity_type,
            entity_id=entity_id,
            field_path=field_key,
        )
        items.append({
            "field_key": field_key,
            "field_label": field_label,
            "field_group": field_group,
            "before": before,
            "after": after,
            "before_display": _display_value(
                before,
                entity_type=entity_type,
                field_code=field_code,
                enum_code=enum_code,
                enum_maps=enum_maps,
            ),
            "after_display": _display_value(
                after,
                entity_type=entity_type,
                field_code=field_code,
                enum_code=enum_code,
                enum_maps=enum_maps,
            ),
        })
    return items


def _json_dumps(data: Any) -> str | None:
    if data is None:
        return None
    return json.dumps(sanitize_data(data), ensure_ascii=False, default=str)


def _request_meta(request: Request | None) -> dict[str, str | None]:
    if request is None:
        return {"ip_address": None, "user_agent": None, "request_path": None, "request_method": None}
    forwarded_for = request.headers.get("x-forwarded-for")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else None)
    return {
        "ip_address": ip_address,
        "user_agent": request.headers.get("user-agent"),
        "request_path": request.url.path,
        "request_method": request.method,
    }


def _operator_name(db: Session, operator_id: int | None) -> str | None:
    if operator_id is None:
        return None
    user = db.query(SysUser).filter(SysUser.id == operator_id).first()
    if not user:
        return None
    return user.real_name or user.username


def record_operation_log(
    db: Session,
    *,
    module: str,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    entity_name: str | None = None,
    operator_id: int | None = None,
    request: Request | None = None,
    status: str = "success",
    summary: str | None = None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    error_msg: str | None = None,
    commit: bool = False,
) -> SysOperationLog:
    """写入系统操作日志。

    调用方在业务事务中记录时保持 commit=False；认证/同步等独立场景可传 commit=True。
    """
    before_clean = sanitize_data(before_data)
    after_clean = sanitize_data(after_data)
    diff_clean = diff_data(before_data, after_data) if before_data is not None or after_data is not None else None
    meta = _request_meta(request)
    resolved_summary = summary or f"{module}{action}"

    log = SysOperationLog(
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        entity_name=entity_name,
        operator_id=operator_id,
        operator_name=_operator_name(db, operator_id),
        ip_address=meta["ip_address"],
        user_agent=meta["user_agent"],
        request_path=meta["request_path"],
        request_method=meta["request_method"],
        status=status,
        summary=resolved_summary,
        error_msg=error_msg,
        before_data=_json_dumps(before_clean),
        after_data=_json_dumps(after_clean),
        diff_data=_json_dumps(diff_clean),
    )
    db.add(log)
    if commit:
        db.commit()
        db.refresh(log)
    return log


def get_operation_logs(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 15,
    module: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    operator_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    start_time: datetime.datetime | None = None,
    end_time: datetime.datetime | None = None,
) -> dict[str, Any]:
    query = db.query(SysOperationLog)

    if module:
        query = query.filter(SysOperationLog.module == module)
    if action:
        query = query.filter(SysOperationLog.action == action)
    if entity_type:
        query = query.filter(SysOperationLog.entity_type == entity_type)
    if operator_id is not None:
        query = query.filter(SysOperationLog.operator_id == operator_id)
    if status:
        query = query.filter(SysOperationLog.status == status)
    if start_time:
        query = query.filter(SysOperationLog.created_at >= start_time)
    if end_time:
        query = query.filter(SysOperationLog.created_at <= end_time)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                SysOperationLog.summary.like(like),
                SysOperationLog.entity_name.like(like),
                SysOperationLog.entity_id.like(like),
                SysOperationLog.operator_name.like(like),
                SysOperationLog.request_path.like(like),
            )
        )

    total = query.count()
    logs = (
        query.order_by(SysOperationLog.created_at.desc(), SysOperationLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    catalog = _catalog_index()
    enum_maps = _enum_label_maps(db)
    items = []
    for log in logs:
        log_data = serialize_model(log)
        try:
            raw_diff = json.loads(log.diff_data) if log.diff_data else {}
        except (TypeError, json.JSONDecodeError):
            raw_diff = {}
        log_data["diff_items"] = build_operation_log_diff_items(
            raw_diff,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            db=db,
            catalog=catalog,
            enum_maps=enum_maps,
        )
        items.append(log_data)
    return {"total": total, "items": items}
