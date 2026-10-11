"""Distinct candidates over the final report scope, not the visible page."""
import json
from datetime import date, datetime
from decimal import Decimal
from fastapi import HTTPException
from pydantic import ValidationError

from app.services.report_filters import query_fields, matches_filters


def candidate_query(query, report, field, keyword, page, page_size):
    fields = {f['field']: f for f in query_fields(report) if f['operators'] != ['reference']}
    if field not in fields or not isinstance(keyword, str) or len(keyword) > 100 or not 1 <= page <= 1000000 or not 1 <= page_size <= 200:
        raise ValueError('Unsupported candidate field or pagination')
    columns = [c for c in json.loads(query.column_filters) if c['field'] != field]
    # The original model already validated every column, including the one
    # excluded here. Do not silently discard malformed client conditions.
    copied = query.model_copy(update={'column_filters': json.dumps(columns)})
    if report.startswith('purchase'):
        copied._candidate_field = field
    return copied, fields[field]


def request_query(model, parameters, column_filters):
    try:
        values = json.loads(parameters)
        if not isinstance(values, dict):
            raise ValueError()
        if column_filters is not None:
            values['column_filters'] = column_filters
        return model.model_validate(values)
    except (ValueError, ValidationError):
        raise HTTPException(422, '候选查询参数无效，物料收发仍须填写物料、组织和完整日期范围') from None


def _public(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return value


def _result(values, spec, total, page, page_size):
    labels = {o['value']: o['label'] for o in spec.get('options', [])}
    return dict(items=[dict(value=_public(v), label='空白' if v is None else labels.get(v, str(_public(v)))) for v in values],
                total=total, page=page, page_size=page_size, has_more=page * page_size < total)


def sql_candidates(connection, base, params, spec, keyword, page, page_size):
    from app.services.purchase_reader import _rows, _like
    column = f"candidate_source.[{spec['field']}]"
    expression = (f'CAST({column} AS date)' if spec['type'] == 'date' else
                  f"NULLIF(LTRIM(RTRIM({column})),'')" if spec['type'] in {'text', 'enum'} else column)
    prefix = f'WITH candidate_source AS ({base}), distinct_values AS (SELECT DISTINCT {expression} AS value FROM candidate_source), choices AS (SELECT * FROM distinct_values'
    if keyword.strip():
        if spec.get('options'):
            selected = [o['value'] for o in spec['options'] if keyword.strip().lower() in o['label'].lower()]
            prefix += ' WHERE value IN (' + ','.join(['%s'] * len(selected)) + ')' if selected else ' WHERE 1=0'
            params = [*params, *selected]
        else:
            prefix += " WHERE LOWER(CAST(value AS nvarchar(256))) LIKE %s ESCAPE '~'"
            params = [*params, _like(keyword.strip().lower())]
    prefix += ')'
    if len(params) > 2000:
        raise ValueError('Candidate query parameter limit exceeded')
    total = _rows(connection, prefix + ' SELECT COUNT(*) AS total FROM choices', params)[0]['total']
    start = (page - 1) * page_size
    rows = _rows(connection, prefix + ', numbered AS (SELECT value,ROW_NUMBER() OVER (ORDER BY value) AS n FROM choices) SELECT value FROM numbered WHERE n>%s AND n<=%s ORDER BY n', [*params, start, start + page_size]) if total else []
    return _result([row['value'] for row in rows], spec, total, page, page_size)


def purchase_candidates(connection, query, grants, field, keyword='', page=1, page_size=50):
    from app.services.purchase_reader import PurchaseOverviewQuery, purchase_selection, overview_selection, ACCOUNTED_FIELDS
    report = 'purchase-overview' if isinstance(query, PurchaseOverviewQuery) else 'purchase'
    query, spec = candidate_query(query, report, field, keyword, page, page_size)
    selection = overview_selection if report == 'purchase-overview' else purchase_selection
    options = {'accounting': field in ACCOUNTED_FIELDS} if report == 'purchase' else {}
    with selection(connection, query, grants, **options) as (base, params):
        return sql_candidates(connection, base, params, spec, keyword, page, page_size)


def inventory_candidates(connection, query, organizations, field, keyword='', page=1, page_size=50):
    from app.services.inventory_reader import where_clause, SOURCE
    query, spec = candidate_query(query, 'inventory', field, keyword, page, page_size)
    where, params = where_clause(query, organizations)
    return sql_candidates(connection, 'SELECT v.*' + SOURCE + where, params, spec, keyword, page, page_size)


def stock_candidates(query, dataset, field, keyword='', page=1, page_size=50):
    from app.services.stock_detail_balance import running_balances
    query, spec = candidate_query(query, 'stock-detail', field, keyword, page, page_size)
    rows = sorted(dataset['rows'], key=lambda r: (r['bill_date'], r['source_order'], r['created_at'], r['bill_no'], r['bill_seq'], r['row_id']))
    selected = set()
    movements = [row for row in running_balances(rows, dataset['openings']) if matches_filters(row, query.conditions())]
    display_rows = [dict(dataset['labels'].get(key, {}), bill_date=query.start_date, bill_name='期初',
                         opening_qty=value, balance_qty=value) for key, value in dataset['openings'].items()]
    from app.services.stock_detail_engine import quantity_summary
    summary = quantity_summary(dataset)
    if summary:
        display_rows.append(summary)
    display_rows = [row for row in display_rows if matches_filters(row, query.column_conditions())]
    for row in [*movements, *display_rows]:
        value = row.get(field)
        if isinstance(value, str):
            value = value.strip() or None
        if keyword.strip() and keyword.strip().lower() not in str(_public(value) or '').lower():
            continue
        selected.add(value)
    values = sorted(selected, key=lambda v: (v is not None, v if v is not None else ''))
    start = (page - 1) * page_size
    return _result(values[start:start + page_size], spec, len(values), page, page_size)
