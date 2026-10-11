"""Versioned, typed SQL predicates. Callers supply the allowlisted column and type."""
import datetime
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException
from sqlalchemy import and_, or_, func

EMPTY = {'isEmpty', 'notEmpty'}
ORDERED = {'equals','notEquals','greaterThan','greaterOrEqual','lessThan','lessOrEqual','between'} | EMPTY

def invalid():
    return HTTPException(422, detail='查询条件无效，请检查字段、匹配方式和值')

def scalar(value, kind):
    if value is None or isinstance(value, (bool, list, dict)):
        raise ValueError()
    if kind == 'enum_number':
        if type(value) is not int:
            raise ValueError()
        return value
    if kind in ('number','decimal'):
        if not isinstance(value, (str, int, float)):
            raise ValueError()
        number = Decimal(str(value))
        if not number.is_finite() or abs(number) > 999999999999:
            raise ValueError()
        return number
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError()
    if kind == 'date':
        if len(value) != 10:
            raise ValueError()
        return datetime.date.fromisoformat(value)
    return value.strip().lower() if kind == 'text' else value

def build_query_clause(column, kind, condition, *, membership=False):
    operator = condition.get('operator')
    allowed = ({'contains','notContains','equals','notEquals','startsWith','endsWith'} | EMPTY) if kind == 'text' else ({'equals','notEquals','in','notIn'} | EMPTY) if kind.startswith('enum_') else ORDERED
    if membership:
        allowed |= {'in','notIn'}
    if condition.get('schemaVersion') != 2 or operator not in allowed:
        raise invalid()
    try:
        text = kind in ('text','enum_text')
        empty = or_(column.is_(None), func.trim(column) == '') if text else column.is_(None)
        if operator in EMPTY:
            return empty if operator == 'isEmpty' else ~empty
        value = condition.get('value')
        if operator in ('in','notIn'):
            if not isinstance(value, list) or not 1 <= len(value) <= (1000 if membership else 100):
                raise ValueError()
            values = [scalar(item, kind) for item in value]
            compared = func.lower(func.trim(column)) if kind == 'text' else column
            clause = compared.in_(values)
            return and_(~empty, clause if operator == 'in' else ~clause)
        value = scalar(value, kind)
        end = scalar(condition.get('valueEnd'), kind) if operator == 'between' else None
        if end is not None and value > end:
            raise ValueError()
        if kind == 'date':
            next_day = value + datetime.timedelta(days=1)
            clause = {
                'equals': lambda: and_(column >= value, column < next_day),
                'notEquals': lambda: or_(column < value, column >= next_day),
                'greaterThan': lambda: column >= next_day,
                'greaterOrEqual': lambda: column >= value,
                'lessThan': lambda: column < value,
                'lessOrEqual': lambda: column < next_day,
                'between': lambda: and_(column >= value, column < end + datetime.timedelta(days=1)),
            }[operator]()
        else:
            compared = func.lower(func.trim(column)) if kind == 'text' else column
            # MSSQL LIKE treats '[' as a wildcard too; escape it with the same
            # explicit escape character used for '%' and '_' on every dialect.
            literal = value.replace('/', '//').replace('%', '/%').replace('_', '/_').replace('[', '/[') if kind == 'text' else value
            clause = {
                'contains': lambda: compared.contains(literal, escape='/'),
                'notContains': lambda: ~compared.contains(literal, escape='/'),
                'startsWith': lambda: compared.startswith(literal, escape='/'),
                'endsWith': lambda: compared.endswith(literal, escape='/'),
                'equals': lambda: compared == value,
                'notEquals': lambda: compared != value,
                'greaterThan': lambda: compared > value,
                'greaterOrEqual': lambda: compared >= value,
                'lessThan': lambda: compared < value,
                'lessOrEqual': lambda: compared <= value,
                'between': lambda: compared.between(value, end),
            }[operator]()
        return and_(~empty, clause)
    except (ValueError, TypeError, OverflowError, InvalidOperation, KeyError):
        raise invalid()
