import csv
import io
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.product_line import SysProductLine
from app.services.authorization import require_permission, enforce_permission
from app.services.inventory_reader import (InventoryQuery, report_fields, public_row, list_inventory,
    list_options, effective_organizations, EXPORT_LIMIT)
from app.services.purchase_connection import purchase_connection
from app.services.operation_log import record_operation_log

router = APIRouter(prefix='/api/reports/inventory', tags=['即时库存查询'])


def scoped_lines(db, ctx):
    return db.query(SysProductLine).filter(SysProductLine.source_key=='kingdee',
        SysProductLine.id.in_(ctx.get('product_line_ids') or [])).order_by(SysProductLine.sort,SysProductLine.id).all()


@contextmanager
def inventory_connection():
    try:
        with purchase_connection() as connection:
            yield connection
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503,'库存查询失败或超时，请重试；持续失败请联系管理员检查只读数据源') from None


@router.get('/metadata')
def metadata(db: Session=Depends(get_db),ctx=Depends(require_permission('report:inventory:view'))):
    return {'fields':report_fields(),'export_limit':EXPORT_LIMIT,
        'organizations':[{'value':line.organization_id,'label':line.display_name} for line in scoped_lines(db,ctx)]}


def query_rows(query,db,ctx):
    organizations=effective_organizations(query,[line.organization_id for line in scoped_lines(db,ctx)])
    if not organizations:
        return {'items':[],'total':0}
    with inventory_connection() as connection:
        return list_inventory(connection,query,organizations)


@router.get('')
def listing(query: Annotated[InventoryQuery,Query()],db: Session=Depends(get_db),
            ctx=Depends(require_permission('report:inventory:view'))):
    result=query_rows(query,db,ctx)
    return {**result,'queried_at':datetime.now(timezone.utc).isoformat()}


@router.get('/options')
def options(field: Literal['Stock'],keyword: str=Query('',max_length=100),
            organization_id: int | None=Query(None,gt=0),db: Session=Depends(get_db),
            ctx=Depends(require_permission('report:inventory:view'))):
    organizations=effective_organizations(InventoryQuery(organization_id=organization_id),
        [line.organization_id for line in scoped_lines(db,ctx)])
    if not organizations:
        return {'items':[],'has_more':False}
    with inventory_connection() as connection:
        return list_options(connection,field,keyword,organizations)


def csv_cell(value):
    value='' if value is None else str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')) else value


@router.get('/export')
def export(request: Request,query: Annotated[InventoryQuery,Query()],db: Session=Depends(get_db),
           ctx=Depends(require_permission('report:inventory:export'))):
    enforce_permission(ctx,'report:inventory:view')
    result=query_rows(query.model_copy(update={'page':1,'page_size':EXPORT_LIMIT}),db,ctx)
    if result['total']>EXPORT_LIMIT:
        raise HTTPException(422,'单次最多导出500条，请缩小筛选范围')
    output=io.StringIO(newline='');writer=csv.writer(output);fields=report_fields()
    writer.writerow([f['label'] for f in fields])
    for raw in result['items']:
        row=public_row(raw)
        writer.writerow([csv_cell(row.get(f['key'])) for f in fields])
    record_operation_log(db,module='即时库存查询',action='export',entity_type='inventory_report',
        operator_id=ctx['user_id'],request=request,summary=f"导出即时库存 {result['total']} 条",
        after_data={'filters':query.model_dump(mode='json'),'row_count':result['total']},commit=True)
    return Response(content=('\ufeff'+output.getvalue()).encode(),media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition':'attachment; filename="inventory.csv"','Cache-Control':'no-store'})
