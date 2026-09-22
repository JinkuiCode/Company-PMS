from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.product_line import SysProductLine
from app.services.authorization import require_permission, enforce_permission
from app.services.inventory_reader import (InventoryQuery, report_fields, list_inventory,
    list_options, effective_organizations)
from app.services.purchase_connection import purchase_connection

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
    return {'fields':report_fields(),
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


@router.get('/export')
def export(request: Request,query: Annotated[InventoryQuery,Query()],db: Session=Depends(get_db),
           ctx=Depends(require_permission('report:inventory:export'))):
    enforce_permission(ctx,'report:inventory:view')
    raise HTTPException(410, '导出已升级为后台Excel任务，请刷新页面后使用导出按钮')
