"""Typed report allowlists shared by request validation, SQL and row filtering."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import re

from app.services.purchase_fields import report_fields as purchase_fields, DOCUMENT_STATUSES, PROGRESS_LABELS
from app.services.stock_detail_fields import report_fields as stock_fields

EMPTY = ('isEmpty', 'notEmpty')
COMPARISONS = {'equals': '=', 'notEquals': '<>', 'greaterThan': '>',
               'greaterOrEqual': '>=', 'lessThan': '<', 'lessOrEqual': '<='}
OPERATORS = {
    'text': ('contains', 'notContains', 'startsWith', 'endsWith', 'equals', 'notEquals', *EMPTY),
    'number': (*COMPARISONS, 'between', *EMPTY),
    'date': (*COMPARISONS, 'between', *EMPTY),
    'enum': ('equals', 'notEquals', *EMPTY),
}
STOCK_FILTER_SEMANTICS = {'movements': 'filtered_after_running_balance',
                          'openings': 'full_scope', 'summary': 'full_scope',
                          'total': 'filtered_movements'}


def filter_fields(report):
    if report == 'purchase':
        # Progress is filtered after full accounting; the other fields belong to
        # the request source. Derived quantities and PMS enrichment stay excluded.
        supported = {'project_code', 'material_code', 'material_name', 'specification',
                     'unit_name', 'bill_no', 'line_no', 'application_date',
                     'document_status', 'close_status', 'requested', 'approved', 'progress'}
        fields = [f for f in purchase_fields() if f['key'] in supported]
        enums = {'document_status': DOCUMENT_STATUSES, 'close_status': {'A': '未关闭', 'B': '已关闭'},
                 'progress': PROGRESS_LABELS}
    elif report == 'stock-detail':
        fields = stock_fields()
        enums = {}
    else:
        raise ValueError('Unknown report')
    result = []
    for field in fields:
        key = field['key']
        kind = field.get('value_type', field.get('type'))
        kind = 'number' if kind == 'decimal' else kind
        kind = 'enum' if key in enums else kind
        item = dict(field=key, label=field['label'], type=kind, operators=list(OPERATORS[kind]))
        if report == 'purchase' and key == 'progress':
            item['operators'] = ['equals', 'notEquals']
        if key in enums:
            item['options'] = [dict(value=value, label=label) for value, label in enums[key].items()]
        result.append(item)
    return result


@dataclass(frozen=True)
class Condition:
    field: str
    operator: str
    kind: str
    value: object = None
    valueEnd: object = None


def _value(value, spec):
    kind = spec['type']
    if type(value) not in (str, int, float) or not str(value).strip():
        raise ValueError('Missing or invalid filter value')
    if kind == 'number':
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            raise ValueError('Invalid filter number') from None
        if (not number.is_finite() or number.copy_abs() > Decimal('999999999999')
                or number.as_tuple().exponent < -28 or len(number.as_tuple().digits) > 38):
            raise ValueError('Filter number out of range')
        return number
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError('Invalid filter text')
    if kind == 'date':
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('Filter date must be YYYY-MM-DD')
        return date.fromisoformat(value)
    if kind == 'enum' and value not in {option['value'] for option in spec['options']}:
        raise ValueError('Unknown filter option')
    return value


def parse_filters(raw, report):
    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError('Invalid filters JSON') from None
    if not isinstance(values, list) or len(values) > 20:
        raise ValueError('Filters must be a list of at most 20 conditions')
    fields = {f['field']: f for f in filter_fields(report)}
    conditions = []
    for item in values:
        if not isinstance(item, dict) or set(item) - {'field', 'operator', 'value', 'valueEnd'}:
            raise ValueError('Invalid filter condition')
        field, operator = item.get('field'), item.get('operator')
        if not isinstance(field, str) or field not in fields:
            raise ValueError('Unknown filter field')
        spec = fields[field]
        if not isinstance(operator, str) or operator not in spec['operators']:
            raise ValueError('Invalid operator for filter type')
        value, end = item.get('value'), item.get('valueEnd')
        if operator != 'between' and end not in (None, ''):
            raise ValueError('Unexpected filter range end')
        if operator in EMPTY:
            if value not in (None, ''):
                raise ValueError('Empty operator does not accept a value')
            value = end = None
        else:
            value = _value(value, spec)
            if operator == 'between':
                end = _value(end, spec)
                if value > end:
                    raise ValueError('Reversed filter range')
        conditions.append(Condition(field, operator, spec['type'], value, end))
    return conditions


def sql_conditions(conditions):
    parts, params = [], []
    for condition in conditions:
        # Conditions come exclusively from the fixed report allowlist above.
        column = f'filter_source.[{condition.field}]'
        if condition.kind == 'date':
            column = f'CAST({column} AS date)'
        op, value = condition.operator, condition.value
        if op in EMPTY:
            if condition.kind in ('text', 'enum'):
                parts.append(f"({column} IS NULL OR {column}='')" if op == 'isEmpty'
                             else f"({column} IS NOT NULL AND {column}<>'')")
            else:
                parts.append(f'{column} IS ' + ('NULL' if op == 'isEmpty' else 'NOT NULL'))
        elif op in ('contains', 'notContains', 'startsWith', 'endsWith'):
            for char in ('~', '%', '_', '['):
                value = value.replace(char, '~' + char)
            pattern = ('' if op == 'startsWith' else '%') + value + ('' if op == 'endsWith' else '%')
            parts.append(f"{column} {'NOT LIKE' if op == 'notContains' else 'LIKE'} %s ESCAPE '~'")
            params.append(pattern)
        elif op == 'between':
            parts.append(f'{column} BETWEEN %s AND %s')
            params.extend([value, condition.valueEnd])
        else:
            parts.append(f'{column}{COMPARISONS[op]}%s')
            params.append(value)
    return ' AND '.join(parts), params


def matches_filters(row, conditions):
    for condition in conditions:
        value, target, op = row.get(condition.field), condition.value, condition.operator
        empty = value is None or (condition.kind in ('text', 'enum') and value == '')
        if op in EMPTY:
            if empty != (op == 'isEmpty'):
                return False
            continue
        # NULL never matches a comparison, including negative comparisons.
        if value is None:
            return False
        if condition.kind == 'number':
            value = Decimal(str(value))
        elif condition.kind == 'date':
            value = value.date() if isinstance(value, datetime) else value
            value = date.fromisoformat(value) if isinstance(value, str) else value
        if op == 'contains': matched = target in value
        elif op == 'notContains': matched = target not in value
        elif op == 'startsWith': matched = value.startswith(target)
        elif op == 'endsWith': matched = value.endswith(target)
        elif op == 'equals': matched = value == target
        elif op == 'notEquals': matched = value != target
        elif op == 'greaterThan': matched = value > target
        elif op == 'greaterOrEqual': matched = value >= target
        elif op == 'lessThan': matched = value < target
        elif op == 'lessOrEqual': matched = value <= target
        elif op == 'between': matched = target <= value <= condition.valueEnd
        else: raise ValueError('Invalid filter operator')
        if not matched:
            return False
    return True
