"""Stable document ownership and event-time field display snapshots."""
import json


def json_value(value, fallback=None):
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value) if value else fallback
    except (TypeError, ValueError):
        return fallback


def resolve_log_root(db, entity_type, entity_id, before=None, after=None):
    snapshot = {**(before or {}), **(after or {})}
    parent = None
    if entity_type == 'pms_archive_change':
        parent = snapshot.get('archive_id')
        if parent is None and entity_id is not None:
            from app.models.archive_change import ArchiveChange
            row = db.get(ArchiveChange, int(entity_id))
            parent = row.archive_id if row else None
        if parent is not None:
            return 'pms_project_archive', str(parent)
    elif entity_type in ('pms_task', 'pms_progress_log'):
        parent = snapshot.get('project_id')
        if parent is None and entity_type == 'pms_task' and entity_id is not None:
            from app.models.project import PmsTask
            row = db.get(PmsTask, int(entity_id))
            parent = row.project_id if row else None
        if parent is not None:
            return 'pms_project', str(parent)
    elif entity_type in ('pms_feedback_followup', 'pms_feedback_attachment', 'pms_feedback_notification'):
        parent = snapshot.get('report_id')
        if parent is not None:
            return 'pms_feedback_report', str(parent)
    return entity_type, str(entity_id) if entity_id is not None else None


def snapshot_display_items(db, entity_type, entity_id, action, diff, after=None):
    from app.services.operation_log import build_operation_log_diff_items, sanitize_data
    if entity_type == 'security_request': return []
    if entity_type == 'pms_archive_change' and action == 'submit':
        requested = json_value((after or {}).get('differences_json'), [])
        if isinstance(requested, list):
            # Keep metadata field names; sanitize only business values.
            return [{**item, **{key: sanitize_data(item.get(key)) for key in
                    ('before', 'after', 'before_display', 'after_display')}}
                    for item in requested if isinstance(item, dict) and 'field_key' in item]
    return build_operation_log_diff_items(diff, entity_type=entity_type, entity_id=entity_id, db=db)
