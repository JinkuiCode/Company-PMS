"""Shared, entity-scoped reference labels without rewriting historical logs."""

ARCHIVE_REFERENCE_FIELDS = {
    'manager_id': '人员',
    'product_line_id': '产品线',
    'business_product_line_id': '产品线',
}
REFERENCE_FIELDS_BY_ENTITY = {
    'pms_project_archive': ARCHIVE_REFERENCE_FIELDS,
    'pms_feedback_report': {'author_id': '人员', 'handler_id': '人员'},
}


def _reference_id(value):
    # Match the SQL Server Integer key without coercing booleans/floats/objects.
    if type(value) is int:
        return value if 0 < value <= 2147483647 else None
    if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 10:
        number = int(value)
        return number if 0 < number <= 2147483647 else None
    return None


def reference_label_maps(db, entity_type, items):
    fields = REFERENCE_FIELDS_BY_ENTITY.get(entity_type, {})
    if db is None or not fields:
        return {}
    from app.models.user import SysUser
    from app.models.product_line import SysProductLine
    ids = {field: set() for field in fields}
    for item in items:
        field = item.get('field_key')
        if field not in ids:
            continue
        for side in ('before', 'after'):
            key = _reference_id(item.get(side))
            if key is not None:
                ids[field].add(key)
    user_ids = {key for field, kind in fields.items() if kind == '人员' for key in ids[field]}
    users = {user.id: f'{user.real_name or user.username}（{user.username}）'
             for user in db.query(SysUser).filter(SysUser.id.in_(user_ids)).all()} if user_ids else {}
    line_ids = {key for field, kind in fields.items() if kind == '产品线' for key in ids[field]}
    lines = {line.id: line.display_name for line in
             db.query(SysProductLine).filter(SysProductLine.id.in_(line_ids)).all()} if line_ids else {}
    return {field: users if kind == '人员' else lines for field, kind in fields.items()}


def fill_reference_displays(db, entity_type, items, *, current):
    """Modify response copies only; a saved human-readable name is authoritative."""
    fields = REFERENCE_FIELDS_BY_ENTITY.get(entity_type, {})
    if not fields or db is None:
        return items
    import json
    from app.services.operation_log import _display_value, MASK_VALUE
    needed = []
    for item in items:
        field = item.get('field_key')
        if field not in fields:
            continue
        for side in ('before', 'after'):
            value = item.get(side)
            if value is None or value == '' or value == MASK_VALUE:
                continue
            shown = item.get(side + '_display')
            raw = _display_value(value, entity_type='', field_code='', enum_code=None, enum_maps={})
            if current and shown is not None and shown != '' and str(shown) not in (
                    str(value), raw, json.dumps(value, ensure_ascii=False, default=str)):
                continue
            needed.append((item, field, side, value))
    # Complete event snapshots need no current master lookups at all.
    maps = reference_label_maps(db, entity_type,
        [{'field_key': field, side: value} for _, field, side, value in needed])
    for item, field, side, value in needed:
        key = _reference_id(value)
        label = maps[field].get(key)
        if label:
            display = label
            item[side + '_name_source'] = 'current' if current else 'snapshot'
        elif key is not None:
            display = (f'关联人员不存在（ID：{key}）' if fields[field] == '人员'
                       else '关联产品线不存在')
        else:
            display = '无法识别的关联值'
        item[side + '_display'] = display
    return items
