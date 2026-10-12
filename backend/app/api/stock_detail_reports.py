from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.authorization import require_permission, enforce_permission
from app.services.purchase_connection import purchase_connection
from app.api.inventory_reports import authorized_organizations, scoped_lines
from app.services.stock_detail_fields import report_fields
from app.services.stock_detail_fetch import read_dataset
from app.services.stock_detail_engine import quantity_summary
from app.services.stock_detail_reader import StockDetailQuery, assemble_page, effective_organizations, list_candidates, list_reference_candidates
from app.services.report_filters import filter_fields, query_fields, matches_filters, STOCK_FILTER_SEMANTICS

router = APIRouter(prefix='/api/reports/stock-detail', tags=['物料收发明细'])


def enrich_stock_product_lines(db, connection, dataset):
    from app.api.purchase_reports import enrich_product_lines
    keys = dict.fromkeys([*dataset['openings'], *(row['inventory_key'] for row in dataset['rows'])])
    if not keys:
        return
    rows = [{'organization_id': org} for org in sorted({key.organization_id for key in keys})]
    enrich_product_lines(db, connection, rows)
    names = {row['organization_id']: row['product_line_name'] for row in rows}
    for key in keys:
        dataset['labels'].setdefault(key, {})['product_line_name'] = names[key.organization_id]
    for row in dataset['rows']:
        row['product_line_name'] = names[row['inventory_key'].organization_id]


@contextmanager
def stock_detail_connection():
    try:
        with purchase_connection() as connection:
            yield connection
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, '物料收发查询未完成，请重试；持续失败请联系管理员检查数据源及库存期初') from None


@router.get('/metadata')
def metadata(db: Session = Depends(get_db), ctx=Depends(require_permission('report:stock-detail:list'))):
    return {'fields': report_fields(), 'filter_fields': filter_fields('stock-detail'),
        'query_fields': query_fields('stock-detail'), 'column_filter_fields': query_fields('stock-detail'),
        'query_schema_version': 2,
        'sort_fields': [field['key'] for field in report_fields()],
        'default_sort': {'sort': 'bill_date', 'direction': 'asc'},
        'sort_semantics': 'display_after_full_running_balance_nulls_last_openings_pinned',
        'filter_semantics': dict(STOCK_FILTER_SEMANTICS),
        'summary_scope_note': '完整期间汇总（不随附加条件重算）',
        'opening_scope_note': '期初保留完整查询范围（不随附加条件筛选）',
        'organizations': [
        {'value': line.organization_id, 'label': line.display_name} for line in scoped_lines(db, ctx)]}


@router.get('')
def listing(query: Annotated[StockDetailQuery, Query()], db: Session = Depends(get_db),
            ctx=Depends(require_permission('report:stock-detail:list'))):
    enforce_permission(ctx, 'report:stock-detail:view')
    organizations = effective_organizations(query, authorized_organizations(db, ctx))
    dataset = dict(rows=[], openings={}, labels={})
    if organizations != []:
        with stock_detail_connection() as connection:
            dataset = read_dataset(connection, query, organizations)
            enrich_stock_product_lines(db, connection, dataset)
            result = assemble_page(query, dataset['rows'], dataset['openings'],
                opening_date=query.start_date, opening_labels=dataset['labels'])
    else:
        result = assemble_page(query, [], {}, opening_date=query.start_date)
    result['summary'] = quantity_summary(dataset)
    if result['summary'] and not matches_filters(result['summary'], query.column_conditions()):
        result['summary'] = None
    for row in [*result['items'], *result['openings'], *([result['summary']] if result['summary'] else [])]:
        for key, value in row.items():
            if isinstance(value, Decimal):
                row[key] = str(value)
    return {**result, 'queried_at': datetime.now(timezone.utc).isoformat()}


@router.get('/options')
def options(field: Literal['material', 'stock'], keyword: str = Query('', max_length=100),
            organization_id: int | None = Query(None, gt=0), db: Session = Depends(get_db),
            organization_ids: list[Annotated[int, Query(gt=0)]] = Query(default=[], max_length=200),
            page: int | None = Query(None, ge=1, le=1000000), page_size: int = Query(50, ge=1, le=200),
            ids: list[str] = Query(default=[], max_length=1000),
            batch_field: Literal['code', 'name'] = 'code', batch_values: list[str] = Query(default=[], max_length=1000),
            ctx=Depends(require_permission('report:stock-detail:list'))):
    enforce_permission(ctx, 'report:stock-detail:view')
    if organization_id is not None and organization_ids:
        raise HTTPException(422, '请勿同时指定单组织和多组织条件')
    organizations = effective_organizations(SimpleNamespace(organization_id=organization_id,
        organization_ids=organization_ids), authorized_organizations(db, ctx))
    if organizations == []:
        if ids:
            raise HTTPException(422, '选中引用已失效或无权访问')
        if page is not None or batch_values:
            return dict(items=[], total=0, has_more=False, page=page or 1, page_size=page_size)
        return {'items': [], 'has_more': False}
    with stock_detail_connection() as connection:
        cursor = connection.cursor()
        try:
            if page is not None or ids or batch_values:
                return list_reference_candidates(cursor, field, keyword, organizations,
                    page=page or 1, page_size=page_size, ids=ids, batch_field=batch_field, batch_values=batch_values)
            return list_candidates(cursor, field, keyword, organizations)
        finally:
            cursor.close()


@router.get('/column-options')
def column_options(field: str = Query(max_length=100), keyword: str = Query('', max_length=100),
                   page: int = Query(1, ge=1, le=1000000), page_size: int = Query(50, ge=1, le=200),
                   parameters: str = Query('{}', max_length=36000), column_filters: str | None = Query(None, max_length=12000),
                   db: Session = Depends(get_db), ctx=Depends(require_permission('report:stock-detail:list'))):
    from app.services.report_column_candidates import request_query, candidate_query, stock_candidates
    enforce_permission(ctx, 'report:stock-detail:view')
    query = request_query(StockDetailQuery, parameters, column_filters)
    try:
        candidate_query(query, 'stock-detail', field, keyword, page, page_size)
    except ValueError:
        raise HTTPException(422, '该列尚不支持候选查询或参数无效') from None
    organizations = effective_organizations(query, authorized_organizations(db, ctx))
    if organizations == []:
        return dict(items=[], total=0, page=page, page_size=page_size, has_more=False)
    with stock_detail_connection() as connection:
        dataset = read_dataset(connection, query, organizations)
        enrich_stock_product_lines(db, connection, dataset)
    return stock_candidates(query, dataset, field, keyword, page, page_size)
