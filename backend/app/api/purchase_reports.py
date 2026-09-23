from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated, Literal
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import PmsProjectArchive
from app.models.product_line import SysProductLine
from app.services.authorization import require_permission, enforce_permission
from app.services.project import get_scoped_archive_query
from app.services.purchase_connection import purchase_connection
from app.services.purchase_reader import PurchaseQuery, ProjectOrganizationGrant, load_request, load_chains, list_requests, list_options, REPORT_START_DATE
from app.services.purchase_fields import report_fields, DOCUMENT_STATUSES, PROGRESS_LABELS

router = APIRouter(prefix='/api/reports/purchase', tags=['采购进度查询'])


def project_scope(db, ctx):
    from app.services.business_data_scope import has_all_business_data, ALL_DATA_SCOPE
    if has_all_business_data(ctx):
        return ALL_DATA_SCOPE
    return [ProjectOrganizationGrant(code, organization_id)
            for code, organization_id in get_scoped_archive_query(db, ctx)
            .join(SysProductLine, SysProductLine.id == PmsProjectArchive.business_product_line_id)
            .filter(SysProductLine.source_key == 'kingdee')
            .with_entities(PmsProjectArchive.project_code, SysProductLine.organization_id)
            .order_by(PmsProjectArchive.project_code).all()]


@contextmanager
def report_connection():
    try:
        with purchase_connection() as connection:
            yield connection
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(422, '查询范围超出限制，请缩小查询范围或联系管理员') from None
    except Exception:
        raise HTTPException(503, '采购报表查询失败或超时，请稍后重试；持续失败请联系管理员检查只读数据源') from None


def public_row(row):
    keys = {field['key'] for field in report_fields()} | {'id', 'bill_id'}
    result = {key: str(value) if isinstance(value, Decimal) else value for key, value in row.items() if key in keys}
    result['document_status_label'] = DOCUMENT_STATUSES.get(row.get('document_status'), '未知状态')
    result['progress_label'] = PROGRESS_LABELS.get(row.get('progress'), '数据待核对')
    return result


def enrich_project_names(db, ctx, rows):
    codes = {row.get('project_code') for row in rows if row.get('project_code')}
    names = dict(get_scoped_archive_query(db, ctx).with_entities(PmsProjectArchive.project_code,
        PmsProjectArchive.project_name).filter(PmsProjectArchive.project_code.in_(codes)).all()) if codes else {}
    for row in rows:
        row['project_name'] = names.get(row.get('project_code'))


@router.get('/metadata')
def metadata(ctx: dict = Depends(require_permission('report:purchase:view'))):
    return dict(fields=report_fields(), progress_labels=PROGRESS_LABELS, document_status_labels=DOCUMENT_STATUSES,
                start_date=REPORT_START_DATE.isoformat())


@router.get('')
def listing(query: Annotated[PurchaseQuery, Query()], db: Session = Depends(get_db),
            ctx: dict = Depends(require_permission('report:purchase:view'))):
    codes = project_scope(db, ctx)
    with report_connection() as connection:
        result = list_requests(connection, query, codes)
    result['items'] = [public_row(row) for row in result['items']]
    enrich_project_names(db, ctx, result['items'])
    result['queried_at'] = datetime.now(timezone.utc).isoformat()
    return result


@router.get('/options')
def options(field: Literal['project', 'supplier'], keyword: str = Query('', max_length=100),
            db: Session = Depends(get_db), ctx: dict = Depends(require_permission('report:purchase:view'))):
    with report_connection() as connection:
        return list_options(connection, field, keyword, project_scope(db, ctx))


def ensure_export_permission(ctx):
    enforce_permission(ctx, 'report:purchase:view')
    enforce_permission(ctx, 'report:purchase:export')


@router.get('/export')
def export(request: Request, query: Annotated[PurchaseQuery, Query()], db: Session = Depends(get_db),
           ctx: dict = Depends(require_permission('report:purchase:export'))):
    ensure_export_permission(ctx)
    raise HTTPException(410, '导出已升级为后台Excel任务，请刷新页面后使用导出按钮')


@router.get('/{request_id}')
def detail(request_id: int = Path(ge=1), db: Session = Depends(get_db),
           ctx: dict = Depends(require_permission('report:purchase:view'))):
    codes = project_scope(db, ctx)
    with report_connection() as connection:
        row = load_request(connection, request_id, codes)
        if not row:
            raise HTTPException(404, '申请明细不存在或无权访问')
        chain = load_chains(connection, [row])[row['id']]
    enrich_project_names(db, ctx, [row])
    # Do not expose other requisitions' IDs or source allocations used internally.
    return jsonable_encoder(dict(request=public_row(row), **chain, queried_at=datetime.now(timezone.utc).isoformat()),
                            custom_encoder={Decimal: str})
