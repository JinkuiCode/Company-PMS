"""Validated request boundary. ERP source execution is not enabled yet."""
from datetime import date
from fastapi import HTTPException
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.services.business_data_scope import ALL_DATA_SCOPE
from app.services.stock_detail_fields import report_fields
from app.services.stock_detail_balance import quantity
from app.services.report_filters import parse_filters, parse_column_filters, matches_filters, STOCK_FILTER_SEMANTICS
from app.services.stock_detail_order import SORT_TYPES, display_movements


class StockDetailQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    filters: str = Field(default='[]', max_length=12000)
    column_filters: str = Field(default='[]', max_length=12000)

    material: str = Field(min_length=1, max_length=100)
    material_field: Literal['material_code', 'material_name', 'specification'] = 'material_code'
    material_operator: Literal['contains', 'equals', 'startsWith', 'endsWith'] = 'contains'
    start_date: date
    end_date: date
    organization_id: int | None = Field(default=None, gt=0)
    organization_ids: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list, max_length=200)
    stock_id: int | None = Field(default=None, gt=0)
    page: int = Field(default=1, ge=1, le=1000000)
    page_size: int = Field(default=50, ge=1, le=500)
    sort: str = Field(default='bill_date', max_length=100)
    direction: Literal['asc', 'desc'] = 'asc'

    @field_validator('sort')
    @classmethod
    def allowed_sort(cls, value):
        if value not in SORT_TYPES:
            raise ValueError('未知收发明细排序字段')
        return value

    @field_validator('material')
    @classmethod
    def require_material(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('请填写物料后再查询')
        return value

    @model_validator(mode='after')
    def date_order(self):
        self.conditions()
        if self.organization_id is None and not self.organization_ids:
            raise ValueError('请选择至少一个库存组织后再查询')
        if self.organization_id is not None and self.organization_ids:
            raise ValueError('请勿同时指定单组织和多组织条件')
        if self.start_date > self.end_date:
            raise ValueError('起始日期不得晚于截止日期')
        return self

    def conditions(self):
        return [*parse_filters(self.filters, 'stock-detail'),
                *self.column_conditions()]

    def column_conditions(self):
        return parse_column_filters(self.column_filters, 'stock-detail')


def effective_organizations(query, authorized):
    selected = sorted(set(getattr(query, 'organization_ids', []) or
                          ([query.organization_id] if query.organization_id else [])))
    if authorized is ALL_DATA_SCOPE:
        return selected
    ids = sorted({value for value in (authorized or []) if type(value) is int and value > 0})
    if selected:
        return [value for value in selected if value in ids]
    return []


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


def list_reference_candidates(cursor, kind, keyword, organizations, *, page=1, page_size=50,
                              ids=(), batch_field='code', batch_values=()):
    """Paged master identities for reference dialogs; preserve legacy lookup."""
    from app.services.query_conditions import scalar
    from app.services.purchase_reader import _like
    if kind not in {'stock', 'material'} or batch_field not in {'code', 'name'}:
        raise HTTPException(422, '引用候选字段无效')
    if not 1 <= page <= 1000000 or not 1 <= page_size <= 500 or len(keyword) > 100 or len(ids) > 1000 or len(batch_values) > 1000:
        raise HTTPException(422, '引用候选查询范围无效')
    if sum(bool(v) for v in (keyword.strip(), ids, batch_values)) > 1:
        raise HTTPException(422, '普通搜索、身份校验及精准批量查询不能混用')
    if organizations is not ALL_DATA_SCOPE and not organizations:
        if ids:
            raise HTTPException(422, '选中引用已失效或无权访问')
        return dict(items=[], total=0, page=page, page_size=page_size, has_more=False, batch=None)
    table, identity = ('T_BD_MATERIAL', 'FMATERIALID') if kind == 'material' else ('T_BD_STOCK', 'FSTOCKID')
    value = 'M.FNUMBER' if kind == 'material' else f'M.{identity}'
    group = 'M.FNUMBER' if kind == 'material' else f'M.{identity},M.FNUMBER'
    params = []
    where = '1=1'
    if organizations is not ALL_DATA_SCOPE:
        selected = sorted(set(organizations))
        if any(type(v) is not int or v <= 0 for v in selected) or len(selected) > 200:
            raise HTTPException(422, '组织范围无效')
        where = 'M.FUSEORGID IN (' + ','.join(['%s'] * len(selected)) + ')'
        params.extend(selected)
    choices = (f'SELECT {value} AS value,M.FNUMBER AS code,MIN(COALESCE(L.FNAME,M.FNUMBER)) AS label '
               f'FROM dbo.{table} M LEFT JOIN dbo.{table}_L L ON L.{identity}=M.{identity} AND L.FLOCALEID=2052 '
               f'WHERE {where} GROUP BY {group}')
    predicate = '1=1'
    normalized_ids, unique = [], {}
    try:
        if ids:
            if kind == 'material':
                normalized_ids = [scalar(v, 'text') for v in ids]
                compared = 'LOWER(LTRIM(RTRIM(value)))'
            else:
                if any(not str(v).isascii() or not str(v).isdigit() or not 0 < int(v) <= 9007199254740991 for v in ids):
                    raise ValueError()
                normalized_ids = [int(v) for v in ids]
                compared = 'value'
            predicate = compared + ' IN (' + ','.join(['%s'] * len(normalized_ids)) + ')'
            params.extend(normalized_ids)
        elif batch_values:
            if any(not isinstance(v, str) or any(c in v for c in '\t\r\n') for v in batch_values):
                raise ValueError()
            unique = dict(zip([scalar(v, 'text') for v in batch_values], batch_values))
            compared = 'code' if batch_field == 'code' else 'label'
            predicate = f'LOWER(LTRIM(RTRIM({compared}))) IN (' + ','.join(['%s'] * len(unique)) + ')'
            params.extend(unique)
        elif keyword.strip():
            predicate = "(code LIKE %s ESCAPE '~' OR label LIKE %s ESCAPE '~')"
            params.extend([_like(keyword.strip())] * 2)
    except (ValueError, TypeError):
        raise HTTPException(422, '引用键或单列精准查询文本无效') from None
    prefix = f'WITH source_choices AS ({choices}), choices AS (SELECT * FROM source_choices WHERE {predicate})'
    if ids:
        cursor.execute(prefix + ' SELECT value FROM choices', tuple(params))
        found = {str(r['value']).strip().lower() if kind == 'material' else r['value'] for r in cursor.fetchall()}
        if found != set(normalized_ids):
            raise HTTPException(422, '选中引用已失效或无权访问')
    batch = None
    if batch_values:
        cursor.execute(prefix + f' SELECT LOWER(LTRIM(RTRIM({compared}))) AS matched,COUNT(*) AS count FROM choices GROUP BY LOWER(LTRIM(RTRIM({compared})))', tuple(params))
        counts = {r['matched']: r['count'] for r in cursor.fetchall()}
        batch = dict(input_count=len(unique), duplicate_count=len(batch_values) - len(unique),
                     matched_records=sum(counts.values()),
                     unmatched_values=[v for key, v in unique.items() if key not in counts],
                     ambiguous_values=[v for key, v in unique.items() if counts.get(key, 0) > 1])
    cursor.execute(prefix + ' SELECT COUNT(*) AS total FROM choices', tuple(params))
    total = cursor.fetchall()[0]['total']
    start = (page - 1) * page_size
    cursor.execute(prefix + ', numbered AS (SELECT *,ROW_NUMBER() OVER (ORDER BY code,value) AS n FROM choices) SELECT value,code,label FROM numbered WHERE n>%s AND n<=%s ORDER BY n', tuple([*params, start, start + page_size]))
    return dict(items=cursor.fetchall(), total=total, page=page, page_size=page_size,
                has_more=page * page_size < total, batch=batch)


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
    start = (query.page - 1) * query.page_size
    movements = display_movements(ordered, verified_openings, conditions=query.conditions(),
                                 sort=query.sort, direction=query.direction)
    total = len(movements)
    items = [{**{key: row.get(key) for key in fields}, 'row_id': row['row_id'],
              'row_kind': 'movement'} for row in movements[start:start + query.page_size]]
    openings = []
    for index, (key, value) in enumerate(verified_openings.items()):
        value = quantity(value)
        openings.append({**{name: labels.get(key, {}).get(name) for name in descriptive},
                         'row_id': f'opening:{index}', 'row_kind': 'opening',
                         'bill_date': query.start_date, 'bill_name': '期初',
                         'bill_no': None, 'bill_seq': None, 'opening_qty': value,
                         'income_qty': None, 'issue_qty': None, 'balance_qty': value})
    openings = [row for row in openings if matches_filters(row, query.column_conditions())]
    return {'items': items, 'openings': openings, 'total': total,
            'filter_semantics': dict(STOCK_FILTER_SEMANTICS),
            'page': query.page, 'page_size': query.page_size}
