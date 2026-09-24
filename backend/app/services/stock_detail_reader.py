"""Validated request boundary. ERP source execution is not enabled yet."""
from datetime import date
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.services.business_data_scope import ALL_DATA_SCOPE
from app.services.stock_detail_fields import report_fields
from app.services.stock_detail_balance import quantity, running_balances


class StockDetailQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')

    material: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date
    organization_id: int | None = Field(default=None, gt=0)
    organization_ids: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list, max_length=200)
    stock_id: int | None = Field(default=None, gt=0)
    page: int = Field(default=1, ge=1, le=1000000)
    page_size: int = Field(default=50, ge=1, le=500)

    @field_validator('material')
    @classmethod
    def require_material(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('请填写物料后再查询')
        return value

    @model_validator(mode='after')
    def date_order(self):
        if self.organization_id is not None and self.organization_ids:
            raise ValueError('请勿同时指定单组织和多组织条件')
        if self.start_date > self.end_date:
            raise ValueError('起始日期不得晚于截止日期')
        return self


def effective_organizations(query, authorized):
    selected = sorted(set(getattr(query, 'organization_ids', []) or
                          ([query.organization_id] if query.organization_id else [])))
    if authorized is ALL_DATA_SCOPE:
        return selected or ALL_DATA_SCOPE
    ids = sorted({value for value in (authorized or []) if type(value) is int and value > 0})
    if selected:
        return [value for value in selected if value in ids]
    return ids


def list_candidates(cursor, kind, keyword, organizations):
    """Historical lookup includes disabled masters and zero-stock warehouses.

    Fixed table/column choices, Chinese locale, and bound search values keep
    candidate lookup within the same organization boundary as report rows.
    """
    if kind not in ('material', 'stock'):
        raise ValueError('未知候选类型')
    params = []
    predicates = []
    if organizations is not ALL_DATA_SCOPE:
        ids = list(organizations or [])
        if any(type(value) is not int or value <= 0 for value in ids):
            raise ValueError('组织范围无效')
        if not ids:
            return {'items': [], 'has_more': False}
        ids = sorted(set(ids))
        predicates.append('M.FUSEORGID IN (' + ','.join(['%s'] * len(ids)) + ')')
        params.extend(ids)
    if not isinstance(keyword, str) or len(keyword) > 100:
        raise ValueError('搜索内容无效')
    keyword = keyword.strip()
    if keyword:
        escaped = keyword.replace('[', '[[]').replace('%', '[%]').replace('_', '[_]')
        predicates.append('(M.FNUMBER LIKE %s OR L.FNAME LIKE %s)')
        params.extend(['%' + escaped + '%'] * 2)
    table, identity = ('T_BD_MATERIAL', 'FMATERIALID') if kind == 'material' else ('T_BD_STOCK', 'FSTOCKID')
    value = 'M.FNUMBER' if kind == 'material' else f'M.{identity}'
    group = 'M.FNUMBER' if kind == 'material' else f'M.{identity}, M.FNUMBER'
    order = 'M.FNUMBER' if kind == 'material' else f'M.FNUMBER, M.{identity}'
    where = ' AND '.join(predicates) or '1=1'
    cursor.execute(f'''SELECT TOP (101) {value} AS value, M.FNUMBER AS code,
        MIN(COALESCE(L.FNAME, M.FNUMBER)) AS label
        FROM dbo.{table} M LEFT JOIN dbo.{table}_L L
          ON L.{identity}=M.{identity} AND L.FLOCALEID=2052
        WHERE {where} GROUP BY {group} ORDER BY {order}''', params)
    rows = cursor.fetchall()
    return {'items': rows[:100], 'has_more': len(rows) > 100}


def assemble_page(query, rows, verified_openings, *, opening_date, opening_labels=None):
    """Page only after computing every in-period movement, never a SQL page.

    The source reader supplies start-of-day openings and a complete, scoped
    period. Missing or duplicate source rows are errors, not zero quantities.
    Raw source attributes must not escape the public field allowlist.
    """
    if opening_date != query.start_date:
        raise ValueError('期初日期与查询开始日期不一致')
    ordered = list(rows)
    identities = set()
    labels = dict(opening_labels or {})
    fields = {field['key'] for field in report_fields()}
    descriptive = fields - {'opening_qty', 'income_qty', 'issue_qty', 'balance_qty',
                            'bill_date', 'bill_name', 'bill_no', 'bill_seq'}
    for row in ordered:
        if not query.start_date <= row['bill_date'] <= query.end_date:
            raise ValueError('流水日期超出查询范围')
        identity = row['row_id']
        if not isinstance(identity, str) or not identity:
            raise ValueError('流水标识无效')
        if identity in identities:
            raise ValueError('来源流水重复，禁止重复累计')
        identities.add(identity)
        labels.setdefault(row['inventory_key'], {key: row.get(key) for key in descriptive})
    ordered.sort(key=lambda row: (row['bill_date'], row['source_order'],
                                  row['created_at'], row['bill_no'],
                                  row['bill_seq'], row['row_id']))
    start = (query.page - 1) * query.page_size
    items = []
    for index, row in enumerate(running_balances(ordered, verified_openings)):
        if start <= index < start + query.page_size:
            items.append({**{key: row.get(key) for key in fields},
                          'row_id': row['row_id'], 'row_kind': 'movement'})
    openings = []
    for index, (key, value) in enumerate(verified_openings.items()):
        value = quantity(value)
        openings.append({**{name: labels.get(key, {}).get(name) for name in descriptive},
                         'row_id': f'opening:{index}', 'row_kind': 'opening',
                         'bill_date': query.start_date, 'bill_name': '期初',
                         'bill_no': None, 'bill_seq': None, 'opening_qty': value,
                         'income_qty': None, 'issue_qty': None, 'balance_qty': value})
    return {'items': items, 'openings': openings, 'total': len(ordered),
            'page': query.page, 'page_size': query.page_size}
