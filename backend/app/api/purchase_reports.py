from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated, Literal
from decimal import Decimal
import json
from pydantic import Field

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.core.database import get_db
from app.models.project import PmsProjectArchive
from app.models.product_line import SysProductLine
from app.api.inventory_reports import authorized_organizations, scoped_lines
from app.services.authorization import require_permission, enforce_permission
from app.services.project import get_scoped_archive_query
from app.services.purchase_connection import purchase_connection
from app.services.purchase_reader import PurchaseQuery, PurchaseOverviewQuery, OrganizationGrant, load_request, load_chains, list_requests, list_overview, list_options, REPORT_START_DATE, _rows
from app.services.purchase_fields import report_fields, overview_fields, DOCUMENT_STATUSES, PROGRESS_LABELS
from app.services.report_filters import filter_fields, query_fields
from app.services.query_conditions import build_query_clause, scalar
from app.services.purchase_query_labels import resolve_query_labels
from app.services.report_material_reference import list_material_candidates, material_organizations, validate_reference_query

router = APIRouter(prefix='/api/reports/purchase', tags=['采购进度查询'])


def project_scope(db, ctx):
    from app.services.business_data_scope import ALL_DATA_SCOPE
    organizations = authorized_organizations(db, ctx)
    if organizations is ALL_DATA_SCOPE:
        return ALL_DATA_SCOPE
    return [OrganizationGrant(value) for value in sorted(set(organizations))]


def resolve_project_references(db, ctx, query):
    """Browser archive IDs are not grants; resolve again on list/export execution."""
    query._project_references = {}
    ids = {key for c in [*query.conditions(), *query.column_conditions()]
           if c.kind == 'project-reference' for key in c.value}
    if not ids:
        return query
    rows = (get_scoped_archive_query(db, ctx)
        .join(SysProductLine, SysProductLine.id == PmsProjectArchive.business_product_line_id)
        .with_entities(PmsProjectArchive.id, PmsProjectArchive.project_code, SysProductLine.organization_id)
        .filter(PmsProjectArchive.id.in_(ids), SysProductLine.source_key == 'kingdee').all())
    resolved = {key: (code, organization) for key, code, organization in rows
                if code and type(organization) is int and organization > 0}
    if (set(resolved) != ids or len(set(resolved.values())) != len(resolved) or
            query.organization_ids and any(org not in query.organization_ids for _, org in resolved.values())):
        raise HTTPException(422, '项目引用失效、无权访问或与所选产品线组织不一致，请重新选择')
    query._project_references = resolved
    return query


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
    names = (get_scoped_archive_query(db, ctx)
        .outerjoin(SysProductLine, SysProductLine.id == PmsProjectArchive.business_product_line_id)
        .with_entities(PmsProjectArchive.project_code, SysProductLine.organization_id,
                       SysProductLine.source_key, PmsProjectArchive.project_name)
        .filter(PmsProjectArchive.project_code.in_(codes)).all()) if codes else []
    pairs = {(code,org): name for code,org,source,name in names if source == 'kingdee'}
    legacy = {code:name for code,org,source,name in names}
    for row in rows:
        row['project_name'] = (pairs.get((row.get('project_code'),row['organization_id']))
                               if 'organization_id' in row else legacy.get(row.get('project_code')))


def enrich_product_lines(db, connection, rows):
    """Label only already-authorized requisitions, including unmapped organizations."""
    ids = {row['organization_id'] for row in rows if row.get('organization_id')}
    if not ids:
        return
    names = dict(db.query(SysProductLine.organization_id, SysProductLine.display_name).filter(
        SysProductLine.source_key == 'kingdee', SysProductLine.organization_id.in_(ids)).all())
    missing = sorted(ids - names.keys())
    if missing:
        organizations = _rows(connection,
            'SELECT FORGID AS id,FNAME AS name FROM dbo.T_ORG_ORGANIZATIONS_L '
            'WHERE FLOCALEID=2052 AND FORGID IN (' + ','.join(['%s'] * len(missing)) + ')', missing)
        source_names = {row['id']: row['name'] for row in organizations}
        names.update({id: f'{source_names.get(id) or "组织 " + str(id)}（未配置产品线）' for id in missing})
    for row in rows:
        row['product_line_name'] = names.get(row.get('organization_id'), '未配置产品线')


@router.get('/metadata')
def metadata(db: Session = Depends(get_db), ctx: dict = Depends(require_permission('report:purchase:view'))):
    return dict(fields=report_fields(), overview_fields=overview_fields(), filter_fields=filter_fields('purchase'),
                query_fields=query_fields('purchase'), column_filter_fields=[f for f in query_fields('purchase') if f['operators'] != ['reference']],
                overview_column_filter_fields=[f for f in query_fields('purchase-overview') if f['operators'] != ['reference']], query_schema_version=2,
                overview_query_fields=list({f['field']: f for f in [*query_fields('purchase'), *query_fields('purchase-overview')]}.values()),
                unsupported_query_fields=[],
                progress_labels=PROGRESS_LABELS, document_status_labels=DOCUMENT_STATUSES,
                organizations=[{'value': line.organization_id, 'label': line.display_name} for line in scoped_lines(db, ctx) if line.is_enabled],
                start_date=REPORT_START_DATE.isoformat())


@router.get('/overview')
def overview(query: Annotated[PurchaseOverviewQuery, Query()], db: Session = Depends(get_db),
             ctx: dict = Depends(require_permission('report:purchase:view'))):
    resolve_project_references(db, ctx, query)
    resolve_query_labels(db, ctx, query)
    with report_connection() as connection:
        validate_reference_query(connection, query, authorized_organizations(db, ctx))
        result = list_overview(connection, query, project_scope(db, ctx))
        enrich_product_lines(db, connection, result['items'])
        ids = sorted({row['organization_id'] for row in result['items']})
        names = {row['id']: row['name'] for row in _rows(connection,
            'SELECT FORGID AS id,FNAME AS name FROM dbo.T_ORG_ORGANIZATIONS_L WHERE FLOCALEID=2052 AND FORGID IN ('
            + ','.join(['%s'] * len(ids)) + ')', ids)} if ids else {}
        for row in result['items']:
            row['organization_name'] = names.get(row['organization_id']) or str(row['organization_id'])
    result['queried_at'] = datetime.now(timezone.utc).isoformat()
    return jsonable_encoder(result, custom_encoder={Decimal: str})


@router.get('')
def listing(query: Annotated[PurchaseQuery, Query()], db: Session = Depends(get_db),
            ctx: dict = Depends(require_permission('report:purchase:view'))):
    resolve_project_references(db, ctx, query)
    resolve_query_labels(db, ctx, query)
    codes = project_scope(db, ctx)
    with report_connection() as connection:
        validate_reference_query(connection, query, authorized_organizations(db, ctx))
        result = list_requests(connection, query, codes)
        enrich_product_lines(db, connection, result['items'])
    result['items'] = [public_row(row) for row in result['items']]
    result['queried_at'] = datetime.now(timezone.utc).isoformat()
    return result


@router.get('/options')
def options(field: Literal['project', 'supplier'], keyword: str = Query('', max_length=100),
            organization_ids: list[Annotated[int, Field(gt=0)]] = Query(default=[], max_length=200),
            project_code: str = Query('', max_length=100),
            db: Session = Depends(get_db), ctx: dict = Depends(require_permission('report:purchase:view'))):
    with report_connection() as connection:
        return list_options(connection, field, keyword, project_scope(db, ctx),
                            query=PurchaseQuery(organization_ids=organization_ids, project_code=project_code))


def ensure_export_permission(ctx):
    enforce_permission(ctx, 'report:purchase:view')
    enforce_permission(ctx, 'report:purchase:export')


@router.get('/export')
def export(request: Request, query: Annotated[PurchaseQuery, Query()], db: Session = Depends(get_db),
           ctx: dict = Depends(require_permission('report:purchase:export'))):
    ensure_export_permission(ctx)
    raise HTTPException(410, '导出已升级为后台Excel任务，请刷新页面后使用导出按钮')


def _column_options(model, field, keyword, page, page_size, parameters, column_filters, db, ctx):
    from app.services.report_column_candidates import request_query, candidate_query, purchase_candidates
    query = request_query(model, parameters, column_filters)
    report = 'purchase-overview' if model is PurchaseOverviewQuery else 'purchase'
    try:
        candidate_query(query, report, field, keyword, page, page_size)
    except ValueError:
        raise HTTPException(422, '该列尚不支持候选查询或参数无效') from None
    resolve_project_references(db, ctx, query)
    query._candidate_field = field
    resolve_query_labels(db, ctx, query)
    grants = project_scope(db, ctx)
    if grants == []:
        return dict(items=[], total=0, page=page, page_size=page_size, has_more=False)
    with report_connection() as connection:
        validate_reference_query(connection, query, authorized_organizations(db, ctx))
        return purchase_candidates(connection, query, grants, field, keyword, page, page_size)


@router.get('/column-options')
def column_options(field: str = Query(max_length=100), keyword: str = Query('', max_length=100),
                   page: int = Query(1, ge=1, le=1000000), page_size: int = Query(50, ge=1, le=200),
                   parameters: str = Query('{}', max_length=36000), column_filters: str | None = Query(None, max_length=12000),
                   db: Session = Depends(get_db), ctx=Depends(require_permission('report:purchase:view'))):
    return _column_options(PurchaseQuery, field, keyword, page, page_size, parameters, column_filters, db, ctx)


@router.get('/overview/column-options')
def overview_column_options(field: str = Query(max_length=100), keyword: str = Query('', max_length=100),
                            page: int = Query(1, ge=1, le=1000000), page_size: int = Query(50, ge=1, le=200),
                            parameters: str = Query('{}', max_length=36000), column_filters: str | None = Query(None, max_length=12000),
                            db: Session = Depends(get_db), ctx=Depends(require_permission('report:purchase:view'))):
    return _column_options(PurchaseOverviewQuery, field, keyword, page, page_size, parameters, column_filters, db, ctx)


@router.get('/material-reference-options')
def material_reference_options(keyword: str = Query('', max_length=100),
        organization_ids: list[Annotated[int, Field(gt=0)]] = Query(default=[], max_length=200),
        page: int = Query(1, ge=1, le=1000000), page_size: int = Query(50, ge=1, le=500),
        ids: list[str] = Query(default=[], max_length=1000), batch_field: Literal['code','name'] = 'code',
        batch_values: list[str] = Query(default=[], max_length=1000),
        db: Session = Depends(get_db), ctx=Depends(require_permission('report:purchase:view'))):
    organizations = material_organizations(organization_ids, authorized_organizations(db, ctx))
    if organizations == []:
        return list_material_candidates(None, keyword, organizations, page=page, page_size=page_size, ids=ids, batch_field=batch_field, batch_values=batch_values)
    with report_connection() as connection:
        cursor = connection.cursor()
        try:
            return list_material_candidates(cursor, keyword, organizations, page=page, page_size=page_size, ids=ids, batch_field=batch_field, batch_values=batch_values)
        finally:
            cursor.close()


@router.get('/reference-options')
def reference_options(field: Literal['project_code', 'project_name'], keyword: str = Query('', max_length=100),
                      exact_values: str | None = Query(None, max_length=12000),
                      ids: list[Annotated[int, Field(gt=0)]] = Query(default=[], max_length=1000),
                      organization_ids: list[Annotated[int, Field(gt=0)]] = Query(default=[], max_length=200),
                      page: int = Query(1, ge=1, le=1000000), page_size: int = Query(50, ge=1, le=500),
                      db: Session = Depends(get_db), ctx=Depends(require_permission('report:purchase:view'))):
    query = (get_scoped_archive_query(db, ctx)
        .join(SysProductLine, SysProductLine.id == PmsProjectArchive.business_product_line_id)
        .filter(SysProductLine.source_key == 'kingdee', SysProductLine.organization_id > 0))
    if organization_ids:
        query = query.filter(SysProductLine.organization_id.in_(organization_ids))
    if ids:
        if exact_values is not None or keyword:
            raise HTTPException(422, '引用身份校验不能混用字符或批量搜索')
        query = query.filter(PmsProjectArchive.id.in_(ids))
        if {key for key, in query.with_entities(PmsProjectArchive.id).all()} != set(ids):
            raise HTTPException(422, '选中的项目引用已失效或无权访问，请重新选择')
    batch = None
    column = getattr(PmsProjectArchive, field)
    if exact_values is not None:
        if keyword:
            raise HTTPException(422, '普通搜索与批量精准搜索不能同时指定')
        try:
            values = json.loads(exact_values)
            if not isinstance(values, list) or not 1 <= len(values) <= 1000 or any(
                    not isinstance(v, str) or any(c in v for c in '\t\r\n') for v in values):
                raise ValueError()
            normalized = [scalar(v, 'text') for v in values]
            unique = dict(zip(normalized, values))
            query = query.filter(build_query_clause(column, 'text',
                dict(schemaVersion=2, operator='in', value=list(unique)), membership=True))
        except (ValueError, HTTPException):
            raise HTTPException(422, '批量查询必须是最多1000个单列文本值，编码请保留前导零') from None
        counts = dict(query.with_entities(func.lower(func.trim(column)), func.count(PmsProjectArchive.id))
                      .group_by(func.lower(func.trim(column))).all())
        batch = dict(input_count=len(unique), duplicate_count=len(values) - len(unique),
                     matched_records=sum(counts.values()),
                     unmatched_values=[v for key, v in unique.items() if key not in counts],
                     ambiguous_values=[v for key, v in unique.items() if counts.get(key, 0) > 1])
    elif keyword.strip():
        query = query.filter(or_(*[build_query_clause(c, 'text',
            dict(schemaVersion=2, operator='contains', value=keyword))
            for c in (PmsProjectArchive.project_code, PmsProjectArchive.project_name)]))
    total = query.count()
    rows = query.with_entities(PmsProjectArchive.id, PmsProjectArchive.project_code,
        PmsProjectArchive.project_name, SysProductLine.organization_id, SysProductLine.display_name).order_by(
        PmsProjectArchive.project_code, PmsProjectArchive.id).offset((page - 1) * page_size).limit(page_size).all()
    return dict(items=[dict(value=key, id=key, code=code, label=name, organization_id=org, product_line_name=line, lineName=line)
                       for key, code, name, org, line in rows], total=total, page=page, page_size=page_size,
                has_more=page * page_size < total, batch=batch)


@router.get('/{request_id}')
def detail(request_id: int = Path(ge=1), db: Session = Depends(get_db),
           ctx: dict = Depends(require_permission('report:purchase:view'))):
    codes = project_scope(db, ctx)
    with report_connection() as connection:
        row = load_request(connection, request_id, codes)
        if not row:
            raise HTTPException(404, '申请明细不存在或无权访问')
        chain = load_chains(connection, [row])[row['id']]
        enrich_product_lines(db, connection, [row])
    # Do not expose other requisitions' IDs or source allocations used internally.
    return jsonable_encoder(dict(request=public_row(row), **chain, queried_at=datetime.now(timezone.utc).isoformat()),
                            custom_encoder={Decimal: str})
