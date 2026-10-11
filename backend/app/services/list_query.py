"""Allowlisted archive filters and stable ordering, applied before SQL pagination."""
import datetime
import json
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import func, select, cast, String, or_, case
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
        'address_province', 'address_city', 'address_detail', 'project_contact', 'contact_phone',
    )}
    fields.update({name: (getattr(Archive, name), 'number') for name in (
        'id', 'product_category', 'equipment_series', 'is_enabled', 'status',
    )})
    fields['product_line_id'] = (Archive.business_product_line_id, 'number')
    fields.update({name: (getattr(Archive, name), 'date') for name in (
        'plan_start_date', 'plan_end_date', 'created_at', 'updated_at', 'erp_sync_time',
        'contract_signed_date', 'contract_ship_date', 'actual_ship_date', 'warranty_end_date',
    )})
    from app.services.offline_archive_fields import OFFLINE_FIELDS
    for name, meta in OFFLINE_FIELDS.items():
        kind = 'number' if meta['enum_code'] else 'date' if name.endswith('_date') else 'decimal' if name == 'quantity' else 'text'
        fields[name] = (getattr(Archive, name), kind)
    fields['erp_sync_policy'] = (Archive.erp_sync_policy, 'text')
    for name, foreign_key in (
        ('manager_name', 'manager_id'), ('created_by_name', 'created_by'),
        ('updated_by_name', 'updated_by'), ('erp_sync_by_name', 'erp_sync_by'),
    ):
        fields[name] = (select(SysUser.real_name).where(
            SysUser.id == getattr(Archive, foreign_key)
        ).scalar_subquery(), 'text')
    fields['erp_sync_status'] = (func.coalesce(Archive.erp_sync_status, ''), 'text')
    fields['erp_sync_state'] = (func.coalesce(func.nullif(Archive.erp_sync_status, ''), case(
        (Archive.data_origin == 'kingdee_initial', 'historical'),
        (Archive.erp_synced == 1, 'success'), else_='')), 'text')
    return fields


def apply_archive_list_query(query, filters=None, sort=None):
    columns = archive_columns()
    from app.services.offline_archive_fields import OFFLINE_FIELDS
    enum_numbers = {'product_line_id', 'product_category', 'equipment_series', 'is_enabled', 'status'} | {name for name, meta in OFFLINE_FIELDS.items() if meta['enum_code']}
    enum_text = {'manager_name','created_by_name','updated_by_name','erp_sync_by_name','erp_sync_status','erp_sync_state','address_province','address_city'}
    kinds = {name: 'enum_number' if name in enum_numbers else 'enum_text' if name in enum_text else kind for name, (_, kind) in columns.items()}
    items = query_items(filters)
    # Bound individual filter payloads before building the complete scoped query.
    if sum(len(c.get('value')) if isinstance(c.get('value'), list) else 2 for c in items) > 1600:
        raise invalid_query()
    remaining = []
    for item in items:
        field, operator = item.get('field'), item.get('operator')
        if field == 'keyword':
            # Preserve the former four-field OR search inside the scoped AND query.
            if item.get('schemaVersion') != 2 or operator != 'contains':
                raise invalid_query()
            from app.services.query_conditions import build_query_clause
            query = query.filter(or_(*(build_query_clause(columns[name][0], 'text', item)
                for name in ('project_code','project_name','customer','serial_no'))))
        elif item.get('schemaVersion') == 2 and operator == 'reference':
            if field not in {'project_code','project_name'} | enum_numbers | enum_text:
                raise invalid_query()
            values = item.get('value')
            if not isinstance(values, list) or not 1 <= len(values) <= 1000:
                raise invalid_query()
            column, kind = (Archive.id, 'enum_number') if field in {'project_code','project_name'} else (columns[field][0], kinds[field])
            from app.services.query_conditions import build_query_clause
            if kind == 'enum_number' and any(type(v) is not int or v < (1 if field in {'project_code','project_name'} else 0) or v > 2147483647 for v in values):
                raise invalid_query()
            query = query.filter(build_query_clause(column, kind, {**item,'operator':'in'},membership=True))
        elif item.get('schemaVersion') == 2 and operator in {'contains','notContains','startsWith','endsWith'} and field in enum_numbers | enum_text:
            query = query.filter(_archive_label_clause(query.session, field, columns[field][0], item))
        else:
            remaining.append(item)
    query = apply_list_query(query, columns, remaining, sort, (Archive.project_code.desc(), Archive.id.desc()), unified_kinds=kinds, membership_fields={'project_code','project_name'})
    from sqlalchemy.dialects import mssql
    compiled = query.statement.compile(dialect=mssql.pyodbc.dialect(paramstyle='qmark'), compile_kwargs={'render_postcompile': True})
    # Scope predicates also contribute parameters; leave room for paging/count.
    if len(compiled.positiontup or ()) > 2000:
        raise HTTPException(422, detail='查询条件与权限范围组合过大，请减少引用数量或拆分查询')
    return query


def _archive_label_clause(db, field, column, item):
    from app.services.query_conditions import build_query_clause
    from app.services.offline_archive_fields import OFFLINE_FIELDS
    from app.models.dict import SysDict, SysDictItem
    from app.models.product_line import SysProductLine
    enum_code = OFFLINE_FIELDS.get(field, {}).get('enum_code') or {'equipment_series':'equipment_series','product_category':'product_category','status':'archive_status'}.get(field)
    if field == 'product_line_id':
        return column.in_(select(SysProductLine.id).where(build_query_clause(SysProductLine.display_name,'text',item)))
    if enum_code:
        # Include disabled values for historical querying; never enable them for writes.
        return cast(column,String(64)).in_(select(SysDictItem.item_value).join(SysDict,SysDict.id==SysDictItem.dict_id).where(
            SysDict.dict_code==enum_code, build_query_clause(SysDictItem.item_label,'text',item)))
    if field in {'is_enabled','erp_sync_status','erp_sync_state'}:
        from app.services.erp_queue import STATUS_LABELS
        labels = {1:'启用',0:'禁用'} if field=='is_enabled' else {**STATUS_LABELS, 'pending':'同步中','historical':'金蝶历史档案', '':'未同步'}
        from app.services.query_conditions import scalar, invalid
        try:
            needle=scalar(item.get('value'),'text')
        except (ValueError,TypeError):
            raise invalid()
        match={'contains':lambda label:needle in label,'notContains':lambda label:needle not in label,
               'startsWith':lambda label:label.startswith(needle),'endsWith':lambda label:label.endswith(needle)}[item['operator']]
        return column.in_([key for key,label in labels.items() if match(label.lower())])
    return build_query_clause(column,'text',item)


def apply_list_query(query, columns, filters=None, sort=None, default_order=(), unified_kinds=None, membership_fields=frozenset()):
    for item in query_items(filters):
        field, operator = item.get('field'), item.get('operator')
        if field not in columns:
            raise invalid_query()
        column, kind = columns[field]
        if item.get('schemaVersion') not in (None, 1, 2) or isinstance(item.get('schemaVersion'), bool):
            raise invalid_query()
        if item.get('schemaVersion') == 2:
            if not unified_kinds:
                raise invalid_query()
            from app.services.query_conditions import build_query_clause
            query = query.filter(build_query_clause(column, unified_kinds[field], item,membership=field in membership_fields))
            continue
        allowed = {'text': {'contains', 'equals', 'notEquals'},
                   'number': {'equals', 'notEquals', 'greaterThan', 'lessThan', 'between'},
                   'decimal': {'equals', 'notEquals', 'greaterThan', 'lessThan', 'between'},
                   'date': {'equals', 'before', 'after', 'between'}}[kind]
        if field == 'archive_category':
            allowed = allowed | {'in'}
        if operator not in allowed:
            raise invalid_query()
        value, end = item.get('value'), item.get('valueEnd')
        if operator == 'in':
            if not isinstance(value, list) or not 1 <= len(value) <= 100 or any(type(v) is not int or v <= 0 for v in value):
                raise invalid_query()
            query = query.filter(column.in_(value))
            continue
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
                if kind == 'decimal':
                    value = Decimal(str(value))
                    if not value.is_finite():
                        raise ValueError()
                    if operator == 'between':
                        end = Decimal(str(end))
                        if not end.is_finite():
                            raise ValueError()
                        value, end = sorted((value, end))
                elif kind == 'number':
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
        except (ValueError, TypeError, OverflowError, InvalidOperation):
            raise invalid_query()
    ordering = []
    ordered_columns = []
    for item in query_items(sort):
        field, direction = item.get('colId'), item.get('sort')
        if field not in columns or direction not in ('asc', 'desc'):
            raise invalid_query()
        column = columns[field][0]
        ordering.append(column.asc() if direction == 'asc' else column.desc())
        ordered_columns.append(ordering[-1].element)
    # SQL Server requires each ORDER BY column to occur only once.
    fallback = [clause for clause in default_order
                if not any(clause.element.compare(column) for column in ordered_columns)]
    return query.order_by(*ordering, *fallback)
