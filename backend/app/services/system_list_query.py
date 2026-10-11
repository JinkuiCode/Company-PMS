"""Allowlisted query v2 predicates and SQL candidates for system lists."""
from sqlalchemy import Unicode, case, cast, false, func, literal_column, or_
from sqlalchemy.dialects import mssql

from app.services.list_query import apply_list_query, invalid_query, query_items
from app.services.query_conditions import build_query_clause

TEXT_OPERATORS = {'contains', 'notContains', 'startsWith', 'endsWith'}


def label_column(column, labels):
    return case(labels, value=column, else_=column) if labels else column


def condition_clause(columns, labels, item):
    field = item.get('field')
    if not isinstance(field, str) or field not in columns or type(item.get('schemaVersion')) is not int:
        raise invalid_query()
    column, kind = columns[field]
    operator = item.get('operator')
    if not isinstance(operator, str):
        raise invalid_query()
    if operator == 'reference':
        if not kind.startswith('enum_'):
            raise invalid_query()
        item = {**item, 'operator': 'in'}
    elif kind.startswith('enum_') and operator in TEXT_OPERATORS:
        column, kind = label_column(column, labels.get(field)), 'text'
    return build_query_clause(column, kind, item, membership=operator == 'reference')


def values_clause(columns, field, values, *, dialect):
    if not isinstance(values, list) or len(values) > 1000:
        raise invalid_query()
    column, kind = columns[field]
    clauses = []
    nonempty = [value for value in values if value is not None]
    if any(isinstance(value, bool) or (kind in ('number', 'decimal') and type(value) not in (int, float)) for value in nonempty):
        raise invalid_query()
    if any(value is None for value in values):
        clauses.append(build_query_clause(column, kind, {'schemaVersion': 2, 'operator': 'isEmpty'}))
    if nonempty:
        compared = (func.date(column) if dialect == 'sqlite' else cast(column, mssql.DATE)) if kind == 'date' else column
        clauses.append(build_query_clause(compared, kind,
            {'schemaVersion': 2, 'operator': 'in', 'value': nonempty}, membership=True))
    return or_(*clauses) if clauses else false()


def apply_system_list_query(query, columns, filters=None, column_filters=None, *, labels=None, exclude_field=None):
    labels = labels or {}
    conditions, column_items = query_items(filters), query_items(column_filters)
    if sum(len(item.get('value')) if isinstance(item.get('value'), list) else 2 for item in conditions) + sum(
        len(item.get('values', [])) if isinstance(item.get('values'), list) else 2 for item in column_items
    ) > 1600:
        raise invalid_query()
    legacy = []
    for item in conditions:
        version = item.get('schemaVersion')
        if version is not None and (type(version) is not int or version not in (1, 2)):
            raise invalid_query()
        if version == 2:
            query = query.filter(condition_clause(columns, labels, item))
        else:
            if not isinstance(item.get('field'), str) or not isinstance(item.get('operator'), str):
                raise invalid_query()
            legacy.append(item)
    legacy_columns = {field: (column, 'text' if kind.startswith('enum_') else kind)
                      for field, (column, kind) in columns.items()}
    query = apply_list_query(query, legacy_columns, legacy)
    seen = set()
    for item in column_items:
        field = item.get('field')
        if not isinstance(field, str) or field not in columns or field in seen:
            raise invalid_query()
        seen.add(field)
        if item.get('mode') == 'values':
            clause = values_clause(columns, field, item.get('values'), dialect=query.session.get_bind().dialect.name)
        elif item.get('mode') == 'condition':
            condition = item.get('condition')
            if not isinstance(condition, dict) or condition.get('field') != field or condition.get('schemaVersion') != 2:
                raise invalid_query()
            clause = condition_clause(columns, labels, condition)
        else:
            raise invalid_query()
        # Validate even the excluded column; exclusion is not a validation bypass.
        if field != exclude_field:
            query = query.filter(clause)
    validate_parameter_budget(query)
    return query


def validate_parameter_budget(query):
    compiled = query.statement.compile(dialect=mssql.pyodbc.dialect(paramstyle='qmark'),
        compile_kwargs={'render_postcompile': True})
    if len(compiled.positiontup or ()) > 2000:
        raise invalid_query()


def system_column_values(query, columns, field, *, keyword='', page=1, page_size=100, labels=None):
    if not isinstance(field, str) or field not in columns or type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
        raise invalid_query()
    column, kind = columns[field]
    if kind == 'date':
        value = func.date(column) if query.session.get_bind().dialect.name == 'sqlite' else cast(column, mssql.DATE)
    elif kind in ('text', 'enum_text'):
        # Fixed constants keep SELECT/GROUP BY expressions identical with ODBC bindings.
        value = case((or_(column.is_(None), func.trim(column) == literal_column("''")), None), else_=column)
    else:
        value = column
    labels = (labels or {}).get(field, {})
    display = label_column(value, labels)
    if keyword:
        if not isinstance(keyword, str) or len(keyword) > 256:
            raise invalid_query()
        # Search labels, never the raw enum protocol value. Blank has a visible label too.
        display_text = case((value.is_(None), '（空白）'), else_=cast(display, Unicode(1024)))
        query = query.filter(build_query_clause(display_text, 'text',
            {'schemaVersion': 2, 'operator': 'contains', 'value': keyword}))
    grouped = query.order_by(None).with_entities(value.label('value'), func.count().label('count')).group_by(value)
    validate_parameter_budget(grouped)
    rows = grouped.order_by(case((value.is_(None), 0), else_=1), value.asc()).offset((page - 1) * page_size).limit(page_size + 1).all()
    items = []
    for raw, count in rows[:page_size]:
        candidate = raw.isoformat() if kind == 'date' and raw is not None and not isinstance(raw, str) else raw
        items.append({'value': candidate, 'label': '（空白）' if candidate is None else labels.get(candidate, str(candidate)), 'count': count})
    return {'items': items, 'hasMore': len(rows) > page_size, 'page': page, 'page_size': page_size}
