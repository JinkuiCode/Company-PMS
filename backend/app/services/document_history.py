"""Current-entity authorization plus a strictly limited business event projection."""
from sqlalchemy import String, and_, cast, or_
from fastapi import HTTPException
from app.models.operation_log import SysOperationLog
from app.services.authorization import enforce_permission
from app.services.operation_log import (
    OPERATION_ACTION_LABELS, build_operation_log_diff_items, sanitize_data, sanitize_text,
)
from app.services.operation_log_metadata import json_value
from app.services.business_resources import DOCUMENT_RESOURCES
from app.services.operation_log_time import display_time

STATUS_LABELS = {'success': '成功', 'failed': '失败', 'queued': '等待处理',
                 'running': '处理中', 'review': '待核查', 'superseded': '已被替代'}
TECHNICAL_FIELDS = {'id', 'project_code_key', 'project_name_key', 'serial_no_key',
    'updated_at', 'updated_by', 'created_at', 'created_by', 'governance_legacy',
    'password', 'password_hash', 'token', 'request_hash'}


def _authorize(db, resource, entity_id, scope):
    if resource not in DOCUMENT_RESOURCES:
        raise HTTPException(404, '业务资源不存在')
    definition = DOCUMENT_RESOURCES[resource]
    entity_type, permission, policy, label = definition.entity_type, definition.view_permission, definition.field_policy, definition.label
    enforce_permission(scope or {}, permission)
    from app.services.project import ensure_archive_access, ensure_project_access
    if resource == 'archive':
        ensure_archive_access(db, entity_id, scope)
    elif resource == 'project':
        ensure_project_access(db, entity_id, scope)
    elif resource == 'task':
        from app.models.project import PmsTask
        task = db.get(PmsTask, entity_id)
        if not task:
            raise HTTPException(404, '任务不存在或无权访问')
        ensure_project_access(db, task.project_id, scope)
    else:
        from app.services.feedback import require_report
        require_report(db, scope, entity_id)
    return entity_type, policy, label


def _query(db, resource, entity_type, entity_id):
    match = [and_(SysOperationLog.entity_type == entity_type, SysOperationLog.entity_id == str(entity_id)),
             and_(SysOperationLog.root_entity_type == entity_type, SysOperationLog.root_entity_id == str(entity_id))]
    if resource == 'archive':
        from app.models.archive_change import ArchiveChange
        changes = db.query(cast(ArchiveChange.id, String(64))).filter(ArchiveChange.archive_id == entity_id)
        match.append(and_(SysOperationLog.entity_type == 'pms_archive_change', SysOperationLog.entity_id.in_(changes)))
    elif resource == 'project':
        from app.models.project import PmsTask
        tasks = db.query(cast(PmsTask.id, String(64))).filter(PmsTask.project_id == entity_id)
        match.append(and_(SysOperationLog.entity_type == 'pms_task', SysOperationLog.entity_id.in_(tasks)))
    return db.query(SysOperationLog).filter(or_(*match))


def _allowed_fields(db, policy, entity_type):
    if policy:
        from app.services.field_policy import get_effective_field_policies
        return {item['key'] for item in get_effective_field_policies(db, policy)['items'] if item['visible']}
    from app.services.field_catalog import build_field_catalog
    module = 'task' if entity_type == 'pms_task' else 'feedback'
    return {item['field_code'] for item in build_field_catalog() if item['module'] == module}


def _project_items(db, log, allowed):
    items = json_value(log.diff_items_data)
    if not isinstance(items, list):
        after = json_value(log.after_data, {})
        if log.entity_type == 'pms_archive_change' and log.action == 'submit':
            items = json_value(after.get('differences_json'), [])
        else:
            items = build_operation_log_diff_items(json_value(log.diff_data, {}),
                entity_type=log.entity_type, entity_id=log.entity_id, db=None)
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        path = str(item.get('field_key', ''))
        parts = path.split('.')
        key = parts[1] if len(parts) > 1 and parts[0] in ('project', 'detail', 'sheet_values') else parts[0]
        key = {'business_product_line_id': 'product_line_id'}.get(key, key)
        if key in TECHNICAL_FIELDS:
            continue
        request_meta = log.entity_type == 'pms_archive_change' and log.action != 'submit' and key in ('status', 'opinion', 'reason')
        if key not in allowed and not request_meta:
            continue
        result.append({
            'field_key': path,
            'field_label': sanitize_text(str(item.get('field_label') or key)),
            'field_group': item.get('field_group'),
            **{name: sanitize_data(item.get(name)) for name in ('before', 'after')},
            **{name: sanitize_text(str(item.get(name, '-'))) for name in ('before_display', 'after_display')},
        })
    return result


def get_document_history(db, resource, entity_id, scope, *, page=1, page_size=50, action=None):
    entity_type, policy, label = _authorize(db, resource, entity_id, scope)
    base = _query(db, resource, entity_type, entity_id)
    actions = [{'value': value, 'label': OPERATION_ACTION_LABELS.get(value, '其他操作')}
               for (value,) in base.with_entities(SysOperationLog.action).distinct().order_by(SysOperationLog.action).all()]
    query = base.filter(SysOperationLog.action == action) if action else base
    total = query.count()
    logs = query.order_by(SysOperationLog.created_at.desc(), SysOperationLog.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    allowed = _allowed_fields(db, policy, entity_type)
    items = []
    for log in logs:
        fields = allowed
        if log.entity_type == 'pms_task' and resource == 'project':
            fields = _allowed_fields(db, None, 'pms_task')
        action_label = OPERATION_ACTION_LABELS.get(log.action, '其他操作')
        summary = f'{action_label}{label}'
        if log.action == 'maintain':
            after = json_value(log.after_data, {})
            reason = (after.get('maintenance') or {}).get('reason')
            if isinstance(reason, str):
                summary = f'档案维护：{sanitize_text(reason)}'
        source = '档案变更申请' if log.entity_type == 'pms_archive_change' else label
        items.append(dict(id=log.id, actor=sanitize_text(log.operator_name or '系统'),
            created_at=display_time(db, log.created_at), action=log.action, action_label=action_label,
            status=log.status, status_label=STATUS_LABELS.get(log.status, '已记录'), source=source,
            summary=summary, diff_items=_project_items(db, log, fields)))
    return {'total': total, 'items': items, 'actions': actions}
