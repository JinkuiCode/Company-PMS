"""Normalize verified source rows without carrying private ERP columns forward."""
from datetime import date, datetime
from decimal import Decimal, localcontext
from app.services.stock_detail_balance import InventoryKey, quantity, stock_quantity
from app.services.stock_detail_fields import report_fields


def _identity(value, *, required=False):
    if value is None and not required:
        return 0
    if type(value) is not int or value < (1 if required else 0):
        raise ValueError('库存维度内码无效')
    return value


def _day(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if type(value) is not date:
        raise ValueError('库存日期无效')
    return value


def inventory_key(row, unit_id):
    values = {key: _identity(row.get(key), required=True) for key in
              ('organization_id', 'material_id', 'stock_id', 'stock_status_id')}
    values.update({key: _identity(row.get(key)) for key in
                   ('owner_id', 'keeper_id', 'stock_location_id', 'auxiliary_property_id', 'bom_id')})
    values.update({key: str(row.get(key) or '').strip() for key in
                   ('owner_type', 'keeper_type', 'mto_no', 'lot_no')})
    values.update({key: _day(row.get(key)) for key in ('produce_date', 'expiry_date')})
    return InventoryKey(**values, unit_id=_identity(unit_id, required=True))


def _convert(value, unit):
    if type(value) is int:
        value = Decimal(value)
    return stock_quantity(value, unit['numerator'], unit['denominator'], unit['precision'])


def normalize_movement(row, form_id, side, unit, labels, bill_name):
    identity = f"{form_id}:{side}:{_identity(row['bill_id'], required=True)}:{_identity(row['entry_id'], required=True)}"
    day = _day(row['bill_date'])
    created = row['created_at']
    if day is None or not isinstance(created, datetime) or not str(row['bill_no']).strip():
        raise ValueError('库存流水时间或单号无效')
    descriptive = {field['key'] for field in report_fields()} - {
        'opening_qty', 'income_qty', 'issue_qty', 'balance_qty', 'bill_date', 'bill_name', 'bill_no', 'bill_seq'}
    return {**{key: labels.get(key) for key in descriptive},
        'row_id': identity, 'inventory_key': inventory_key(row, unit['unit_id']),
        'source_order': 0, 'created_at': created, 'bill_date': day,
        'bill_no': row['bill_no'], 'bill_seq': _identity(row['bill_seq']), 'bill_name': bill_name,
        'opening_qty': None, 'income_qty': _convert(row['base_income_qty'], unit),
        'issue_qty': _convert(row['base_issue_qty'], unit)}


def normalize_snapshots(rows, units):
    totals, identities, key_units = {}, set(), {}
    for row in rows:
        identity = _identity(row['snapshot_id'], required=True)
        if identity in identities:
            raise ValueError('结存映射重复，禁止重复累计')
        identities.add(identity)
        for field in ('owner', 'keeper', 'bom', 'lot'):
            target = row.get('lot_no') if field == 'lot' else row.get(field + '_id')
            if row.get(field + '_master_id') and not target:
                raise ValueError('结存基础资料映射缺失')
        unit = units.get(row['material_id'])
        if unit is None:
            raise ValueError('库存单位映射缺失')
        key = inventory_key(row, unit['unit_id'])
        with localcontext() as context:
            context.prec = 50
            totals[key] = totals.get(key, Decimal(0)) + quantity(row['base_qty'])
        key_units[key] = unit
    return {key: _convert(value, key_units[key]) for key, value in totals.items()}
