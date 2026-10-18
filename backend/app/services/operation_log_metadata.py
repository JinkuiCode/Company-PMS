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


def snapshot_display_items(db, entity_type, entity_id, action, diff, after=None, before=None):
    from app.services.operation_log import build_operation_log_diff_items, sanitize_data
    if entity_type == 'security_request': return []
    if entity_type == 'pms_archive_change' and action == 'submit':
        requested = json_value((after or {}).get('differences_json'), [])
        if isinstance(requested, list):
            # Keep metadata field names; sanitize only business values.
            return [{**item, **{key: sanitize_data(item.get(key)) for key in
                    ('before', 'after', 'before_display', 'after_display')}}
                    for item in requested if isinstance(item, dict) and 'field_key' in item]
    return build_operation_log_diff_items(diff, entity_type=entity_type, entity_id=entity_id,
        db=db, before_data=before, after_data=after)


def resolve_display_items(db, log, *, catalog=None, enum_maps=None):
    """Preserve event labels and explain legacy codes without rewriting storage.

    A current reference name carries separate provenance for on-demand explanation.
    """
    from app.services.operation_log import (
        _catalog_index, _enum_label_maps, _event_contexts, _field_metadata,
        _value_enum_code, _display_value, _system_value_labels,
        build_operation_log_diff_items,
    )
    if log.entity_type == 'security_request':
        return []
    catalog = _catalog_index() if catalog is None else catalog
    enum_maps = _enum_label_maps(db) if enum_maps is None else enum_maps
    before = json_value(log.before_data, {})
    after = json_value(log.after_data, {})
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    diff = json_value(log.diff_data, {})
    diff = diff if isinstance(diff, dict) else {}
    saved = json_value(log.diff_items_data)
    entity_type = log.entity_type
    if entity_type == 'pms_archive_change' and log.action == 'submit':
        entity_type = 'pms_project_archive'
        if not isinstance(saved, list):
            saved = json_value(after.get('differences_json'), [])
    if not isinstance(saved, list):
        saved = build_operation_log_diff_items(diff, entity_type=entity_type,
            entity_id=log.entity_id, catalog=catalog, enum_maps=enum_maps,
            before_data=before, after_data=after)

    contexts = dict(zip(('before', 'after'), _event_contexts(diff, before, after)))
    result = []
    for source in saved:
        if not isinstance(source, dict) or not isinstance(source.get('field_key'), str):
            continue
        item = dict(source)
        label, _, enum_code, field = _field_metadata(catalog, entity_type=entity_type,
            entity_id=log.entity_id, field_path=item['field_key'])
        if entity_type == 'pms_project_archive' and item['field_key'] in ('product_line_id', 'business_product_line_id'):
            item['field_label'] = label
        for side in ('before', 'after'):
            code = _value_enum_code(entity_type, field, enum_code, contexts[side])
            if not code and not _system_value_labels(entity_type, field):
                continue
            value = item.get(side)
            shown = item.get(side + '_display')
            raw = _display_value(value, entity_type='', field_code='', enum_code=None, enum_maps={})
            # A real event-time label is authoritative, including a later-disabled label.
            if shown is None or shown == '' or str(shown) in (str(value), raw, json.dumps(value, ensure_ascii=False, default=str)):
                item[side + '_display'] = _display_value(value, entity_type=entity_type,
                    field_code=field, enum_code=code, enum_maps=enum_maps)
        result.append(item)
    if (entity_type == 'pms_feedback_report'
            and contexts['before'].get('type_id') != contexts['after'].get('type_id')
            and not any(item['field_key'] == 'category_id' for item in result)):
        semantic = build_operation_log_diff_items(diff, entity_type=entity_type,
            entity_id=log.entity_id, catalog=catalog, enum_maps=enum_maps,
            before_data=before, after_data=after)
        result.extend(item for item in semantic if item['field_key'] == 'category_id')
    from app.services.operation_log_references import fill_reference_displays
    from app.services.archive_log_presentation import order_archive_log_items
    return order_archive_log_items(entity_type, fill_reference_displays(db, entity_type, result, current=True))
