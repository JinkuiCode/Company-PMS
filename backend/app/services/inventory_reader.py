"""Bounded, parameterized reads of the inventory view, scoped by stable org IDs."""
import json
from decimal import Decimal, InvalidOperation
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator
from app.services.inventory_fields import FIELDS, report_fields
from app.services.business_data_scope import ALL_DATA_SCOPE
from app.services.report_filters import parse_filters, parse_column_filters, sql_conditions

KEYS = tuple(row[0] for row in FIELDS)
PUBLIC_KEYS = ('FID', *(field['key'] for field in report_fields()))
SOURCE = ' FROM dbo.YD_JIN_INVENTORY v '


class Condition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    field: str
    operator: Literal['contains','notContains','startsWith','endsWith','equals','notEquals','greaterThan','greaterOrEqual','lessThan','lessOrEqual','between','isEmpty','notEmpty']
    value: str | int | float | None = None
    valueEnd: str | int | float | None = None

    @model_validator(mode='after')
    def validate_condition(self):
        if self.field not in PUBLIC_KEYS or self.field == 'FID':
            raise ValueError('未知筛选字段')
        if self.operator in ('isEmpty','notEmpty'):
            return self
        if self.value is None or not str(self.value).strip():
            raise ValueError('请填写筛选值')
        if self.field == 'FBaseQty':
            if self.operator not in ('equals','notEquals','greaterThan','greaterOrEqual','lessThan','lessOrEqual','between'):
                raise ValueError('数量筛选操作无效')
            values = [self.value, self.valueEnd] if self.operator == 'between' else [self.value]
            try:
                numbers = [Decimal(str(value)) for value in values]
            except InvalidOperation:
                raise ValueError('数量格式无效') from None
            if any(not n.is_finite() or abs(n) > Decimal('999999999999') for n in numbers):
                raise ValueError('数量范围无效')
            if len(numbers) == 2 and numbers[0] > numbers[1]:
                raise ValueError('数量区间顺序无效')
        elif self.operator not in ('contains','notContains','startsWith','endsWith','equals','notEquals') or len(str(self.value)) > 256:
            raise ValueError('文本筛选无效')
        return self


class InventoryQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    _product_line_names: dict = PrivateAttr(default_factory=dict)
    keyword: str = Field(default='', max_length=100)
    organization_id: int | None = Field(default=None, gt=0)
    stock: str = Field(default='', max_length=256)
    filters: str = Field(default='[]', max_length=12000)
    column_filters: str = Field(default='[]', max_length=12000)
    page: int = Field(default=1, ge=1, le=1000000)
    page_size: int = Field(default=50, ge=1, le=500)
    sort: str = 'FID'
    direction: Literal['asc','desc'] = 'asc'

    @model_validator(mode='after')
    def validate_query(self):
        if self.sort not in PUBLIC_KEYS:
            raise ValueError('未知排序字段')
        self.conditions()
        return self

    def conditions(self):
        try:
            values = json.loads(self.filters)
        except (ValueError, TypeError):
            raise ValueError('筛选格式无效') from None
        if not isinstance(values, list) or len(values) > 20:
            raise ValueError('最多20个筛选条件')
        # Preserve old inventory validation and SQL semantics; only v2 delegates
        # to the shared query compiler via report field metadata.
        legacy = [Condition.model_validate({k: v for k, v in value.items() if k not in {'schemaVersion','id'}}
                  if isinstance(value, dict) and type(value.get('schemaVersion')) is int and value['schemaVersion'] == 1 else value) for value in values
                  if not isinstance(value, dict) or value.get('schemaVersion') != 2]
        typed = parse_filters(json.dumps([v for v in values if isinstance(v, dict) and v.get('schemaVersion') == 2]), 'inventory')
        columns = parse_column_filters(self.column_filters, 'inventory')
        return [*legacy, *typed, *columns]


def public_row(row):
    return {key: str(row[key]) if isinstance(row[key], Decimal) else row[key]
            for key in PUBLIC_KEYS if key in row}


def resolve_product_lines(db, query):
    from app.models.product_line import SysProductLine
    rows = db.query(SysProductLine.organization_id, SysProductLine.display_name).filter(
        SysProductLine.source_key == 'kingdee', SysProductLine.organization_id > 0)
    if query.organization_id:
        rows = rows.filter(SysProductLine.organization_id == query.organization_id)
    query._product_line_names = dict(rows.all())
    return query


def inventory_source(query):
    """Display adapter only: retain stable stock org IDs and original row scope."""
    parts, params = [], []
    for org, name in sorted(query._product_line_names.items()):
        parts.append('WHEN s.FSTOCKORGID=%s THEN %s')
        params.extend([org, name])
    fallback = ("CONCAT(COALESCE(NULLIF(raw.[Organization],''),"
                "CONCAT(N'组织 ',s.FSTOCKORGID)),N'（未配置产品线）')")
    expression = 'CASE ' + ' '.join(parts) + ' ELSE ' + fallback + ' END' if parts else fallback
    projection = ','.join(f'raw.[{key}]' for key in KEYS)
    source = (f' FROM (SELECT {projection},s.FSTOCKORGID AS organization_id,'
              f'{expression} AS product_line_name FROM dbo.YD_JIN_INVENTORY raw '
              'LEFT JOIN dbo.T_STK_INVENTORY s ON s.FID=raw.FID) v ')
    return source, params


def inventory_selection(query, organizations):
    source, source_params = inventory_source(query)
    where, params = where_clause(query, organizations)
    params = [*source_params, *params]
    if len(params) > 2000:
        raise ValueError('查询参数过多，请缩小范围')
    return source + where, params


def inventory_order(query):
    return f'v.[{query.sort}] {query.direction.upper()}' + ''.join(
        f',v.[{key}] ASC' for key in KEYS if key != query.sort)


def inventory_projection():
    return ','.join(f'v.[{key}]' for key in PUBLIC_KEYS)


def like(value):
    for char in ('~','%','_','['):
        value = value.replace(char, '~'+char)
    return '%'+value+'%'


def effective_organizations(query, authorized):
    if authorized is ALL_DATA_SCOPE:
        return [query.organization_id] if query.organization_id else ALL_DATA_SCOPE
    ids = sorted({value for value in (authorized or []) if type(value) is int and value > 0})
    return [query.organization_id] if query.organization_id in ids else [] if query.organization_id else ids


def where_clause(query, organizations):
    if organizations is None or organizations == []:
        return ' WHERE 1=0', []
    if organizations is not ALL_DATA_SCOPE and len(organizations) > 500:
        raise ValueError('组织范围超出上限')
    parts = ['1=1'] if organizations is ALL_DATA_SCOPE else ['EXISTS (SELECT 1 FROM dbo.T_STK_INVENTORY s WHERE s.FID=v.FID AND s.FSTOCKORGID IN ('+
             ','.join(['%s']*len(organizations))+'))']
    params = [] if organizations is ALL_DATA_SCOPE else list(organizations)
    if query.keyword.strip():
        parts.append('('+' OR '.join(f"v.[{key}] LIKE %s ESCAPE '~'" for key in ('MaterialCode','MaterialName','FSPECIFICATION'))+')')
        params.extend([like(query.keyword.strip())]*3)
    if query.stock:
        parts.append('v.Stock=%s'); params.append(query.stock)
    for f in query.conditions():
        if getattr(f, 'schemaVersion', 1) == 2:
            extra, bound = sql_conditions([f], alias='v')
            parts.append(extra)
            params.extend(bound)
            continue
        column = f'v.[{f.field}]'
        if f.operator in ('isEmpty','notEmpty'):
            is_empty = f.operator == 'isEmpty'
            if f.field == 'FBaseQty':
                parts.append(f'{column} IS ' + ('NULL' if is_empty else 'NOT NULL'))
            else:
                parts.append(f"({column} IS NULL OR {column}='')" if is_empty else f"({column} IS NOT NULL AND {column}<>'')")
            continue
        value = Decimal(str(f.value)) if f.field == 'FBaseQty' else str(f.value)
        if f.operator in ('contains','notContains','startsWith','endsWith'):
            pattern = like(value)
            if f.operator == 'startsWith': pattern = pattern[1:]
            if f.operator == 'endsWith': pattern = pattern[:-1]
            comparison = 'NOT LIKE' if f.operator == 'notContains' else 'LIKE'
            parts.append(f"{column} {comparison} %s ESCAPE '~'"); params.append(pattern)
        elif f.operator == 'between':
            parts.append(f'{column} BETWEEN %s AND %s'); params.extend([value,Decimal(str(f.valueEnd))])
        else:
            operator = {'equals':'=','notEquals':'<>','greaterThan':'>','greaterOrEqual':'>=','lessThan':'<','lessOrEqual':'<='}[f.operator]
            parts.append(f'{column}{operator}%s'); params.append(value)
    if len(params) > 2000:
        raise ValueError('查询参数过多，请缩小范围')
    return ' WHERE '+' AND '.join(parts), params


def list_inventory(connection, query, authorized):
    organizations = effective_organizations(query, authorized)
    if organizations == []:
        return {'items': [], 'total': 0}
    selection, params = inventory_selection(query, organizations)
    cursor = connection.cursor()
    try:
        cursor.execute('SELECT COUNT_BIG(*) AS total'+selection, tuple(params))
        total = int(cursor.fetchone()['total'])
        # Keep source rows, including duplicates; do not silently sum or deduplicate.
        cursor.execute('SELECT '+inventory_projection()+selection+
            ' ORDER BY '+inventory_order(query)+' OFFSET %s ROWS FETCH NEXT %s ROWS ONLY',
            tuple(params+[(query.page-1)*query.page_size,query.page_size]))
        return {'items': [public_row(row) for row in cursor.fetchall()], 'total': total}
    finally:
        cursor.close()


def list_options(connection, field, keyword, organizations):
    if field != 'Stock' or len(keyword) > 100:
        raise ValueError('候选字段或搜索无效')
    if organizations == []:
        return {'items': [], 'has_more': False}
    where, params = where_clause(InventoryQuery(), organizations)
    where += " AND v.Stock IS NOT NULL AND v.Stock<>'' AND v.Stock LIKE %s ESCAPE '~'"
    cursor = connection.cursor()
    try:
        cursor.execute('SELECT DISTINCT TOP (51) v.Stock AS value'+SOURCE+where+' ORDER BY v.Stock',tuple(params+[like(keyword)]))
        rows = cursor.fetchall()
        return {'items':[{'value':row['value'],'label':row['value']} for row in rows[:50]],'has_more':len(rows)>50}
    finally:
        cursor.close()
