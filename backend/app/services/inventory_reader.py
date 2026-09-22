"""Bounded, parameterized reads of the inventory view, scoped by stable org IDs."""
import json
from decimal import Decimal, InvalidOperation
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.services.inventory_fields import FIELDS, report_fields

KEYS = tuple(row[0] for row in FIELDS)
SOURCE = ' FROM dbo.YD_JIN_INVENTORY v '


class Condition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    field: str
    operator: Literal['contains','equals','notEquals','greaterThan','lessThan','between']
    value: str | int | float
    valueEnd: str | int | float | None = None

    @model_validator(mode='after')
    def validate_condition(self):
        if self.field not in KEYS or self.field == 'FID':
            raise ValueError('未知筛选字段')
        if self.field == 'FBaseQty':
            if self.operator not in ('equals','greaterThan','lessThan','between'):
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
        elif self.operator not in ('contains','equals','notEquals') or len(str(self.value)) > 256:
            raise ValueError('文本筛选无效')
        return self


class InventoryQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    keyword: str = Field(default='', max_length=100)
    organization_id: int | None = Field(default=None, gt=0)
    stock: str = Field(default='', max_length=256)
    filters: str = Field(default='[]', max_length=12000)
    page: int = Field(default=1, ge=1, le=1000000)
    page_size: int = Field(default=50, ge=1, le=500)
    sort: str = 'FID'
    direction: Literal['asc','desc'] = 'asc'

    @model_validator(mode='after')
    def validate_query(self):
        if self.sort not in KEYS:
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
        return [Condition.model_validate(value) for value in values]


def public_row(row):
    return {key: str(row[key]) if isinstance(row[key], Decimal) else row[key]
            for key in KEYS if key in row}


def like(value):
    for char in ('~','%','_','['):
        value = value.replace(char, '~'+char)
    return '%'+value+'%'


def effective_organizations(query, authorized):
    ids = sorted({value for value in authorized if type(value) is int and value > 0})
    return [query.organization_id] if query.organization_id in ids else [] if query.organization_id else ids


def where_clause(query, organizations):
    if not organizations:
        return ' WHERE 1=0', []
    if len(organizations) > 500:
        raise ValueError('组织范围超出上限')
    parts = ['EXISTS (SELECT 1 FROM dbo.T_STK_INVENTORY s WHERE s.FID=v.FID AND s.FSTOCKORGID IN ('+
             ','.join(['%s']*len(organizations))+'))']
    params = list(organizations)
    if query.keyword.strip():
        parts.append('('+' OR '.join(f"v.[{key}] LIKE %s ESCAPE '~'" for key in ('MaterialCode','MaterialName','FSPECIFICATION'))+')')
        params.extend([like(query.keyword.strip())]*3)
    if query.stock:
        parts.append('v.Stock=%s'); params.append(query.stock)
    for f in query.conditions():
        column = f'v.[{f.field}]'
        value = Decimal(str(f.value)) if f.field == 'FBaseQty' else str(f.value)
        if f.operator == 'contains':
            parts.append(f"{column} LIKE %s ESCAPE '~'"); params.append(like(value))
        elif f.operator == 'between':
            parts.append(f'{column} BETWEEN %s AND %s'); params.extend([value,Decimal(str(f.valueEnd))])
        else:
            operator = {'equals':'=','notEquals':'<>','greaterThan':'>','lessThan':'<'}[f.operator]
            parts.append(f'{column}{operator}%s'); params.append(value)
    return ' WHERE '+' AND '.join(parts), params


def list_inventory(connection, query, authorized):
    organizations = effective_organizations(query, authorized)
    if not organizations:
        return {'items': [], 'total': 0}
    where, params = where_clause(query, organizations)
    cursor = connection.cursor()
    try:
        cursor.execute('SELECT COUNT_BIG(*) AS total'+SOURCE+where, tuple(params))
        total = int(cursor.fetchone()['total'])
        # Keep source rows, including duplicates; do not silently sum or deduplicate.
        ordering = f'v.[{query.sort}] {query.direction.upper()}'
        ordering += ''.join(f',v.[{key}] ASC' for key in KEYS if key != query.sort)
        cursor.execute('SELECT '+','.join(f'v.[{key}]' for key in KEYS)+SOURCE+where+
            ' ORDER BY '+ordering+' OFFSET %s ROWS FETCH NEXT %s ROWS ONLY',
            tuple(params+[(query.page-1)*query.page_size,query.page_size]))
        return {'items': [public_row(row) for row in cursor.fetchall()], 'total': total}
    finally:
        cursor.close()


def list_options(connection, field, keyword, organizations):
    if field != 'Stock' or len(keyword) > 100:
        raise ValueError('候选字段或搜索无效')
    if not organizations:
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
