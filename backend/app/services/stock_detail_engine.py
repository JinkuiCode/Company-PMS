"""Combine complete organization datasets before business-row pagination."""
from decimal import Decimal, localcontext

from app.services.stock_detail_balance import derive_openings, running_balances
from app.services.stock_detail_fields import report_fields
from app.services.stock_detail_catalog import row_labels
from app.services.stock_detail_normalize import inventory_key, normalize_movement, normalize_snapshots
from app.services.stock_detail_sources import require_source_coverage
from app.services.report_filters import matches_filters


def validate_registry(rows):
    forms = []
    for row in rows:
        if str(row.get('FCLASSNAME') or '').strip() or str(row.get('FRPTTYPE') or '').strip():
            raise ValueError('金蝶报表来源已自定义，需核对后才能查询')
        form = str(row.get('FBILLFORMID') or '').strip().upper()
        if not form or form in forms:
            raise ValueError('金蝶报表来源缺失或重复')
        forms.append(form)
    if 'STK_INVBAL' not in forms:
        raise ValueError('金蝶报表缺少结存来源')
    forms.remove('STK_INVBAL')
    require_source_coverage(forms)
    return forms


def compile_organization(query, organization_id, baseline, snapshots, movements, catalog):
    """Caller must read every registered source successfully in one dataset.

    An absent snapshot dimension can be zero only after the organization-wide
    baseline was established and its complete filtered snapshot was read.
    """
    if baseline.effective_date > query.start_date:
        raise ValueError('库存基点晚于查询日期')
    if baseline.balance_type is None and snapshots:
        raise ValueError('初始化基点不得混入结存快照')
    for row in [*snapshots, *(item[3] for item in movements)]:
        if row['organization_id'] != organization_id:
            raise ValueError('库存数据超出组织范围')
    balances = normalize_snapshots(snapshots, catalog['units'])
    labels = {inventory_key(row, catalog['units'][row['material_id']]['unit_id']): row_labels(row, catalog)
              for row in snapshots}
    history, period, identities = [], [], set()
    for form, side, bill_name, raw in movements:
        row = normalize_movement(raw, form, side, catalog['units'][raw['material_id']], row_labels(raw, catalog), bill_name)
        if row['row_id'] in identities:
            raise ValueError('来源流水重复，禁止重复累计')
        identities.add(row['row_id'])
        if not baseline.effective_date <= row['bill_date'] <= query.end_date:
            raise ValueError('库存流水超出完整补算区间')
        key = row['inventory_key']
        balances.setdefault(key, Decimal(0))
        labels.setdefault(key, row_labels(raw, catalog))
        (history if row['bill_date'] < query.start_date else period).append(row)
    openings = derive_openings(baseline.effective_date, query.start_date, balances, history)
    return {'rows': period, 'openings': openings, 'labels': labels}


def export_rows(dataset, start_date, *, conditions=()):
    fields = {field['key'] for field in report_fields()}
    for key, value in dataset['openings'].items():
        row = dict(dataset['labels'].get(key, {}), bill_date=start_date, bill_name='期初',
                   opening_qty=value, balance_qty=value)
        yield {field: row.get(field) for field in fields}
    ordered = sorted(dataset['rows'], key=lambda row: (row['bill_date'], row['source_order'],
        row['created_at'], row['bill_no'], row['bill_seq'], row['row_id']))
    for row in running_balances(ordered, dataset['openings']):
        if matches_filters(row, conditions):
            yield {field: row.get(field) for field in fields}


def quantity_summary(dataset):
    if len(dataset['openings']) != 1:
        return None
    key, opening = next(iter(dataset['openings'].items()))
    with localcontext() as context:
        context.prec = 50
        income = sum((row['income_qty'] for row in dataset['rows']), Decimal(0))
        issue = sum((row['issue_qty'] for row in dataset['rows']), Decimal(0))
        balance = opening + income - issue
    return {**dataset['labels'].get(key, {}), 'opening_qty': opening,
            'income_qty': income, 'issue_qty': issue, 'balance_qty': balance}
