"""统一操作日志服务。"""
from __future__ import annotations

import datetime
import decimal
import json
import re
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


def sanitize_text(value: str) -> str:
    value = re.sub(r'(?i)\bBearer\s+[^\s,;"\']+', 'Bearer ***', value)
    value = re.sub(r'(?i)((?:password|password_hash|app_?secret|secret|token|api_?key|sign|密码)\s*[=:：]\s*)(?:"[^"]*"|\'[^\']*\'|[^\s,;&]+)', r'\1***', value)
    return re.sub(r'(https?://)[^/@\s]+:[^/@\s]+@', r'\1***@', value)

ENTITY_CATALOG_MODULES = {
    'pms_business_notice': 'business_notice', 'pms_business_notice_mail': 'business_notice_mail',
    'pms_form_draft': 'form_draft',
    'pms_release': 'release', 'pms_release_notice': 'release_notice', 'pms_release_mail': 'release_mail',
    "pms_feedback_report": "feedback",
    "pms_feedback_followup": "feedback_followup",
    "pms_feedback_attachment": "feedback_attachment",
    "pms_feedback_notification": "feedback_notification",
    "sys_product_line": "product_line",
    "sys_role_product_line": "role_product_line",
    "sys_parameter": "parameter",
    "sys_user": "user",
    "sys_role": "role",
    "sys_menu": "permission_menu",
    "sys_dept": "department",
    'pms_archive_change': 'archive_change',
    "sys_enum_item": "enum_item",
    "pms_project": "project_progress",
    "pms_project_archive": "project_archive",
    "pms_task": "task",
}

FIELD_LABEL_OVERRIDES = {
    "initial_release": "首次启用升级通知",
    "initial_release_reason": "首次发布说明",
    "configured": "已配置",
    "credentials_changed": "凭据已变更",
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
    "product_category_ids": "产品类别范围",
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
    ('pms_form_draft','status'): {'active':'待填写','used':'已转档','deleted':'已删除'},
    ('pms_form_draft','resource'): {'archive-create':'新增项目档案'},
    ("sys_user", "status"): {"0": "禁用", "1": "启用"},
    ("sys_role", "status"): {"0": "禁用", "1": "启用"},
    ("sys_dept", "status"): {"0": "禁用", "1": "启用"},
    ("sys_menu", "status"): {"0": "禁用", "1": "启用"},
    ("sys_menu", "visible"): {"0": "隐藏", "1": "显示"},
    ("sys_menu", "menu_type"): {"M": "目录", "C": "页面", "B": "按钮权限"},
    ("sys_enum_item", "status"): {"0": "禁用", "1": "启用"},
    ("pms_project_archive", "erp_synced"): {"0": "否", "1": "是"},
    ("pms_project_archive", "is_enabled"): {"0": "禁用", "1": "启用"},
    ("pms_project_archive", "erp_sync_policy"): {
        'manual': '仅手动同步', 'auto': '自动同步', 'conditional': '条件同步'},
    ("pms_project_archive", "data_origin"): {
        'pms': 'PMS新建', 'kingdee_initial': '金蝶期初', 'erp': '金蝶历史档案', 'offline_initial': '线下期初'},
    ('pms_business_notice', 'event'): {'submitted':'提交待审批','approved':'审批通过','rejected':'审批退回'},
    ('pms_business_notice_mail', 'status'): {'pending':'待投递','waiting':'等待配置','processing':'投递中','accepted':'服务器已接受','failed':'投递失败','unknown':'结果未知','suppressed':'停止投递'},
    ('pms_release_mail', 'status'): {
        'pending': '待投递', 'waiting': '等待配置', 'processing': '投递中',
        'accepted': '服务器已接受', 'failed': '投递失败', 'unknown': '结果未知'},
    ('pms_feedback_notification', 'audience'): {'admins': '系统管理员', 'author': '提报人'},
}


def _system_value_labels(entity_type, field_code):
    if (entity_type, field_code) in (('pms_project_archive', 'erp_sync_status'), ('erp_sync_task', 'status')):
        from app.services.erp_queue import STATUS_LABELS
        return {**STATUS_LABELS, 'pending': '同步中', 'historical': '金蝶历史档案'}
    if entity_type == 'pms_feedback_notification' and field_code == 'status':
        from app.services.feedback import MAIL_LABELS
        return MAIL_LABELS
    return SYSTEM_VALUE_LABELS.get((entity_type, field_code), {})


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
    if isinstance(data, str):
        return sanitize_text(data)
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

    # The persisted archive FK and its public field share the catalog's business name.
    catalog_field = ('product_line_id' if entity_type == 'pms_project_archive'
                     and field_code == 'business_product_line_id' else field_code)
    metadata = catalog.get((module, catalog_field), {}) if module else {}
    base_label = metadata.get("field_name") or FIELD_LABEL_OVERRIDES.get(field_code) or field_code
    if base_label == field_code:
        base_label = FIELD_LABEL_OVERRIDES.get(field_code, field_code)
    if policy_suffix in POLICY_FIELD_LABELS:
        base_label = f"{base_label} / {POLICY_FIELD_LABELS[policy_suffix]}"

    group = metadata.get("group")
    enum_code = metadata.get("enum_code")
    if not enum_code and metadata.get('source_type') == 'system_fixed':
        enum_code = next((code for code, definition in ENUM_REGISTRY.items()
            if definition['table_name'] == metadata.get('storage_table')
            and definition['field_name'] == metadata.get('storage_column')), None)
    if policy_suffix:
        enum_code = None  # Rule flags describe the field, not its business enum value.
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
        .outerjoin(SysDictItem, SysDictItem.dict_id == SysDict.id)
        .all()
    )
    seen = set()
    for code, value, label in rows:
        if code not in seen and ENUM_REGISTRY.get(code, {}).get('mode') == 'configurable':
            maps[code] = {}  # Actual configurable definitions supersede initial seed options.
        seen.add(code)
        if value is not None:
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
    if value == MASK_VALUE:
        return MASK_VALUE
    if isinstance(value, bool):
        return "是" if value else "否"
    system_labels = _system_value_labels(entity_type, field_code)
    if isinstance(value, list):
        if not value:
            return '-'
        if enum_code or system_labels:
            return '、'.join(_display_value(item, entity_type=entity_type,
                field_code=field_code, enum_code=enum_code, enum_maps=enum_maps) for item in value)
    if enum_code and field_code == 'product_category_ids' and isinstance(value, str) and ',' in value:
        return '、'.join(_display_value(item.strip(), entity_type=entity_type,
            field_code=field_code, enum_code=enum_code, enum_maps=enum_maps) for item in value.split(',') if item.strip())
    if system_labels:
        return system_labels.get(str(value), f'未识别选项（编码：{value}）')
    if enum_code:
        mapped = enum_maps.get(enum_code, {}).get(str(value))
        if mapped is not None:
            return mapped
        return f'未识别选项（编码：{value}）'
    if isinstance(value, list):
        if not value:
            return "-"
        if all(not isinstance(item, (dict, list)) for item in value):
            return "、".join(str(item) for item in value)
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return str(_normalize_value(value))


def _event_contexts(diff, before_data=None, after_data=None):
    before = {**(after_data or {}), **(before_data or {})}
    after = {**(before_data or {}), **(after_data or {})}
    for key, pair in (diff or {}).items():
        if isinstance(pair, dict):
            if 'before' in pair: before[key] = pair['before']
            if 'after' in pair: after[key] = pair['after']
    return before, after


def _value_enum_code(entity_type, field_code, enum_code, context):
    if entity_type == 'pms_feedback_report' and field_code == 'category_id':
        return {'1': 'feedback_issue_category', '2': 'feedback_request_category'}.get(
            str(context.get('type_id')), 'feedback_category_unknown')
    return enum_code


def build_operation_log_diff_items(
    diff: dict[str, Any] | None,
    *,
    entity_type: str,
    entity_id: str | None = None,
    db: Session | None = None,
    catalog: dict[tuple[str, str], dict[str, Any]] | None = None,
    enum_maps: dict[str, dict[str, str]] | None = None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """把原始差异转换为面向业务人员的中文字段变更项。"""
    catalog = _catalog_index() if catalog is None else catalog
    enum_maps = _enum_label_maps(db) if enum_maps is None else enum_maps
    before_context, after_context = _event_contexts(diff, before_data, after_data)
    diff = dict(diff or {})
    if (entity_type == 'pms_feedback_report'
            and before_context.get('type_id') != after_context.get('type_id')
            and ('category_id' in before_context or 'category_id' in after_context)):
        # The same numeric category can mean different things after a type change.
        diff.setdefault('category_id', {'before': before_context.get('category_id'),
                                        'after': after_context.get('category_id')})
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
                enum_code=_value_enum_code(entity_type, field_code, enum_code, before_context),
                enum_maps=enum_maps,
            ),
            "after_display": _display_value(
                after,
                entity_type=entity_type,
                field_code=field_code,
                enum_code=_value_enum_code(entity_type, field_code, enum_code, after_context),
                enum_maps=enum_maps,
            ),
        })
    from app.services.operation_log_references import fill_reference_displays
    return fill_reference_displays(db, entity_type, items, current=False)


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
        "user_agent": sanitize_text(request.headers.get("user-agent", ''))[:512],
        "request_path": sanitize_text(getattr(request.scope.get('route'), 'path', '[未匹配路由]'))[:256],
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
) -> SysOperationLog | None:
    """写入系统操作日志。

    调用方在业务事务中记录时保持 commit=False；认证/同步等独立场景可传 commit=True。
    """
    before_clean = sanitize_data(before_data)
    after_clean = sanitize_data(after_data)
    diff_clean = diff_data(before_data, after_data) if before_data is not None or after_data is not None else None
    if action == 'update' and status == 'success' and before_data is not None and after_data is not None and not diff_clean:
        return None
    from app.services.operation_log_metadata import resolve_log_root, snapshot_display_items
    root_type, root_id = resolve_log_root(db, entity_type, entity_id, before_clean, after_clean)
    display_items = snapshot_display_items(db, entity_type, str(entity_id) if entity_id is not None else None,
        action, diff_clean, after_clean, before_clean)
    for item in display_items:
        for name in ('field_label', 'field_group', 'before_display', 'after_display'):
            if isinstance(item.get(name), str): item[name] = sanitize_text(item[name])
        for name in ('before', 'after'): item[name] = sanitize_data(item.get(name))
    meta = _request_meta(request)
    resolved_summary = summary or f"{module}{action}"

    log = SysOperationLog(
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        entity_name=sanitize_text(entity_name)[:256] if entity_name else None,
        root_entity_type=root_type,
        root_entity_id=root_id,
        operator_id=operator_id,
        operator_name=sanitize_text(_operator_name(db, operator_id) or '')[:64] or None,
        ip_address=meta["ip_address"],
        user_agent=meta["user_agent"],
        request_path=meta["request_path"],
        request_method=meta["request_method"],
        status=status,
        summary=sanitize_text(resolved_summary)[:512],
        error_msg=sanitize_text(error_msg)[:1024] if error_msg else None,
        before_data=_json_dumps(before_clean),
        after_data=_json_dumps(after_clean),
        diff_data=_json_dumps(diff_clean),
        diff_items_data=json.dumps(display_items, ensure_ascii=False, default=str),
    )
    db.add(log)
    if commit:
        db.commit()
        db.refresh(log)
        if status == 'failed' and request is not None:
            request.state.audit_failure_recorded = True
    return log


OPERATION_ACTION_LABELS = {
    'draft_save': '保存草稿', 'draft_delete': '删除草稿', 'draft_convert': '草稿转档',
    'verify': '核查结果', 'change_password': '修改密码', 'reset_password': '重置密码',
    'reset': '恢复设置', 'sso_url_generate': '生成登录链接',
    'publish': '发布版本', 'read': '确认已读', 'mail_delivery': '邮件投递',
    'denied': '访问被拒绝', 'failed_write': '写入失败',
    'maintain': '档案维护', 'submit': '提交变更', 'approve': '审批通过', 'reject': '退回',
    'withdraw': '撤回', 'import': '导入', 'export': '导出', 'retry': '重试',
    'create': '新增', 'update': '编辑', 'delete': '删除', 'login': '登录',
    'auto_login': '自动登录', 'logout': '退出', 'sso_login': 'SSO 登录',
    'sync': 'ERP 同步', 'batch_sync': '批量同步', 'sso_verify': 'SSO Token',
    'sso_url_login': 'SSO URL', 'oa_login': 'OA 登录', 'oa_password_login': 'OA 账号登录',
}
OPERATION_QUERY_LABELS = {'action': OPERATION_ACTION_LABELS, 'status': {'success': '成功', 'failed': '失败'}}


def operation_log_columns(db=None):
    columns = {name: (getattr(SysOperationLog, name), 'text') for name in (
        'entity_type', 'entity_name', 'operator_name', 'ip_address', 'summary', 'request_path',
    )}
    columns.update({name: (getattr(SysOperationLog, name), 'enum_text') for name in ('module', 'action', 'status')})
    from app.services.operation_log_time import date_column
    columns['created_at'] = (date_column(db, SysOperationLog.created_at), 'date')
    return columns


def _operation_log_query(
    db: Session,
    *,
    module: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    operator_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    start_time: datetime.datetime | None = None,
    end_time: datetime.datetime | None = None,
):
    from app.services.operation_log_time import query_time
    start_time, end_time = query_time(db, start_time), query_time(db, end_time)
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

    return query


def get_operation_log_column_values(db, *, field, keyword='', page=1, page_size=100,
                                    filters=None, column_filters=None, base_keyword=None, **base):
    from app.services.system_list_query import apply_system_list_query, system_column_values
    columns = operation_log_columns(db)
    query = _operation_log_query(db, keyword=base_keyword, **base)
    query = apply_system_list_query(query, columns, filters, column_filters,
        labels=OPERATION_QUERY_LABELS, exclude_field=field)
    return system_column_values(query, columns, field, keyword=keyword, page=page, page_size=page_size,
        labels=OPERATION_QUERY_LABELS)


def get_operation_logs(db: Session, *, page=1, page_size=15, filters=None, column_filters=None, **base) -> dict[str, Any]:
    from app.services.system_list_query import apply_system_list_query
    query = apply_system_list_query(_operation_log_query(db, **base), operation_log_columns(db),
        filters, column_filters, labels=OPERATION_QUERY_LABELS)
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
        from app.services.operation_log_time import display_time
        shown_time = display_time(db, log.created_at)
        log_data['created_at'] = shown_time.isoformat() if shown_time is not None else None
        for name in ('summary', 'error_msg', 'entity_name', 'operator_name', 'user_agent', 'request_path'):
            if isinstance(log_data.get(name), str):
                log_data[name] = sanitize_text(log_data[name])
        for name in ('before_data', 'after_data', 'diff_data'):
            from app.services.operation_log_metadata import json_value
            log_data[name] = _json_dumps(json_value(log_data.get(name)))
        from app.services.operation_log_metadata import resolve_display_items
        log_data['diff_items'] = resolve_display_items(db, log, catalog=catalog, enum_maps=enum_maps)
        # Metadata keys stay intact; all user-supplied values remain sanitized.
        for item in log_data['diff_items']:
            for name in ('field_label', 'field_group', 'before_display', 'after_display'):
                if isinstance(item.get(name), str): item[name] = sanitize_text(item[name])
            for name in ('before', 'after'): item[name] = sanitize_data(item.get(name))
        log_data.pop('diff_items_data', None)
        items.append(log_data)
    return {"total": total, "items": items, "query_version": 2,
            'actions': [{'value': value, 'label': label} for value, label in OPERATION_ACTION_LABELS.items()],
            'modules': [{'value': value, 'label': value} for (value,) in db.query(SysOperationLog.module).distinct().order_by(SysOperationLog.module)]}
