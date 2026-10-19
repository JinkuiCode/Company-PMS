"""Approved archive relationships, keyed by stable source/enum identities.

Unclassified options and product lines remain unrestricted until separately
confirmed. This is validation metadata, never a permission grant.
"""
from app.models.product_line import SysProductLine
from app.services.business_data_scope import has_all_business_data

ORGANIZATION_PROFILES = {200292: 'bench8', 499413: 'bench12', 4146325: 'single'}
PROFILES = {
    'bench8': {'machine_model': (5, 6, 7, 8, 10, 11, 12), 'equipment_series': (6, 7, 8, 9, 10, 11)},
    'bench12': {'machine_model': (2, 3, 4), 'equipment_series': (12, 13)},
    'single': {'machine_model': (1, 9, 13, 15), 'equipment_series': (14, 15)},
}
LABELS = {'machine_model': '机型', 'equipment_series': '设备系列'}


def _profile(line):
    return ORGANIZATION_PROFILES.get(line.organization_id) if line and line.source_key == 'kingdee' else None


def linkage_metadata(db, context=None):
    lines = db.query(SysProductLine)
    if not context or not has_all_business_data(context):
        lines = lines.filter(SysProductLine.id.in_((context or {}).get('product_line_ids') or []))
    return {
        'line_profiles': {str(line.id): profile for line in lines.all() if (profile := _profile(line))},
        'profiles': {key: {field: list(values) for field, values in fields.items()} for key, fields in PROFILES.items()},
    }


def linkage_errors(db, current, updates, *, is_create=False):
    merged = {**current, **updates}
    parent_changed = is_create or merged.get('product_line_id') != current.get('product_line_id')
    fields = [key for key in LABELS if parent_changed or (key in updates and updates[key] != current.get(key))]
    if not fields or not merged.get('product_line_id'):
        return []
    profile = _profile(db.get(SysProductLine, merged['product_line_id']))
    if not profile:
        return []
    errors = []
    for field in fields:
        value = merged.get(field)
        assigned = {v for group in PROFILES.values() for v in group[field]}
        if value in assigned and value not in PROFILES[profile][field]:
            errors.append({'field_key': field, 'message': f'{LABELS[field]}与产品线不匹配，请重新选择'})
    return errors
