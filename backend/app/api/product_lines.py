from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.product_line import SysProductLine
from app.schemas.product_line import ProductLineCreate, ProductLineUpdate
from app.services.authorization import require_permission, require_any_permission
from app.services.product_line import (list_product_lines, create_product_line, update_product_line,
                                       delete_product_line, snapshot)
from app.services.product_line_source import list_organizations, get_organization
from app.services.business_data_scope import has_all_business_data

router = APIRouter(prefix='/api/product-lines', tags=['产品线管理'])


@router.get('')
def list_lines(keyword: str = Query('', max_length=100), page: int = Query(1, ge=1),
               page_size: int = Query(50, ge=1, le=500), db: Session = Depends(get_db),
               context=Depends(require_permission('system:product-line:view'))):
    return list_product_lines(db, keyword, page, page_size)


@router.get('/organizations')
def organization_candidates(keyword: str = Query('', max_length=100), page: int = Query(1, ge=1),
                            page_size: int = Query(50, ge=1, le=100),
                            context=Depends(require_permission('system:product-line:add'))):
    return list_organizations(keyword, page, page_size)


@router.get('/options')
def business_options(db: Session = Depends(get_db), context=Depends(require_any_permission(
        'project:archive:view', 'project:archive:add', 'project:archive:edit', 'project:list:view',
        'project:list:add', 'project:list:edit'))):
    query = db.query(SysProductLine)
    if not has_all_business_data(context):
        query = query.filter(SysProductLine.id.in_(context.get('product_line_ids') or []))
    lines = query.order_by(SysProductLine.sort, SysProductLine.id).all()
    options = []
    for line in lines:
        if not line.is_enabled:
            continue
        try:
            get_organization(line.organization_id)
        except HTTPException as error:
            if error.status_code == 422:
                continue
            raise
        options.append({'value': line.id, 'label': line.display_name})
    return {'options': options, 'label_map': {str(line.id): line.display_name for line in lines}}


@router.post('')
def add_line(data: ProductLineCreate, db: Session = Depends(get_db),
             context=Depends(require_permission('system:product-line:add'))):
    organization = get_organization(data.organization_id)
    return snapshot(create_product_line(db, data, organization=organization, operator_id=context['user_id']))


@router.get('/role-options')
def role_options(db: Session = Depends(get_db), context=Depends(require_any_permission(
        'system:role:view', 'system:role:add', 'system:role:edit'))):
    rows = db.query(SysProductLine).order_by(SysProductLine.sort, SysProductLine.id).all()
    return {'items': [{'value': line.id, 'label': line.display_name, 'disabled': not bool(line.is_enabled)}
                      for line in rows]}


@router.put('/{line_id}')
def edit_line(line_id: int, data: ProductLineUpdate, db: Session = Depends(get_db),
              context=Depends(require_permission('system:product-line:edit'))):
    return snapshot(update_product_line(db, line_id, data, operator_id=context['user_id']))


@router.delete('/{line_id}')
def remove_line(line_id: int, db: Session = Depends(get_db),
                context=Depends(require_permission('system:product-line:delete'))):
    delete_product_line(db, line_id, operator_id=context['user_id'])
    return {'msg': '删除成功'}
