from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.product_line import SysProductLine
from app.services.authorization import require_permission, enforce_permission
from app.services.inventory_reader import (InventoryQuery, report_fields, list_inventory,
    list_options, effective_organizations, resolve_product_lines)
from app.services.purchase_connection import purchase_connection
from app.services.business_data_scope import has_all_business_data, ALL_DATA_SCOPE
from app.services.report_filters import query_fields
from app.services.report_material_reference import list_material_candidates, material_organizations, validate_reference_query

router = APIRouter(prefix='/api/reports/inventory', tags=['即时库存查询'])


def scoped_lines(db, ctx):
    query = db.query(SysProductLine).filter(SysProductLine.source_key=='kingdee')
    if not has_all_business_data(ctx):
        query = query.filter(SysProductLine.id.in_(ctx.get('product_line_ids') or []))
    return query.order_by(SysProductLine.sort,SysProductLine.id).all()


def authorized_organizations(db, ctx):
    return ALL_DATA_SCOPE if has_all_business_data(ctx) else [line.organization_id for line in scoped_lines(db, ctx)]


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
    return {'fields':report_fields(), 'query_fields':query_fields('inventory'),
        'column_filter_fields':query_fields('inventory'), 'query_schema_version':2,
        'organizations':[{'value':line.organization_id,'label':line.display_name} for line in scoped_lines(db,ctx)]}


def query_rows(query,db,ctx):
    organizations=effective_organizations(query,authorized_organizations(db,ctx))
    if organizations == []:
        validate_reference_query(None, query, organizations)
        return {'items':[],'total':0}
    resolve_product_lines(db, query)
    with inventory_connection() as connection:
        validate_reference_query(connection, query, organizations)
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
        authorized_organizations(db,ctx))
    if organizations == []:
        return {'items':[],'has_more':False}
    with inventory_connection() as connection:
        return list_options(connection,field,keyword,organizations)


@router.get('/material-reference-options')
def material_reference_options(keyword: str=Query('',max_length=100),
        organization_id: int | None=Query(None,gt=0),
        page: int=Query(1,ge=1,le=1000000), page_size: int=Query(50,ge=1,le=500),
        ids: list[str]=Query(default=[],max_length=1000), batch_field: Literal['code','name']='code',
        batch_values: list[str]=Query(default=[],max_length=1000),
        db: Session=Depends(get_db),ctx=Depends(require_permission('report:inventory:view'))):
    organizations=material_organizations([organization_id] if organization_id else [],authorized_organizations(db,ctx))
    if organizations == []:
        return list_material_candidates(None,keyword,organizations,page=page,page_size=page_size,ids=ids,batch_field=batch_field,batch_values=batch_values)
    with inventory_connection() as connection:
        cursor=connection.cursor()
        try:
            return list_material_candidates(cursor,keyword,organizations,page=page,page_size=page_size,ids=ids,batch_field=batch_field,batch_values=batch_values)
        finally:
            cursor.close()


@router.get('/export')
def export(request: Request,query: Annotated[InventoryQuery,Query()],db: Session=Depends(get_db),
           ctx=Depends(require_permission('report:inventory:export'))):
    enforce_permission(ctx,'report:inventory:view')
    raise HTTPException(410, '导出已升级为后台Excel任务，请刷新页面后使用导出按钮')


@router.get('/column-options')
def column_options(field: str = Query(max_length=100), keyword: str = Query('', max_length=100),
                   page: int = Query(1, ge=1, le=1000000), page_size: int = Query(50, ge=1, le=200),
                   parameters: str = Query('{}', max_length=36000), column_filters: str | None = Query(None, max_length=12000),
                   db: Session = Depends(get_db), ctx=Depends(require_permission('report:inventory:view'))):
    from app.services.report_column_candidates import request_query, candidate_query, inventory_candidates
    query = request_query(InventoryQuery, parameters, column_filters)
    try:
        candidate_query(query, 'inventory', field, keyword, page, page_size)
    except ValueError:
        raise HTTPException(422, '该列尚不支持候选查询或参数无效') from None
    organizations = effective_organizations(query, authorized_organizations(db, ctx))
    if organizations == []:
        return dict(items=[], total=0, page=page, page_size=page_size, has_more=False)
    resolve_product_lines(db, query)
    with inventory_connection() as connection:
        validate_reference_query(connection, query, organizations)
        return inventory_candidates(connection, query, organizations, field, keyword, page, page_size)
