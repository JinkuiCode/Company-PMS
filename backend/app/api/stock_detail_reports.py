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
from app.services.stock_detail_reader import StockDetailQuery, assemble_page, effective_organizations, list_candidates
from app.services.report_filters import filter_fields, STOCK_FILTER_SEMANTICS

router = APIRouter(prefix='/api/reports/stock-detail', tags=['物料收发明细'])


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
            result = assemble_page(query, dataset['rows'], dataset['openings'],
                opening_date=query.start_date, opening_labels=dataset['labels'])
    else:
        result = assemble_page(query, [], {}, opening_date=query.start_date)
    result['summary'] = quantity_summary(dataset)
    for row in [*result['items'], *result['openings'], *([result['summary']] if result['summary'] else [])]:
        for key, value in row.items():
            if isinstance(value, Decimal):
                row[key] = str(value)
    return {**result, 'queried_at': datetime.now(timezone.utc).isoformat()}


@router.get('/options')
def options(field: Literal['material', 'stock'], keyword: str = Query('', max_length=100),
            organization_id: int | None = Query(None, gt=0), db: Session = Depends(get_db),
            organization_ids: list[Annotated[int, Query(gt=0)]] = Query(default=[], max_length=200),
            ctx=Depends(require_permission('report:stock-detail:list'))):
    enforce_permission(ctx, 'report:stock-detail:view')
    if organization_id is not None and organization_ids:
        raise HTTPException(422, '请勿同时指定单组织和多组织条件')
    organizations = effective_organizations(SimpleNamespace(organization_id=organization_id,
        organization_ids=organization_ids), authorized_organizations(db, ctx))
    if organizations == []:
        return {'items': [], 'has_more': False}
    with stock_detail_connection() as connection:
        cursor = connection.cursor()
        try:
            return list_candidates(cursor, field, keyword, organizations)
        finally:
            cursor.close()
