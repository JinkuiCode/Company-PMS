"""Allowlisted archive filters and stable ordering, applied before SQL pagination."""
import datetime
import json

from fastapi import HTTPException
from sqlalchemy import func, select
from app.models.project import PmsProjectArchive as Archive
from app.models.user import SysUser


def invalid_query():
    return HTTPException(422, detail='列表查询条件无效，请检查筛选字段、运算符和排序')


def query_items(value):
    try:
        items = json.loads(value) if isinstance(value, str) else (value or [])
        if not isinstance(items, list) or len(items) > 50:
            raise ValueError()
        if any(not isinstance(item, dict) for item in items):
            raise ValueError()
        return items
    except (ValueError, TypeError):
        raise invalid_query()


def archive_columns():
    fields = {name: (getattr(Archive, name), 'text') for name in (
        'project_code', 'project_name', 'customer', 'serial_no', 'data_origin', 'erp_sync_status',
    )}
    fields.update({name: (getattr(Archive, name), 'number') for name in (
        'id', 'product_category', 'equipment_series', 'is_enabled', 'status',
    )})
    fields.update({name: (getattr(Archive, name), 'date') for name in (
        'plan_start_date', 'plan_end_date', 'created_at', 'updated_at', 'erp_sync_time',
    )})
    for name, foreign_key in (
        ('manager_name', 'manager_id'), ('created_by_name', 'created_by'),
        ('updated_by_name', 'updated_by'), ('erp_sync_by_name', 'erp_sync_by'),
    ):
        fields[name] = (select(SysUser.real_name).where(
            SysUser.id == getattr(Archive, foreign_key)
        ).scalar_subquery(), 'text')
    fields['erp_sync_status'] = (func.coalesce(Archive.erp_sync_status, 'pending'), 'text')
    return fields


def apply_archive_list_query(query, filters=None, sort=None):
    return apply_list_query(query, archive_columns(), filters, sort, (Archive.id.desc(),))


def apply_list_query(query, columns, filters=None, sort=None, default_order=()):
    for item in query_items(filters):
        field, operator = item.get('field'), item.get('operator')
        if field not in columns:
            raise invalid_query()
        column, kind = columns[field]
        allowed = {'text': {'contains', 'equals', 'notEquals'},
                   'number': {'equals', 'notEquals', 'greaterThan', 'lessThan', 'between'},
                   'date': {'equals', 'before', 'after', 'between'}}[kind]
        if operator not in allowed:
            raise invalid_query()
        value, end = item.get('value'), item.get('valueEnd')
        if value in (None, '') or (operator == 'between' and end in (None, '')):
            continue
        try:
            if kind == 'date':
                value = datetime.date.fromisoformat(str(value)[:10])
                if operator == 'between':
                    end = datetime.date.fromisoformat(str(end)[:10])
                    value, end = sorted((value, end))
                if operator == 'equals':
                    clause = (column >= value) & (column < value + datetime.timedelta(days=1))
                elif operator == 'before':
                    clause = column < value
                elif operator == 'after':
                    clause = column >= value + datetime.timedelta(days=1)
                else:
                    clause = (column >= value) & (column < end + datetime.timedelta(days=1))
            else:
                if kind == 'number':
                    value = int(value)
                    if operator == 'between':
                        value, end = sorted((value, int(end)))
                else:
                    column = func.lower(func.trim(func.coalesce(column, '')))
                    value = str(value).strip().lower()
                if operator == 'contains':
                    clause = column.contains(value, autoescape=True)
                elif operator == 'notEquals':
                    clause = (column != value) | column.is_(None)
                elif operator == 'greaterThan':
                    clause = column > value
                elif operator == 'lessThan':
                    clause = column < value
                elif operator == 'between':
                    clause = column.between(value, end)
                else:
                    clause = column == value
            query = query.filter(clause)
        except (ValueError, TypeError, OverflowError):
            raise invalid_query()
    ordering = []
    for item in query_items(sort):
        field, direction = item.get('colId'), item.get('sort')
        if field not in columns or direction not in ('asc', 'desc'):
            raise invalid_query()
        column = columns[field][0]
        ordering.append(column.asc() if direction == 'asc' else column.desc())
    return query.order_by(*ordering, *default_order)
