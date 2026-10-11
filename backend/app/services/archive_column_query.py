"""Scoped archive column filters and independently paged distinct candidates."""
import datetime
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import func, or_, false, case, cast, Date
from app.services.list_query import archive_columns, apply_archive_list_query, query_items, invalid_query
from app.services.query_conditions import build_query_clause

def day_column(column, db):
    return func.date(column) if db.bind.dialect.name == 'sqlite' else cast(column,Date)

def archive_candidate_labels(db, field):
    from app.services.offline_archive_fields import OFFLINE_FIELDS
    from app.models.dict import SysDict, SysDictItem
    from app.models.product_line import SysProductLine
    from app.services.erp_queue import STATUS_LABELS
    code = OFFLINE_FIELDS.get(field, {}).get('enum_code') or {'equipment_series':'equipment_series', 'product_category':'product_category', 'status':'archive_status'}.get(field)
    if field == 'product_line_id':
        return {row.id:row.display_name for row in db.query(SysProductLine).all()}
    if code:
        rows = db.query(SysDictItem).join(SysDict,SysDict.id==SysDictItem.dict_id).filter(SysDict.dict_code==code).all()
        return {int(row.item_value):row.item_label for row in rows if str(row.item_value).isdigit()}
    if field == 'is_enabled':
        return {1:'启用',0:'禁用'}
    if field == 'erp_sync_status':
        return {**STATUS_LABELS,'pending':'同步中','historical':'金蝶历史档案'}
    return {}

def apply_archive_column_filters(query, filters):
    columns = archive_columns()
    used = set()
    for item in query_items(filters):
        field = item.get('field')
        if field not in columns or field in used:
            raise invalid_query()
        used.add(field)
        column, kind = columns[field]
        if item.get('mode') == 'condition':
            condition = item.get('condition')
            if not isinstance(condition, dict) or condition.get('field') != field:
                raise invalid_query()
            query = apply_archive_list_query(query.order_by(None), [condition])
        elif item.get('mode') == 'values':
            values = item.get('values')
            if not isinstance(values, list) or len(values) > 1000:
                raise invalid_query()
            if not values:
                query = query.filter(false())
                continue
            values = [None if v is None or isinstance(v,str) and not v.strip() else v for v in values]
            clauses = []
            if None in values:
                clauses.append(build_query_clause(column, kind, {'operator':'isEmpty','schemaVersion':2}))
            populated = [v for v in values if v is not None]
            if populated:
                compared = day_column(column,query.session) if kind == 'date' else column
                clauses.append(build_query_clause(compared,kind,{'operator':'in','value':populated,'schemaVersion':2},membership=True))
            query = query.filter(or_(*clauses))
        else:
            raise invalid_query()
    # Include the extra column predicates in SQL Server's bound-parameter budget.
    return apply_archive_list_query(query.order_by(None))

def archive_column_candidates(db, field, *, filters=None, column_filters=None, keyword='', page=1, page_size=100, scope_context=None):
    from app.services.project import get_scoped_archive_query
    columns = archive_columns()
    if field not in columns:
        raise invalid_query()
    query = apply_archive_list_query(get_scoped_archive_query(db,scope_context), filters)
    other = [item for item in query_items(column_filters) if item.get('field') != field]
    query = apply_archive_column_filters(query,other)
    column, kind = columns[field]
    labels = archive_candidate_labels(db, field)
    expression = (day_column(column,db) if kind == 'date' else
                  func.nullif(func.trim(column),'') if kind == 'text' else column)
    from app.models.project import PmsProjectArchive as Archive
    source = query.order_by(None).with_entities(
        Archive.id.label('archive_id'), expression.label('value')).subquery('archive_candidate_rows')
    value_column = source.c.value
    candidates = db.query(value_column,func.count(source.c.archive_id))
    if keyword:
        from sqlalchemy import cast, String
        literal = keyword.replace('/', '//').replace('%','/%').replace('_','/_').replace('[','/[')
        raw_match = cast(value_column,String(256)).contains(literal,escape='/')
        label_values = [value for value,label in labels.items() if keyword.lower() in label.lower()]
        candidates = candidates.filter(or_(raw_match,value_column.in_(label_values)))
    ordering = case(labels,value=value_column,else_='') if labels else value_column
    candidates = candidates.group_by(value_column).order_by(ordering,value_column).offset((page-1)*page_size).limit(page_size+1)
    from sqlalchemy.dialects import mssql
    compiled = candidates.statement.compile(dialect=mssql.pyodbc.dialect(paramstyle='qmark'),compile_kwargs={'render_postcompile':True})
    if len(compiled.positiontup or ()) > 2000:
        raise HTTPException(422,detail='查询条件与候选标签组合过大，请减少条件或拆分查询')
    rows = candidates.all()
    def value(v):
        if isinstance(v,Decimal):return float(v)
        if isinstance(v,(datetime.datetime,datetime.date)):return v.isoformat()[:10]
        return v
    return {'items':[{'value':value(v),'label':'（空白）' if v is None or v == '' else labels.get(v,str(value(v))),'count':count} for v,count in rows[:page_size]],'hasMore':len(rows)>page_size}
