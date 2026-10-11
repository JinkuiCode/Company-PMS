"""Submitted business-row queries using the shared v2 validator and matcher."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import cmp_to_key
from sqlalchemy import literal_column
from app.services.list_query import invalid_query, query_items
from app.services.query_conditions import build_query_clause, scalar
from app.services.report_filters import Condition, matches_filters

CHARACTER_OPERATORS = {'contains', 'notContains', 'startsWith', 'endsWith'}


def _condition(item, fields, *, membership=False, mode='condition'):
    try:
        return _validated_condition(item, fields, membership=membership, mode=mode)
    except (ValueError, TypeError, InvalidOperation):
        raise invalid_query() from None


def _validated_condition(item, fields, *, membership=False, mode='condition'):
    if (set(item) - {'id', 'field', 'schemaVersion', 'operator', 'value', 'valueEnd'} or
            type(item.get('schemaVersion')) is not int or item['schemaVersion'] != 2 or
            ('id' in item and type(item['id']) is not int)):
        raise invalid_query()
    field, operator = item.get('field'), item.get('operator')
    if not isinstance(field, str) or field not in fields or not isinstance(operator, str):
        raise invalid_query()
    spec = fields[field]
    kind = spec['kind']
    value, end = item.get('value'), item.get('valueEnd')
    if end not in (None, '') and operator != 'between':
        raise invalid_query()
    if operator in {'isEmpty', 'notEmpty'} and value not in (None, ''):
        raise invalid_query()
    if operator == 'reference':
        if not kind.startswith('enum_'):
            raise invalid_query()
        operator, membership = 'in', True
    if kind.startswith('enum_') and operator in CHARACTER_OPERATORS:
        if kind == 'enum_text' and not spec.get('labels'):
            build_query_clause(literal_column('value'), 'text', item)
            return Condition(field, operator, 'text', scalar(value, 'text'), schemaVersion=2)
        needle = scalar(value, 'text')
        match = {'contains': lambda label: needle in label,
                 'notContains': lambda label: needle not in label,
                 'startsWith': lambda label: label.startswith(needle),
                 'endsWith': lambda label: label.endswith(needle)}[operator]
        values = [key for key, label in spec.get('labels', {}).items() if match(label.strip().lower())]
        return Condition(field, 'in', 'number' if kind == 'enum_number' else 'enum',
                         [Decimal(key) for key in values] if kind == 'enum_number' else values, schemaVersion=2)
    adapted = {**item, 'operator': operator}
    build_query_clause(literal_column('value'), kind, adapted, membership=membership)
    match_kind = 'number' if kind == 'enum_number' else 'enum' if kind == 'enum_text' else kind
    if operator in {'isEmpty', 'notEmpty'}:
        value = end = None
    elif operator in {'in', 'notIn'}:
        value = [scalar(v, kind) for v in value]
        if match_kind == 'number':
            value = [Decimal(v) for v in value]
    else:
        value = scalar(value, kind)
        if match_kind == 'number':
            value = Decimal(value)
        end = scalar(end, kind) if operator == 'between' else None
    return Condition(field, operator, match_kind, value, end, 2, mode)


def compile_business_query(fields, filters=None, column_filters=None):
    conditions = [_condition(item, fields) for item in query_items(filters)]
    seen = set()
    budget = sum(len(c.value) if isinstance(c.value, list) else 2 for c in conditions)
    for item in query_items(column_filters):
        field = item.get('field')
        if not isinstance(field, str) or field not in fields or field in seen:
            raise invalid_query()
        seen.add(field)
        if item.get('mode') == 'condition':
            if set(item) != {'field', 'mode', 'condition'} or not isinstance(item['condition'], dict) or item['condition'].get('field') != field:
                raise invalid_query()
            condition = _condition(item['condition'], fields)
        elif item.get('mode') == 'values':
            values = item.get('values')
            if set(item) != {'field', 'mode', 'values'} or not isinstance(values, list) or len(values) > 1000:
                raise invalid_query()
            if any(type(v) not in (str, int, float, type(None)) for v in values):
                raise invalid_query()
            values = [None if isinstance(v, str) and not v.strip() else v for v in values]
            populated = [v for v in values if v is not None]
            if populated:
                condition = _condition({'schemaVersion': 2, 'field': field, 'operator': 'in', 'value': populated},
                                       fields, membership=True, mode='values')
            else:
                kind = fields[field]['kind']
                condition = Condition(field, 'in', 'number' if kind == 'enum_number' else 'enum' if kind == 'enum_text' else kind,
                                      [], schemaVersion=2, mode='values')
            if None in values:
                condition = Condition(condition.field, condition.operator, condition.kind, [*condition.value, None], schemaVersion=2, mode='values')
        else:
            raise invalid_query()
        conditions.append(condition)
        budget += len(condition.value) if isinstance(condition.value, list) else 2
    if budget > 1600:
        raise invalid_query()
    return conditions


def filter_business_rows(rows, fields, filters=None, column_filters=None, sort=None):
    conditions = compile_business_query(fields, filters, column_filters)
    result = [row for row in rows if matches_filters(row, conditions)]
    key = business_sort_key(fields, sort)
    return sorted(result, key=key) if sort else result


def business_sort_key(fields, sort):
    orders = query_items(sort)
    seen = set()
    for item in orders:
        field = item.get('colId')
        if set(item) != {'colId', 'sort'} or not isinstance(field, str) or field not in fields or field in seen or item.get('sort') not in ('asc', 'desc'):
            raise invalid_query()
        seen.add(field)
    def compare(left, right):
        for item in orders:
            field, direction = item['colId'], item['sort']
            a, b = left.get(field), right.get(field)
            if a in (None, '') or b in (None, ''):
                delta = (b in (None, '')) - (a in (None, ''))
            else:
                kind = fields[field]['kind']
                if kind in ('number', 'enum_number'):
                    a, b = Decimal(str(a)), Decimal(str(b))
                elif kind == 'date':
                    a = a.date().isoformat() if isinstance(a, datetime) else str(a)[:10]
                    b = b.date().isoformat() if isinstance(b, datetime) else str(b)[:10]
                else:
                    a, b = str(a), str(b)
                delta = (a > b) - (a < b)
            if direction == 'desc':
                delta = -delta
            if delta:
                return delta
        return 0
    return cmp_to_key(compare)
