"""Typed report allowlists shared by request validation, SQL and row filtering."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import re
from fastapi import HTTPException
from sqlalchemy import literal_column, or_, false, cast, Date
from sqlalchemy.dialects import mssql
from app.services.query_conditions import build_query_clause, scalar

from app.services.purchase_fields import report_fields as purchase_fields, DOCUMENT_STATUSES, PROGRESS_LABELS
from app.services.stock_detail_fields import report_fields as stock_fields, QUERY_ONLY_FIELDS

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
                     'close_status', 'requested', 'approved', 'progress'}
        fields = [f for f in purchase_fields() if f['key'] in supported]
        enums = {'document_status': DOCUMENT_STATUSES, 'close_status': {'A': '未关闭', 'B': '已关闭'},
                 'progress': PROGRESS_LABELS}
    elif report == 'stock-detail':
        fields = [*stock_fields(), *[dict(key=k, label=l, type=t) for k,l,t,_ in QUERY_ONLY_FIELDS]]
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
    schemaVersion: int = 1
    mode: str = 'condition'


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


def parse_filters(raw, report, *, additional_fields=()):
    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError('Invalid filters JSON') from None
    if not isinstance(values, list) or len(values) > 20:
        raise ValueError('Filters must be a list of at most 20 conditions')
    fields = {f['field']: f for f in (query_fields(report) if report in {'inventory', 'purchase-overview'} else filter_fields(report))}
    fields.update({f['field']: f for f in additional_fields})
    conditions = []
    for item in values:
        if isinstance(item, dict) and item.get('schemaVersion') == 2:
            conditions.append(_parse_v2(item, report, additional_fields=additional_fields))
            continue
        if isinstance(item, dict) and type(item.get('schemaVersion')) is int and item['schemaVersion'] == 1:
            if 'id' in item and type(item['id']) is not int:
                raise ValueError('Invalid condition identity')
            item = {key: value for key, value in item.items() if key not in {'schemaVersion', 'id'}}
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


def query_fields(report):
    """V2 capabilities; fixed purchase data status is display-only."""
    from app.services.purchase_fields import overview_fields
    from app.services.inventory_fields import report_fields as inventory_fields
    if report == 'purchase':
        fields = purchase_fields()
    elif report == 'purchase-overview':
        fields = overview_fields()
    elif report == 'inventory':
        fields = inventory_fields()
    elif report == 'stock-detail':
        fields = [*stock_fields(), *[dict(key=k, label=l, type=t) for k,l,t,_ in QUERY_ONLY_FIELDS]]
    else:
        raise ValueError('Unknown report')
    enums = {'document_status': DOCUMENT_STATUSES, 'close_status': {'A': '未关闭', 'B': '已关闭'},
             'progress': PROGRESS_LABELS}
    result = []
    for field in fields:
        key = field['key']
        if report.startswith('purchase') and key == 'document_status':
            continue
        kind = field.get('value_type', field.get('type'))
        kind = 'number' if kind == 'decimal' else kind
        kind = 'enum' if key in enums else kind
        spec = dict(field=key, label=field['label'], type=kind, operators=list(OPERATORS[kind]))
        if key in enums:
            spec['options'] = [dict(value=v, label=label) for v, label in enums[key].items()]
            spec['operators'] += ['in', 'notIn', 'reference', 'contains', 'notContains', 'startsWith', 'endsWith']
        if report.startswith('purchase') and key in {'project_code', 'project_name'}:
            spec['reference'] = dict(source='project-archive', keyField='id', keyType='number')
            spec['operators'] += ['reference']
        result.append(spec)
    return result


def _parse_v2(item, report, *, additional_fields=()):
    if set(item) - {'id', 'schemaVersion', 'field', 'operator', 'value', 'valueEnd'}:
        raise ValueError('Invalid filter condition')
    if 'id' in item and type(item['id']) is not int:
        raise ValueError('Invalid condition identity')
    specs = {f['field']: f for f in [*query_fields(report), *additional_fields]}
    field, operator = item.get('field'), item.get('operator')
    if not isinstance(field, str) or field not in specs:
        raise ValueError('Unknown or unsupported v2 filter field')
    spec = specs[field]
    if not isinstance(operator, str) or operator not in spec['operators']:
        raise ValueError('Unsupported v2 filter operator')
    if item.get('valueEnd') not in (None, '') and operator != 'between':
        raise ValueError('Unexpected filter range end')
    if operator in EMPTY and item.get('value') not in (None, ''):
        raise ValueError('Empty operator does not accept a value')
    kind, value, end = spec['type'], item.get('value'), item.get('valueEnd')
    if operator == 'reference' and 'reference' in spec:
        if (not isinstance(value, list) or not 1 <= len(value) <= 1000 or
                any(type(v) is not int or not 0 < v <= 9007199254740991 for v in value)):
            raise ValueError('Invalid project archive identities')
        return Condition(field, operator, 'project-reference', value, schemaVersion=2)
    if kind == 'enum':
        options = {o['value']: o['label'] for o in spec['options']}
        if operator in {'contains', 'notContains', 'startsWith', 'endsWith'}:
            # Character filters target displayed labels, never protocol values.
            positive = {'contains': 'contains', 'notContains': 'contains',
                        'startsWith': 'startsWith', 'endsWith': 'endsWith'}[operator]
            try:
                target = scalar(value, 'text')
                build_query_clause(literal_column('label'), 'text', dict(item, operator=positive))
            except (ValueError, HTTPException):
                raise ValueError('Invalid enum label filter') from None
            predicate = {'contains': lambda label: target in label,
                         'startsWith': lambda label: label.startswith(target),
                         'endsWith': lambda label: label.endswith(target)}[positive]
            selected = [key for key, label in options.items() if predicate(label.strip().lower())]
            return Condition(field, 'notIn' if operator == 'notContains' else 'in', 'enum', selected, schemaVersion=2)
        if operator == 'reference':
            operator = 'in'
        values = value if operator in {'in', 'notIn'} else [value]
        if operator not in EMPTY and (not isinstance(values, list) or not values or
                any(type(v) is not str or v not in options for v in values)):
            raise ValueError('Unknown filter option')
    sql_kind = 'enum_text' if kind == 'enum' else kind
    if kind == 'number' and operator not in EMPTY:
        _value(value, spec)
        if operator == 'between':
            _value(end, spec)
    adapted = dict(item, operator=operator)
    try:
        build_query_clause(literal_column('value'), sql_kind, adapted)
        if operator in EMPTY:
            value = end = None
        elif operator in {'in', 'notIn'}:
            value = [scalar(v, sql_kind) for v in value]
        else:
            value = scalar(value, sql_kind)
            end = scalar(end, sql_kind) if operator == 'between' else None
    except (ValueError, HTTPException, InvalidOperation):
        raise ValueError('Invalid v2 filter condition') from None
    return Condition(field, operator, kind, value, end, 2)


def parse_column_filters(raw, report):
    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError('Invalid column filters JSON') from None
    if not isinstance(values, list) or len(values) > 20:
        raise ValueError('Invalid column filters')
    specs = {f['field']: f for f in query_fields(report) if f['operators'] != ['reference']}
    seen, result = set(), []
    for item in values:
        if not isinstance(item, dict) or not isinstance(item.get('field'), str):
            raise ValueError('Invalid column filter')
        field = item['field']
        if field in seen or field not in specs:
            raise ValueError('Duplicate or unsupported column field')
        seen.add(field)
        mode, spec = item.get('mode'), specs[field]
        if mode == 'condition':
            c = item.get('condition')
            if set(item) != {'field', 'mode', 'condition'} or not isinstance(c, dict) or c.get('field') != field or c.get('schemaVersion') != 2:
                raise ValueError('Invalid column condition')
            result.append(_parse_v2(c, report))
        elif mode == 'values':
            selected = item.get('values')
            if set(item) != {'field', 'mode', 'values'} or not isinstance(selected, list) or len(selected) > 1000:
                raise ValueError('Invalid selected column values')
            kind = 'enum_text' if spec['type'] == 'enum' else spec['type']
            try:
                normalized = [None if v is None else _value(v, spec) if kind == 'number' else scalar(v, kind) for v in selected]
                if spec['type'] == 'enum' and any(v is not None and v not in {o['value'] for o in spec['options']} for v in normalized):
                    raise ValueError('Unknown column option')
            except (ValueError, InvalidOperation):
                raise ValueError('Invalid column value') from None
            result.append(Condition(field, 'in', spec['type'], normalized, schemaVersion=2, mode='values'))
        else:
            raise ValueError('Unknown column filter mode')
    return result


def column_clause(column, condition):
    kind = 'enum_text' if condition.kind == 'enum' else condition.kind
    selected = condition.value
    clauses = []
    if None in selected:
        clauses.append(build_query_clause(column, kind, dict(schemaVersion=2, operator='isEmpty')))
    nonempty = [str(v) if isinstance(v, (date, Decimal)) else v for v in selected if v is not None]
    if nonempty:
        compared = cast(column, Date) if kind == 'date' else column
        clauses.append(build_query_clause(compared, kind, dict(schemaVersion=2, operator='in', value=nonempty), membership=True))
    return or_(*clauses) if clauses else false()


def compile_predicate(clause):
    dialect = mssql.dialect(paramstyle='format')
    dialect.server_version_info = (14, 0)
    compiled = clause.compile(dialect=dialect, compile_kwargs={'render_postcompile': True})
    return str(compiled), [compiled.params[compiled.escaped_bind_names.get(name, name)] for name in compiled.positiontup]


def sql_conditions(conditions, *, alias='filter_source', project_references=None):
    parts, params = [], []
    for condition in conditions:
        # Conditions come exclusively from the fixed report allowlist above.
        column = f'{alias}.[{condition.field}]'
        if condition.mode == 'values':
            sql, bound = compile_predicate(column_clause(literal_column(column), condition))
            parts.append('(' + sql + ')')
            params.extend(bound)
            continue
        if condition.kind == 'project-reference':
            references = project_references or {}
            if any(key not in references for key in condition.value):
                raise ValueError('Project references require current scoped archive resolution')
            pairs = sorted({references[key] for key in condition.value})
            parts.append('(' + ' OR '.join(f'({alias}.[project_code]=%s AND {alias}.[organization_id]=%s)' for _ in pairs) + ')')
            params.extend(v for pair in pairs for v in pair)
            continue
        if condition.schemaVersion == 2:
            if condition.operator in {'in', 'notIn'} and not condition.value:
                parts.append('1=0' if condition.operator == 'in' else f"({column} IS NOT NULL AND {column}<>'')")
                continue
            clause = build_query_clause(literal_column(column), 'enum_text' if condition.kind == 'enum' else condition.kind,
                dict(schemaVersion=2, operator=condition.operator,
                     value=str(condition.value) if isinstance(condition.value, (date, Decimal)) else condition.value,
                     valueEnd=str(condition.valueEnd) if isinstance(condition.valueEnd, (date, Decimal)) else condition.valueEnd))
            sql, bound = compile_predicate(clause)
            parts.append(sql)
            params.extend(bound)
            continue
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
    return ' AND '.join(f'({part})' for part in parts), params


def matches_filters(row, conditions):
    for condition in conditions:
        value, target, op = row.get(condition.field), condition.value, condition.operator
        empty = value is None or (condition.kind in ('text', 'enum') and
                                  (not value.strip() if condition.schemaVersion == 2 else value == ''))
        if condition.mode == 'values' and empty:
            if None not in target:
                return False
            continue
        if op in EMPTY:
            if empty != (op == 'isEmpty'):
                return False
            continue
        # NULL never matches a comparison, including negative comparisons.
        if value is None or (condition.schemaVersion == 2 and empty):
            return False
        if condition.kind == 'number':
            value = Decimal(str(value))
        elif condition.kind == 'date':
            value = value.date() if isinstance(value, datetime) else value
            value = date.fromisoformat(value) if isinstance(value, str) else value
        elif condition.kind == 'text' and condition.schemaVersion == 2:
            value = value.strip().lower()
        if op == 'contains': matched = target in value
        elif op == 'notContains': matched = target not in value
        elif op == 'startsWith': matched = value.startswith(target)
        elif op == 'endsWith': matched = value.endswith(target)
        elif op == 'equals': matched = value == target
        elif op == 'notEquals': matched = value != target
        elif op == 'in': matched = value in target
        elif op == 'notIn': matched = value not in target
        elif op == 'greaterThan': matched = value > target
        elif op == 'greaterOrEqual': matched = value >= target
        elif op == 'lessThan': matched = value < target
        elif op == 'lessOrEqual': matched = value <= target
        elif op == 'between': matched = target <= value <= condition.valueEnd
        else: raise ValueError('Invalid filter operator')
        if not matched:
            return False
    return True
