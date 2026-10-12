"""Materialize current display labels before report predicates and pagination.

This is a source adapter only; all conditions use the shared query compiler.
No SQL identifiers or label mappings are accepted from the browser.
"""
from app.services.purchase_fields import DOCUMENT_STATUSES

PMS_LABELS = {'product_line_name', 'project_name'}
CHAIN_LABELS = {'supplier_name', 'order_statuses', 'stock_statuses'}


def needed_labels(query, conditions):
    return {c.field for c in conditions if c.kind != 'project-reference'} | {query._candidate_field, query.sort}


def resolve_query_labels(db, ctx, query):
    from app.models.product_line import SysProductLine
    from app.models.project import PmsProjectArchive
    from app.services.project import get_scoped_archive_query
    needed = needed_labels(query, [*query.conditions(), *query.column_conditions()])
    query._query_labels = {}
    if 'product_line_name' in needed:
        rows = db.query(SysProductLine.organization_id, SysProductLine.display_name).filter(
            SysProductLine.source_key == 'kingdee', SysProductLine.organization_id > 0)
        if query.organization_ids:
            rows = rows.filter(SysProductLine.organization_id.in_(query.organization_ids))
        query._query_labels['product_line_name'] = dict(rows.all())
    if 'project_name' in needed:
        rows = (get_scoped_archive_query(db, ctx)
            .join(SysProductLine, SysProductLine.id == PmsProjectArchive.business_product_line_id)
            .filter(SysProductLine.source_key == 'kingdee', SysProductLine.organization_id > 0))
        if query.organization_ids:
            rows = rows.filter(SysProductLine.organization_id.in_(query.organization_ids))
        query._query_labels['project_name'] = {(code, org): name for code, org, name in rows.with_entities(
            PmsProjectArchive.project_code, SysProductLine.organization_id, PmsProjectArchive.project_name).all()}
    return query


def public_orders():
    # Match load_chains' public_order_ids, not the larger accounting workset.
    return """SELECT e.FENTRYID AS id,e.FID AS bill_id,e.FMATERIALID AS material_id,
 e.FBASEUNITID AS base_unit_id,h.FDOCUMENTSTATUS AS document_status,
 h.FSUPPLIERID AS supplier_id,s.FNAME AS supplier_name
 FROM dbo.T_PUR_POORDERENTRY e JOIN dbo.T_PUR_POORDER h ON h.FID=e.FID
 LEFT JOIN dbo.T_BD_SUPPLIER_L s ON s.FSUPPLIERID=h.FSUPPLIERID AND s.FLOCALEID=2052
 WHERE h.FPURCHASEORGID=label_source.organization_id
 AND e.FMATERIALID=label_source.material_id AND e.FBASEUNITID=label_source.base_unit_id
 AND (SELECT COUNT(*) FROM dbo.T_PUR_POORDERENTRY_LK x WHERE x.FENTRYID=e.FENTRYID)=1
 AND EXISTS (SELECT 1 FROM dbo.T_PUR_POORDERENTRY_LK l WHERE l.FENTRYID=e.FENTRYID
 AND LOWER(l.FSTABLENAME)='t_pur_reqentry' AND l.FSID=label_source.id AND l.FSBILLID=label_source.bill_id)"""


def public_stocks():
    return f"""SELECT h.FDOCUMENTSTATUS AS document_status FROM dbo.T_STK_INSTOCKENTRY s
 JOIN dbo.T_STK_INSTOCK h ON h.FID=s.FID
 JOIN ({public_orders()}) o ON o.id=s.FPOORDERENTRYID
 WHERE h.FSTOCKORGID=label_source.organization_id
 AND s.FMATERIALID=o.material_id AND s.FBASEUNITID=o.base_unit_id
 AND NOT EXISTS (SELECT 1 FROM dbo.T_PUR_RECEIVEENTRY re
 LEFT JOIN dbo.T_PUR_RECEIVE rh ON rh.FID=re.FID WHERE re.FPOORDERENTRYID=o.id
 AND (rh.FSTOCKORGID IS NULL OR rh.FSTOCKORGID<>label_source.organization_id))
 AND (SELECT COUNT(*) FROM dbo.T_STK_INSTOCKENTRY_LK x WHERE x.FENTRYID=s.FENTRYID)=1
 AND EXISTS (SELECT 1 FROM dbo.T_STK_INSTOCKENTRY_LK l WHERE l.FENTRYID=s.FENTRYID
 AND l.FBASEUNITQTY=s.FBASEUNITQTY AND (
 (LOWER(l.FSTABLENAME)='t_pur_poorderentry' AND l.FSID=o.id AND l.FSBILLID=o.bill_id)
 OR (LOWER(l.FSTABLENAME)='t_pur_receiveentry' AND EXISTS (
 SELECT 1 FROM dbo.T_PUR_RECEIVEENTRY r WHERE r.FENTRYID=l.FSID AND r.FID=l.FSBILLID
 AND r.FPOORDERENTRYID=o.id AND r.FMATERIALID=s.FMATERIALID AND r.FBASEUNITID=s.FBASEUNITID))))"""


def status_labels(source):
    # Fixed Unicode order mirrors sorted(set(labels)) in the existing row view.
    values = sorted([*DOCUMENT_STATUSES.items(), (None, '未知状态')], key=lambda item: item[1])
    parts = []
    for key, label in values:
        predicate = f"document_status='{key}'" if key else "(document_status IS NULL OR document_status NOT IN ('A','B','C','D','Z'))"
        parts.append(f"MAX(CASE WHEN {predicate} THEN N'、{label}' ELSE N'' END)")
    return f"(SELECT STUFF(CONCAT({','.join(parts)}),1,1,N'') FROM ({source}) documents)"


def label_source(base, params, query, conditions, *, final_overview=False):
    needed = {c.field for c in conditions if c.kind != 'project-reference'}
    # Overview labels belong to final groups, never the accounting input.
    from app.services.purchase_reader import PurchaseOverviewQuery
    if not isinstance(query, PurchaseOverviewQuery) or final_overview:
        needed.add(query._candidate_field)
        needed.add(query.sort)
    fields = needed & (PMS_LABELS | CHAIN_LABELS | {'organization_name'})
    if not fields:
        return base, params
    source_params, params, expressions = list(params), [], []
    for field in sorted(fields):
        if field in PMS_LABELS:
            if field not in query._query_labels:
                raise ValueError('PMS display labels require current database resolution')
            parts = []
            for key, name in sorted(query._query_labels[field].items()):
                if field == 'project_name':
                    code, org = key
                    parts.append('WHEN label_source.project_code=%s AND label_source.organization_id=%s THEN %s')
                    params.extend([code, org, name])
                else:
                    parts.append('WHEN label_source.organization_id=%s THEN %s')
                    params.extend([key, name])
            fallback = 'CAST(NULL AS nvarchar(128))' if field == 'project_name' else (
                "CONCAT(COALESCE((SELECT NULLIF(MAX(FNAME),'') FROM dbo.T_ORG_ORGANIZATIONS_L "
                "WHERE FLOCALEID=2052 AND FORGID=label_source.organization_id),"
                "CONCAT(N'组织 ',label_source.organization_id)),N'（未配置产品线）')")
            expression = 'CASE ' + ' '.join(parts) + ' ELSE ' + fallback + ' END' if parts else fallback
        elif field == 'organization_name':
            expression = ("COALESCE((SELECT MAX(FNAME) FROM dbo.T_ORG_ORGANIZATIONS_L "
                          "WHERE FLOCALEID=2052 AND FORGID=label_source.organization_id),CONCAT('',label_source.organization_id))")
        elif field == 'supplier_name':
            expression = ("(SELECT CASE WHEN COUNT(DISTINCT supplier_id)>1 THEN N'多家供应商' "
                          f"ELSE MAX(supplier_name) END FROM ({public_orders()}) suppliers WHERE supplier_id<>0)")
        else:
            expression = status_labels(public_orders() if field == 'order_statuses' else public_stocks())
        expressions.append(f'{expression} AS [{field}]')
    params += source_params
    if len(params) > 2000:
        raise ValueError('PMS label mapping exceeds SQL parameter budget; narrow the organization scope')
    return f"SELECT label_source.*,{','.join(expressions)} FROM ({base}) label_source", params
