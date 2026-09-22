"""Fixed, parameterized Kingdee queries through the dedicated read-only identity."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.services.purchase_progress import summarize_requisition
from app.services.purchase_fields import DOCUMENT_STATUSES

REPORT_START_DATE = date(2026, 1, 1)


class PurchaseQuery(BaseModel):
    keyword: str = Field(default='', max_length=100)
    project_code: str = Field(default='', max_length=100)
    supplier: str = Field(default='', max_length=100)
    date_from: date | None = None
    date_to: date | None = None
    progress: Literal['', 'not_ordered', 'ordering', 'receiving', 'complete', 'review'] = ''
    page: int = Field(default=1, ge=1, le=1000000)
    page_size: int = Field(default=50, ge=1, le=500)
    sort: Literal['date', 'bill_no', 'project_code', 'material_code'] = 'date'
    direction: Literal['asc', 'desc'] = 'desc'

    @model_validator(mode='after')
    def date_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError('开始日期不能晚于结束日期')
        return self


def effective_state(status, cancelled):
    if cancelled == 'B':
        return False
    if cancelled != 'A':
        return None
    if status == 'C':
        return True
    if status in ('A', 'B', 'D', 'Z'):
        return False
    return None


@dataclass(frozen=True)
class ProjectOrganizationGrant:
    project_code: str
    organization_id: int

    def __post_init__(self):
        if not isinstance(self.project_code, str) or not self.project_code or len(self.project_code) > 100:
            raise ValueError('invalid_project_code')
        if type(self.organization_id) is not int or self.organization_id <= 0:
            raise ValueError('invalid_organization_id')


def scope_clause(column, grants):
    if not grants:
        return '1=0', []
    if any(not isinstance(grant, ProjectOrganizationGrant) for grant in grants):
        raise ValueError('paired_project_organization_grants_required')
    if len(grants) > 400:
        return (f'EXISTS (SELECT 1 FROM #pms_purchase_scope g WHERE g.project_code={column}'
                ' AND g.organization_id=h.FAPPLICATIONORGID)'), []
    return '(' + ' OR '.join([f'({column}=%s AND h.FAPPLICATIONORGID=%s)'] * len(grants)) + ')', [
        value for grant in grants for value in (grant.project_code, grant.organization_id)]


def _prepare_scope(connection, grants):
    scope_clause('a.FNUMBER', grants)
    if not grants or len(grants) <= 400:
        return
    cursor = connection.cursor()
    try:
        cursor.execute('DROP TABLE IF EXISTS #pms_purchase_scope', ())
        cursor.execute('CREATE TABLE #pms_purchase_scope (project_code nvarchar(100) COLLATE DATABASE_DEFAULT, organization_id bigint)', ())
        for start in range(0, len(grants), 400):
            batch = grants[start:start + 400]
            cursor.execute('INSERT INTO #pms_purchase_scope (project_code, organization_id) VALUES '
                + ','.join(['(%s,%s)'] * len(batch)), tuple(
                    value for grant in batch for value in (grant.project_code, grant.organization_id)))
    finally:
        cursor.close()


def receipt_source_valid(receipt, edges, order, receiving):
    if (not order or len(edges) != 1 or receipt['material_id'] != order['material_id']
            or receipt['base_unit_id'] != order['base_unit_id']):
        return False
    edge = edges[0]
    try:
        if Decimal(str(edge['base_qty'])) != Decimal(str(receipt['base_qty'])):
            return False
    except (InvalidOperation, TypeError, ValueError):
        return False
    source = edge['source_table'].lower()
    if source == 't_pur_poorderentry':
        return edge['source_id'] == order['id'] and edge['source_bill_id'] == order['bill_id']
    if source == 't_pur_receiveentry':
        upstream = receiving.get(edge['source_id'])
        return bool(upstream and upstream['bill_id'] == edge['source_bill_id']
                    and upstream['order_id'] == order['id']
                    and upstream['material_id'] == receipt['material_id']
                    and upstream['base_unit_id'] == receipt['base_unit_id'])
    return False


REQUEST_SELECT = """
SELECT e.FENTRYID AS id, e.FID AS bill_id, e.FSEQ AS line_no,
 h.FBILLNO AS bill_no, h.FAPPLICATIONDATE AS application_date, h.FAPPLICATIONORGID AS organization_id,
 h.FDOCUMENTSTATUS AS document_status, h.FCANCELSTATUS AS cancel_status,
 h.FCLOSESTATUS AS close_status, e.FMRPCLOSESTATUS AS line_close_status,
 e.FMRPTERMINATESTATUS AS terminate_status, e.FISSPLITCANCEL AS split_cancel,
 e.FMATERIALID AS material_id, e.FUNITID AS unit_id, e.FBASEUNITID AS base_unit_id,
 e.FREQQTY AS requested, e.FAPPROVEQTY AS approved, e.FBASEUNITQTY AS approved_base,
 m.FNUMBER AS material_code, ml.FNAME AS material_name, ml.FSPECIFICATION AS specification,
 u.FNAME AS unit_name, a.FNUMBER AS project_code
FROM dbo.T_PUR_REQENTRY e JOIN dbo.T_PUR_REQUISITION h ON h.FID=e.FID
LEFT JOIN dbo.T_BD_MATERIAL m ON m.FMATERIALID=e.FMATERIALID
LEFT JOIN dbo.T_BD_MATERIAL_L ml ON ml.FMATERIALID=e.FMATERIALID AND ml.FLOCALEID=2052
LEFT JOIN dbo.T_BD_UNIT_L u ON u.FUNITID=e.FUNITID AND u.FLOCALEID=2052
LEFT JOIN dbo.T_BAS_ASSISTANTDATAENTRY a ON a.FENTRYID=e.F_TWBJ_ASSISTANT_83G
"""


def _rows(connection, sql, params=()):
    cursor = connection.cursor()
    try:
        cursor.execute(sql, tuple(params))
        return list(cursor.fetchall())
    finally:
        cursor.close()


def _in(ids):
    return ','.join(['%s'] * len(ids))


def _with_state(rows):
    for row in rows:
        row['effective'] = effective_state(row['document_status'], row['cancel_status'])
    return rows


def load_request(connection, request_id, project_codes):
    _prepare_scope(connection, project_codes)
    scope, params = scope_clause('a.FNUMBER', project_codes)
    rows = _rows(connection, REQUEST_SELECT + ' WHERE e.FENTRYID=%s AND h.FAPPLICATIONDATE>=%s AND ' + scope,
                 [request_id, REPORT_START_DATE, *params])
    if len(rows) != 1:
        return None
    return _with_state(rows)[0]


def load_chains(connection, requests):
    """Read complete chains in batches; no LIMIT on a single request's children.

    Reads all source links for the orders, including other requests. Those links
    are accounting-only and must never be returned to the browser.
    """
    if not requests:
        return {}
    request_ids = [row['id'] for row in requests]
    orders = _with_state(_rows(connection, f"""
SELECT e.FENTRYID AS id, e.FID AS bill_id, e.FSEQ AS line_no,
 h.FBILLNO AS bill_no, h.FDATE AS order_date, h.FDOCUMENTSTATUS AS document_status, h.FPURCHASEORGID AS organization_id,
 h.FCANCELSTATUS AS cancel_status, h.FCLOSESTATUS AS close_status,
 h.FSUPPLIERID AS supplier_id, s.FNAME AS supplier_name,
 e.FMATERIALID AS material_id, e.FUNITID AS unit_id, e.FBASEUNITID AS base_unit_id,
 e.FQTY AS quantity, e.FBASEUNITQTY AS base_qty, u.FNAME AS unit_name
FROM dbo.T_PUR_POORDERENTRY e JOIN dbo.T_PUR_POORDER h ON h.FID=e.FID
LEFT JOIN dbo.T_BD_SUPPLIER_L s ON s.FSUPPLIERID=h.FSUPPLIERID AND s.FLOCALEID=2052
LEFT JOIN dbo.T_BD_UNIT_L u ON u.FUNITID=e.FUNITID AND u.FLOCALEID=2052
WHERE EXISTS (SELECT 1 FROM dbo.T_PUR_POORDERENTRY_LK l
 WHERE l.FENTRYID=e.FENTRYID AND LOWER(l.FSTABLENAME)='t_pur_reqentry'
 AND l.FSID IN ({_in(request_ids)}))
""", request_ids))
    # Discover IDs from the links, not existing orders: dangling links must fail closed.
    order_ids = [row['id'] for row in _rows(connection, f"""
SELECT DISTINCT FENTRYID AS id FROM dbo.T_PUR_POORDERENTRY_LK
WHERE LOWER(FSTABLENAME)='t_pur_reqentry' AND FSID IN ({_in(request_ids)})""", request_ids)]
    if not order_ids:
        return {row['id']: dict(summary=summarize_requisition(row, [], [], [], complete=True),
                               orders=[], receipts=[], returns=[]) for row in requests}
    # Bound placeholders below SQL Server's 2100 parameter ceiling. Child
    # chains are not truncated: each independent order batch is read completely.
    links, receipts, returns, receiving, receipt_edges = [], [], [], [], []
    for start in range(0, len(order_ids), 500):
        batch = order_ids[start:start + 500]
        links.extend(_rows(connection, f"""SELECT FENTRYID AS order_id, FLINKID AS link_id,
 FSTABLENAME AS source_table, FSID AS request_id, FSBILLID AS request_bill_id,
 FBASEUNITQTY AS base_qty FROM dbo.T_PUR_POORDERENTRY_LK WHERE FENTRYID IN ({_in(batch)})""", batch))
        receipts.extend(_with_state(_rows(connection, f"""
SELECT e.FENTRYID AS id, e.FID AS bill_id, e.FSEQ AS line_no,
 h.FBILLNO AS bill_no, h.FDATE AS stock_date, h.FDOCUMENTSTATUS AS document_status, h.FSTOCKORGID AS organization_id,
 h.FCANCELSTATUS AS cancel_status, e.FPOORDERENTRYID AS order_id,
 e.FMATERIALID AS material_id, e.FUNITID AS unit_id, e.FBASEUNITID AS base_unit_id,
 e.FREALQTY AS quantity, e.FBASEUNITQTY AS base_qty, u.FNAME AS unit_name
FROM dbo.T_STK_INSTOCKENTRY e JOIN dbo.T_STK_INSTOCK h ON h.FID=e.FID
LEFT JOIN dbo.T_BD_UNIT_L u ON u.FUNITID=e.FUNITID AND u.FLOCALEID=2052
WHERE e.FPOORDERENTRYID IN ({_in(batch)})""", batch)))
        receiving.extend(_rows(connection, f"""SELECT e.FENTRYID AS id, e.FID AS bill_id,
 e.FPOORDERENTRYID AS order_id, e.FMATERIALID AS material_id, e.FBASEUNITID AS base_unit_id,
 h.FSTOCKORGID AS organization_id
FROM dbo.T_PUR_RECEIVEENTRY e LEFT JOIN dbo.T_PUR_RECEIVE h ON h.FID=e.FID
WHERE e.FPOORDERENTRYID IN ({_in(batch)})""", batch))
        returns.extend(_with_state(_rows(connection, f"""
SELECT e.FENTRYID AS id, e.FID AS bill_id, e.FSEQ AS line_no, e.FPOORDERENTRYID AS order_id,
 h.FBILLNO AS bill_no, h.FDATE AS return_date, h.FDOCUMENTSTATUS AS document_status, h.FSTOCKORGID AS organization_id,
 h.FCANCELSTATUS AS cancel_status, e.FMATERIALID AS material_id,
 e.FBASEUNITID AS base_unit_id, e.FRMREALQTY AS quantity, e.FBASEUNITQTY AS entry_base_qty,
 l.FLINKID AS link_id, l.FSTABLENAME AS source_table, l.FSID AS receipt_id,
 l.FSBILLID AS source_bill_id, l.FBASEUNITQTY AS base_qty
FROM dbo.T_PUR_MRBENTRY e JOIN dbo.T_PUR_MRB h ON h.FID=e.FID
LEFT JOIN dbo.T_PUR_MRBENTRY_LK l ON l.FENTRYID=e.FENTRYID
WHERE e.FPOORDERENTRYID IN ({_in(batch)})""", batch)))
    receipt_ids = [row['id'] for row in receipts]
    for start in range(0, len(receipt_ids), 500):
        batch = receipt_ids[start:start + 500]
        receipt_edges.extend(_rows(connection, f"""SELECT FENTRYID AS receipt_id,
 FSTABLENAME AS source_table, FSID AS source_id, FSBILLID AS source_bill_id,
 FBASEUNITQTY AS base_qty FROM dbo.T_STK_INSTOCKENTRY_LK WHERE FENTRYID IN ({_in(batch)})""", batch))
    order_map = {row['id']: row for row in orders}
    receipt_map = {row['id']: row for row in receipts}
    receiving_map = {row['id']: row for row in receiving}
    edges_by_receipt = defaultdict(list)
    for edge in receipt_edges:
        edges_by_receipt[edge['receipt_id']].append(edge)
    for row in receipts:
        row['source_valid'] = receipt_source_valid(row, edges_by_receipt[row['id']],
                                                   order_map.get(row['order_id']), receiving_map)
        if row['effective'] is True and not row['source_valid']:
            row['effective'] = None
    for row in returns:
        source = (row['source_table'] or '').lower()
        row['source_kind'] = {'t_stk_instockentry': 'stock', 't_pur_receiveentry': 'receive'}.get(source)
        stock = receipt_map.get(row['receipt_id'])
        if row['source_kind'] == 'stock' and (not stock or stock['bill_id'] != row['source_bill_id']
                or stock['order_id'] != row['order_id'] or row['entry_base_qty'] != row['base_qty']):
            row['source_kind'] = None
    # A different source entity can reuse the same numeric ID; namespace it so
    # it cannot be mistaken for this requisition, while preserving ambiguity.
    for link in links:
        if (link['source_table'] or '').lower() != 't_pur_reqentry':
            link['request_id'] = str(link['source_table']) + ':' + str(link['request_id'])
    result = {}
    for request in requests:
        ids = {link['order_id'] for link in links if link['request_id'] == request['id']}
        selected_orders = [row for row in orders if row['id'] in ids]
        selected_receipts = [row for row in receipts if row['order_id'] in ids]
        selected_returns = [row for row in returns if row['order_id'] in ids]
        selected_receiving = [row for row in receiving if row['order_id'] in ids]
        organization = request.get('organization_id')
        organization_valid = bool(organization) and all(
            row.get('organization_id') == organization
            for row in [*selected_orders, *selected_receipts, *selected_returns, *selected_receiving])
        summary = summarize_requisition(request, selected_orders,
            [row for row in links if row['order_id'] in ids], selected_receipts, selected_returns, complete=organization_valid)
        if not organization_valid:
            summary['issues'] = ['organization_chain_unverified']
        public_order_ids = set()
        for order in selected_orders:
            edges = [link for link in links if link['order_id'] == order['id']]
            if (organization and order.get('organization_id') == organization
                    and len(edges) == 1 and edges[0]['request_id'] == request['id']
                    and edges[0]['request_bill_id'] == request['bill_id']
                    and order['material_id'] == request['material_id']
                    and order['base_unit_id'] == request['base_unit_id']):
                public_order_ids.add(order['id'])
        # Totals retain only the current request's allocation, but raw merged
        # documents could disclose another project's quantities and suppliers.
        if len(public_order_ids) != len(ids):
            summary['issues'] = sorted(set(summary['issues']) | {'withheld_source_documents'})
        unsafe_receiving_orders = {row['order_id'] for row in selected_receiving if row.get('organization_id') != organization}
        public_receipts = [row for row in selected_receipts if row['order_id'] in public_order_ids and row['source_valid']
                           and row.get('organization_id') == organization and row['order_id'] not in unsafe_receiving_orders]
        public_stock_ids = {row['id'] for row in public_receipts}
        result[request['id']] = dict(summary=summary,
            orders=[row for row in selected_orders if row['id'] in public_order_ids], receipts=public_receipts,
            returns=[row for row in selected_returns if row['order_id'] in public_order_ids
                     and row.get('organization_id') == organization
                     and row['source_kind'] == 'stock' and row['receipt_id'] in public_stock_ids],
            withheld_order_count=len(ids - public_order_ids))
    return result


# Each aggregation below has exactly one business grain: order/source pair,
# stock entry, order entry, then request entry. Never sum a raw three-way join.
ACCOUNTING_STAGES = [('order_ids', """
 SELECT DISTINCT l.FENTRYID AS id FROM dbo.T_PUR_POORDERENTRY_LK l
 JOIN q ON q.id=l.FSID WHERE LOWER(l.FSTABLENAME)='t_pur_reqentry'
"""), ('links', """
 SELECT l.FENTRYID AS order_id, LOWER(l.FSTABLENAME) AS source_table,
 l.FSID AS request_id, l.FSBILLID AS request_bill_id,
 SUM(l.FBASEUNITQTY) AS base_qty, COUNT(*) AS edge_count
 FROM dbo.T_PUR_POORDERENTRY_LK l JOIN order_ids i ON i.id=l.FENTRYID
 GROUP BY l.FENTRYID, LOWER(l.FSTABLENAME), l.FSID, l.FSBILLID
"""), ('sources', """
 SELECT order_id, COUNT(*) AS source_count FROM links GROUP BY order_id
"""), ('orders', """
 SELECT e.FENTRYID AS id, e.FID AS bill_id, e.FMATERIALID AS material_id,
 e.FBASEUNITID AS base_unit_id, h.FDATE AS order_date, h.FSUPPLIERID AS supplier_id,
 s.FNAME AS supplier_name, h.FPURCHASEORGID AS organization_id,
 CASE WHEN h.FCANCELSTATUS='B' THEN 0
 WHEN h.FCANCELSTATUS='A' AND h.FDOCUMENTSTATUS='C' THEN 1
 WHEN h.FCANCELSTATUS='A' AND h.FDOCUMENTSTATUS IN ('A','B','D','Z') THEN 0 ELSE -1 END AS active
 FROM dbo.T_PUR_POORDERENTRY e JOIN order_ids i ON i.id=e.FENTRYID
 JOIN dbo.T_PUR_POORDER h ON h.FID=e.FID
 LEFT JOIN dbo.T_BD_SUPPLIER_L s ON s.FSUPPLIERID=h.FSUPPLIERID AND s.FLOCALEID=2052
"""), ('stock', """
 SELECT e.FENTRYID AS id, e.FID AS bill_id, e.FPOORDERENTRYID AS order_id,
 e.FMATERIALID AS material_id, e.FBASEUNITID AS base_unit_id, e.FBASEUNITQTY AS base_qty,
 h.FDATE AS stock_date, h.FSTOCKORGID AS organization_id,
 CASE WHEN h.FCANCELSTATUS='B' THEN 0
 WHEN h.FCANCELSTATUS='A' AND h.FDOCUMENTSTATUS='C' THEN 1
 WHEN h.FCANCELSTATUS='A' AND h.FDOCUMENTSTATUS IN ('A','B','D','Z') THEN 0 ELSE -1 END AS active,
 CASE WHEN (SELECT COUNT(*) FROM dbo.T_STK_INSTOCKENTRY_LK l WHERE l.FENTRYID=e.FENTRYID)=1
 AND EXISTS (SELECT 1 FROM dbo.T_STK_INSTOCKENTRY_LK l
  WHERE l.FENTRYID=e.FENTRYID AND l.FBASEUNITQTY=e.FBASEUNITQTY AND (
   (LOWER(l.FSTABLENAME)='t_pur_poorderentry' AND l.FSID=o.id AND l.FSBILLID=o.bill_id)
   OR (LOWER(l.FSTABLENAME)='t_pur_receiveentry' AND EXISTS (
    SELECT 1 FROM dbo.T_PUR_RECEIVEENTRY r WHERE r.FENTRYID=l.FSID AND r.FID=l.FSBILLID
    AND r.FPOORDERENTRYID=o.id AND r.FMATERIALID=e.FMATERIALID AND r.FBASEUNITID=e.FBASEUNITID))))
 THEN 1 ELSE 0 END AS source_valid
 FROM dbo.T_STK_INSTOCKENTRY e JOIN orders o ON o.id=e.FPOORDERENTRYID
 JOIN dbo.T_STK_INSTOCK h ON h.FID=e.FID
"""), ('return_edges', """
 SELECT e.FENTRYID AS id, e.FPOORDERENTRYID AS order_id, e.FMATERIALID AS material_id,
 e.FBASEUNITID AS base_unit_id, e.FBASEUNITQTY AS entry_base_qty,
 l.FSID AS stock_id, l.FSBILLID AS stock_bill_id, l.FBASEUNITQTY AS base_qty,
 LOWER(l.FSTABLENAME) AS source_table, h.FSTOCKORGID AS organization_id,
 (SELECT COUNT(*) FROM dbo.T_PUR_MRBENTRY_LK x WHERE x.FENTRYID=e.FENTRYID) AS edge_count,
 CASE WHEN h.FCANCELSTATUS='B' THEN 0
 WHEN h.FCANCELSTATUS='A' AND h.FDOCUMENTSTATUS='C' THEN 1
 WHEN h.FCANCELSTATUS='A' AND h.FDOCUMENTSTATUS IN ('A','B','D','Z') THEN 0 ELSE -1 END AS active
 FROM dbo.T_PUR_MRBENTRY e JOIN orders o ON o.id=e.FPOORDERENTRYID
 JOIN dbo.T_PUR_MRB h ON h.FID=e.FID
 LEFT JOIN dbo.T_PUR_MRBENTRY_LK l ON l.FENTRYID=e.FENTRYID
"""), ('return_totals', """
 SELECT r.order_id, SUM(CASE WHEN r.active=1 THEN r.base_qty ELSE 0 END) AS returned,
 MAX(CASE WHEN r.active=0 THEN 0
 WHEN r.active=1 AND r.source_table='t_stk_instockentry'
 AND r.edge_count=1 AND r.entry_base_qty=r.base_qty AND r.base_qty>=0
 AND s.id IS NOT NULL AND s.bill_id=r.stock_bill_id AND s.order_id=r.order_id
 AND s.material_id=r.material_id AND s.base_unit_id=r.base_unit_id AND s.active=1
 THEN 0 ELSE 1 END) AS invalid
 FROM return_edges r LEFT JOIN stock s ON s.id=r.stock_id
 WHERE r.source_table IS NULL OR r.source_table<>'t_pur_receiveentry'
 GROUP BY r.order_id
"""), ('over_returns', """
 SELECT r.order_id FROM return_edges r JOIN stock s ON s.id=r.stock_id
 WHERE r.active=1 AND r.source_table='t_stk_instockentry'
 GROUP BY r.order_id, s.id, s.base_qty HAVING SUM(r.base_qty)>s.base_qty
"""), ('stock_totals', """
 SELECT s.order_id, SUM(CASE WHEN s.active=1 THEN s.base_qty ELSE 0 END) AS received,
 MAX(CASE WHEN s.active=1 THEN s.stock_date ELSE NULL END) AS last_stock_date,
 MAX(CASE WHEN s.active=0 THEN 0
 WHEN s.active=1 AND o.active=1 AND src.source_count=1 AND s.source_valid=1
 AND s.material_id=o.material_id AND s.base_unit_id=o.base_unit_id
 AND s.base_qty>=0 THEN 0 ELSE 1 END) AS invalid
 FROM stock s JOIN orders o ON o.id=s.order_id JOIN sources src ON src.order_id=o.id
 GROUP BY s.order_id
"""), ('allocated', """
 SELECT q.id, l.order_id, l.base_qty, o.order_date, o.supplier_id, o.supplier_name, o.active,
 COALESCE(s.received,0) AS received, COALESCE(r.returned,0) AS returned, s.last_stock_date,
 CASE WHEN l.edge_count=1 AND l.request_bill_id=q.bill_id AND o.id IS NOT NULL
 AND o.organization_id=q.organization_id
 AND NOT EXISTS (SELECT 1 FROM stock os WHERE os.order_id=o.id
  AND (os.organization_id IS NULL OR os.organization_id<>q.organization_id))
 AND NOT EXISTS (SELECT 1 FROM return_edges org_return WHERE org_return.order_id=o.id
  AND (org_return.organization_id IS NULL OR org_return.organization_id<>q.organization_id))
 AND NOT EXISTS (SELECT 1 FROM dbo.T_PUR_RECEIVEENTRY org_entry
  LEFT JOIN dbo.T_PUR_RECEIVE org_head ON org_head.FID=org_entry.FID
  WHERE org_entry.FPOORDERENTRYID=o.id AND (org_head.FSTOCKORGID IS NULL OR org_head.FSTOCKORGID<>q.organization_id))
 AND o.material_id=q.material_id AND (o.active=0 OR
 (o.active=1 AND o.base_unit_id=q.base_unit_id AND l.base_qty>=0))
 THEN 0 ELSE 1 END AS order_invalid,
 COALESCE(s.invalid,0) AS receipt_invalid,
 CASE WHEN COALESCE(r.invalid,0)=1
 OR EXISTS (SELECT 1 FROM over_returns x WHERE x.order_id=l.order_id) THEN 1 ELSE 0 END AS return_invalid
 FROM q JOIN links l ON l.request_id=q.id AND l.source_table='t_pur_reqentry'
 LEFT JOIN orders o ON o.id=l.order_id LEFT JOIN stock_totals s ON s.order_id=l.order_id
 LEFT JOIN return_totals r ON r.order_id=l.order_id
"""), ('totals', """
 SELECT id, SUM(CASE WHEN active=1 THEN base_qty ELSE 0 END) AS ordered_base,
 SUM(received) AS received_base, SUM(returned) AS returned_base,
 MAX(order_invalid) AS order_invalid, MAX(receipt_invalid) AS receipt_invalid, MAX(return_invalid) AS return_invalid,
 MAX(CASE WHEN active=1 THEN order_date ELSE NULL END) AS last_order_date,
 MAX(last_stock_date) AS last_stock_date,
 CASE WHEN COUNT(DISTINCT supplier_id)>1 THEN N'多家供应商' ELSE MAX(supplier_name) END AS supplier_name
 FROM allocated GROUP BY id
"""), ('base_amounts', """
 SELECT q.*, t.last_order_date, t.last_stock_date, t.supplier_name,
 CASE WHEN COALESCE(t.order_invalid,0)=0 AND q.approved>0 AND q.approved_base>0
 THEN COALESCE(t.ordered_base,0) ELSE NULL END AS ordered_base,
 CASE WHEN COALESCE(t.order_invalid,0)=0 AND COALESCE(t.receipt_invalid,0)=0 AND q.approved>0 AND q.approved_base>0
 THEN COALESCE(t.received_base,0) ELSE NULL END AS received_base,
 CASE WHEN COALESCE(t.order_invalid,0)=0 AND COALESCE(t.receipt_invalid,0)=0 AND COALESCE(t.return_invalid,0)=0 AND q.approved>0 AND q.approved_base>0
 THEN COALESCE(t.returned_base,0) ELSE NULL END AS returned_base
 FROM q LEFT JOIN totals t ON t.id=q.id
"""), ('base_balances', """
 SELECT base_amounts.*,
 -- SUM of signed operands retains SQL Server's aggregate decimal scale;
 -- subtracting decimal(38,s) aggregates directly can reduce that scale.
 CASE WHEN received_base IS NOT NULL AND returned_base IS NOT NULL THEN
 (SELECT SUM(v.qty) FROM (SELECT received_base AS qty UNION ALL SELECT -returned_base) v)
 ELSE NULL END AS net_received_base,
 CASE WHEN document_status='C' AND cancel_status='A' AND ordered_base IS NOT NULL THEN
 (SELECT SUM(v.qty) FROM (SELECT approved_base AS qty UNION ALL SELECT -ordered_base) v)
 ELSE NULL END AS pending_order_base,
 CASE WHEN ordered_base IS NOT NULL AND received_base IS NOT NULL AND returned_base IS NOT NULL THEN
 (SELECT SUM(v.qty) FROM (SELECT ordered_base AS qty UNION ALL SELECT -received_base UNION ALL SELECT returned_base) v)
 ELSE NULL END AS pending_receipt_base FROM base_amounts
"""), ('balances', """
 SELECT base_balances.*,
 CAST(ordered_base*1.0*approved/NULLIF(approved_base,0) AS decimal(28,8)) AS ordered,
 CAST(received_base*1.0*approved/NULLIF(approved_base,0) AS decimal(28,8)) AS received,
 CAST(returned_base*1.0*approved/NULLIF(approved_base,0) AS decimal(28,8)) AS returned,
 CAST(net_received_base*1.0*approved/NULLIF(approved_base,0) AS decimal(28,8)) AS net_received,
 CAST(pending_order_base*1.0*approved/NULLIF(approved_base,0) AS decimal(28,8)) AS pending_order,
 CAST(pending_receipt_base*1.0*approved/NULLIF(approved_base,0) AS decimal(28,8)) AS pending_receipt
 FROM base_balances
"""), ('report', """
 SELECT balances.*, CASE
 WHEN pending_order_base IS NULL OR pending_receipt_base IS NULL OR pending_order_base<0 OR pending_receipt_base<0 THEN 'review'
 WHEN ordered_base=0 THEN 'not_ordered' WHEN pending_order_base>0 THEN 'ordering'
 WHEN pending_receipt_base>0 THEN 'receiving' ELSE 'complete' END AS progress FROM balances
""")]


def _like(text):
    return '%' + text.replace('~', '~~').replace('%', '~%').replace('_', '~_').replace('[', '~[') + '%'


def request_query(query, project_codes):
    scope, params = scope_clause('a.FNUMBER', project_codes)
    filters = [scope, 'h.FAPPLICATIONDATE >= %s']
    params.append(REPORT_START_DATE)
    if query.keyword:
        filters.append("(h.FBILLNO LIKE %s ESCAPE '~' OR m.FNUMBER LIKE %s ESCAPE '~' OR ml.FNAME LIKE %s ESCAPE '~' OR ml.FSPECIFICATION LIKE %s ESCAPE '~')")
        params.extend([_like(query.keyword)] * 4)
    if query.project_code:
        filters.append('a.FNUMBER=%s')
        params.append(query.project_code)
    if query.date_from:
        filters.append('h.FAPPLICATIONDATE >= %s')
        params.append(query.date_from)
    if query.date_to:
        # Calendar comparison includes all timestamps on the selected end date.
        filters.append('h.FAPPLICATIONDATE < %s')
        params.append(query.date_to + timedelta(days=1))
    if query.supplier:
        filters.append("""EXISTS (SELECT 1 FROM dbo.T_PUR_POORDERENTRY_LK sl
 JOIN dbo.T_PUR_POORDERENTRY se ON se.FENTRYID=sl.FENTRYID
 JOIN dbo.T_PUR_POORDER sh ON sh.FID=se.FID
 JOIN dbo.T_BD_SUPPLIER_L sn ON sn.FSUPPLIERID=sh.FSUPPLIERID AND sn.FLOCALEID=2052
 WHERE LOWER(sl.FSTABLENAME)='t_pur_reqentry' AND sl.FSID=e.FENTRYID AND sl.FSBILLID=e.FID
 AND sh.FPURCHASEORGID=h.FAPPLICATIONORGID
 AND se.FMATERIALID=e.FMATERIALID AND se.FBASEUNITID=e.FBASEUNITID
 AND (SELECT COUNT(*) FROM dbo.T_PUR_POORDERENTRY_LK all_links WHERE all_links.FENTRYID=se.FENTRYID)=1
 AND sn.FNAME LIKE %s ESCAPE '~')""")
        params.append(_like(query.supplier))
    return REQUEST_SELECT + ' WHERE ' + ' AND '.join(filters), params


def list_requests(connection, query, project_codes):
    import re
    import time
    _prepare_scope(connection, project_codes)
    base, params = request_query(query, project_codes)
    if not query.progress:
        return _page_then_summarize(connection, query, base, params)
    deadline = time.monotonic() + 25
    names = ['q', *(name for name, _ in ACCOUNTING_STAGES)]
    # Session-local tempdb worksets avoid SQL Server repeatedly expanding a
    # deep CTE graph. They require no writes or indexes in the ERP database.
    reference = re.compile(r'\b(' + '|'.join(names) + r')\b')
    cursor = connection.cursor()
    created = []
    try:
        for name, select in [('q', base), *ACCOUNTING_STAGES]:
            if time.monotonic() > deadline:
                raise TimeoutError('report_budget_exceeded')
            select = reference.sub(lambda match: '#pms_purchase_' + match.group(0), select)
            cursor.execute(f'WITH workset AS ({select}) SELECT * INTO #pms_purchase_{name} FROM workset',
                           tuple(params) if name == 'q' else ())
            created.append(name)
        where = ' WHERE progress=%s' if query.progress else ''
        params = [query.progress] if query.progress else []
        total = _rows(connection, 'SELECT COUNT(*) AS total FROM #pms_purchase_report' + where, params)[0]['total']
        sort = {'date': 'application_date', 'bill_no': 'bill_no', 'project_code': 'project_code',
                'material_code': 'material_code'}[query.sort]
        sql = f'WITH numbered AS (SELECT *, ROW_NUMBER() OVER (ORDER BY {sort} {query.direction}, id {query.direction}) AS row_number FROM #pms_purchase_report{where})'
        start = (query.page - 1) * query.page_size
        items = _rows(connection, sql + ' SELECT * FROM numbered WHERE row_number>%s AND row_number<=%s ORDER BY row_number',
                      [*params, start, start + query.page_size]) if total else []
        _decorate_rows(connection, _with_state(items))
        return dict(total=total, items=items, page=query.page, page_size=query.page_size)
    finally:
        try:
            for name in reversed(created):
                cursor.execute(f'DROP TABLE #pms_purchase_{name}', ())
        finally:
            cursor.close()


def progress_for(summary):
    pending_order = summary.get('pending_order_base', summary['pending_order'])
    pending_receipt = summary.get('pending_receipt_base', summary['pending_receipt'])
    if pending_order is None or pending_receipt is None or pending_order < 0 or pending_receipt < 0:
        return 'review'
    if summary.get('ordered_base', summary['ordered']) == 0:
        return 'not_ordered'
    if pending_order > 0:
        return 'ordering'
    return 'receiving' if pending_receipt > 0 else 'complete'


def _page_then_summarize(connection, query, base, params):
    total = _rows(connection, 'WITH q AS (' + base + ') SELECT COUNT(*) AS total FROM q', params)[0]['total']
    sort = {'date': 'application_date', 'bill_no': 'bill_no', 'project_code': 'project_code', 'material_code': 'material_code'}[query.sort]
    start = (query.page - 1) * query.page_size
    sql = f'WITH q AS ({base}), numbered AS (SELECT *, ROW_NUMBER() OVER (ORDER BY {sort} {query.direction}, id {query.direction}) AS row_number FROM q) SELECT * FROM numbered WHERE row_number>%s AND row_number<=%s ORDER BY row_number'
    items = _with_state(_rows(connection, sql, [*params, start, start + query.page_size])) if total else []
    _decorate_rows(connection, items)
    return dict(total=total, items=items, page=query.page, page_size=query.page_size)


def _decorate_rows(connection, items):
    chains = load_chains(connection, items)
    for row in items:
        chain = chains[row['id']]
        row.update(chain['summary'])
        row['progress'] = progress_for(chain['summary'])
        for key, documents in (('order_statuses', chain['orders']), ('stock_statuses', chain['receipts'])):
            row[key] = '、'.join(sorted({DOCUMENT_STATUSES.get(document['document_status'], '未知状态')
                                        for document in documents}))
        orders = [order for order in chain['orders'] if order['effective'] is True]
        stocks = [stock for stock in chain['receipts'] if stock['effective'] is True]
        row['last_order_date'] = max((order['order_date'] for order in orders if order['order_date']), default=None)
        row['last_stock_date'] = max((stock['stock_date'] for stock in stocks if stock['stock_date']), default=None)
        suppliers = {order['supplier_id']: order['supplier_name'] for order in chain['orders'] if order['supplier_id']}
        row['supplier_name'] = '多家供应商' if len(suppliers) > 1 else next(iter(suppliers.values()), None)


def list_options(connection, field, keyword, project_codes):
    _prepare_scope(connection, project_codes)
    base, params = request_query(PurchaseQuery(), project_codes)
    if field == 'project':
        choices = "SELECT DISTINCT project_code AS value FROM q WHERE project_code IS NOT NULL AND project_code<>'' AND project_code LIKE %s ESCAPE '~'"
    elif field == 'supplier':
        choices = """SELECT DISTINCT sn.FNAME AS value FROM q
 JOIN dbo.T_PUR_POORDERENTRY_LK l ON l.FSID=q.id AND l.FSBILLID=q.bill_id AND LOWER(l.FSTABLENAME)='t_pur_reqentry'
 JOIN dbo.T_PUR_POORDERENTRY e ON e.FENTRYID=l.FENTRYID JOIN dbo.T_PUR_POORDER h ON h.FID=e.FID
 JOIN dbo.T_BD_SUPPLIER_L sn ON sn.FSUPPLIERID=h.FSUPPLIERID AND sn.FLOCALEID=2052
 WHERE h.FPURCHASEORGID=q.organization_id
 AND e.FMATERIALID=q.material_id AND e.FBASEUNITID=q.base_unit_id
 AND (SELECT COUNT(*) FROM dbo.T_PUR_POORDERENTRY_LK all_links WHERE all_links.FENTRYID=e.FENTRYID)=1
 AND sn.FNAME LIKE %s ESCAPE '~'"""
    else:
        raise ValueError('invalid_option_field')
    sql = f'WITH q AS ({base}), choices AS ({choices}), numbered AS (SELECT value, ROW_NUMBER() OVER (ORDER BY value) AS n FROM choices) SELECT value FROM numbered WHERE n<=51 ORDER BY n'
    values = _rows(connection, sql, [*params, _like(keyword)])
    return dict(items=[dict(value=row['value'], label=row['value']) for row in values[:50]], has_more=len(values) > 50)
