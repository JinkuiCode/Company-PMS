"""Batch reads reuse report filters and verified document-chain authorization."""
import json
from app.services.report_workbook import ReportWorkbook
from app.services.purchase_connection import purchase_connection
from app.services.purchase_fields import DOCUMENT_STATUSES, PROGRESS_LABELS
from app.services.report_export_jobs import fields_for

PARENT_FIELDS = [('request_bill_no', '申请单编号'), ('request_line_no', '申请单行号'),
    ('project_code', '项目编号'), ('material_code', '物料编码'), ('material_name', '物料名称')]
ORDER_FIELDS = [('bill_no', '采购订单编号'), ('line_no', '订单行号'), ('order_date', '订单日期'),
    ('document_status', '数据状态'), ('cancel_status', '作废状态'), ('close_status', '关闭状态'),
    ('quantity', '采购数量'), ('unit_name', '采购单位'), ('supplier_name', '供应商'), ('effective_label', '计入有效数量')]
RECEIPT_FIELDS = [('order_bill_no', '采购订单编号'), ('order_line_no', '订单行号'),
    ('supplier_name', '供应商'), ('bill_no', '入库单编号'), ('line_no', '入库行号'),
    ('stock_date', '入库日期'), ('document_status', '数据状态'), ('cancel_status', '作废状态'),
    ('quantity', '实收数量'), ('unit_name', '库存单位'), ('effective_label', '计入有效数量')]


def detail_sheets(book):
    return book.sheet('订单明细', PARENT_FIELDS + ORDER_FIELDS), book.sheet('入库明细', PARENT_FIELDS + RECEIPT_FIELDS)


def labels(row):
    return dict(row, document_status=DOCUMENT_STATUSES.get(row.get('document_status'), '未知状态'),
        cancel_status={'A': '未作废', 'B': '已作废'}.get(row.get('cancel_status'), ''),
        close_status={'A': '未关闭', 'B': '已关闭'}.get(row.get('close_status'), ''),
        effective_label={True: '是', False: '否', None: '待核对'}.get(row.get('effective'), '待核对'),
        progress=PROGRESS_LABELS.get(row.get('progress'), '数据待核对'))


def append_purchase(main, orders, receipts, row, chain):
    main.append(labels(row))
    parent = {key: row.get(key) for key in ('project_code', 'material_code', 'material_name')}
    parent.update(request_bill_no=row.get('bill_no'), request_line_no=row.get('line_no'))
    order_map = {order['id']: order for order in chain['orders']}
    for order in chain['orders']:
        orders.append(dict(labels(order), **parent))
    for receipt in chain['receipts']:
        order = order_map[receipt['order_id']]
        receipts.append(dict(labels(receipt), **parent, order_bill_no=order['bill_no'],
            order_line_no=order['line_no'], supplier_name=order.get('supplier_name')))


def inventory_batches(connection, query, organizations):
    from app.services.inventory_reader import effective_organizations, where_clause, KEYS, SOURCE
    organizations = effective_organizations(query, organizations)
    if organizations == []:
        return
    where, params = where_clause(query, organizations)
    ordering = f'v.[{query.sort}] {query.direction.upper()}'
    ordering += ''.join(f',v.[{key}] ASC' for key in KEYS if key != query.sort)
    cursor = connection.cursor()
    try:
        cursor.execute('SELECT '+','.join(f'v.[{key}]' for key in KEYS)+SOURCE+where+' ORDER BY '+ordering, tuple(params))
        while rows := cursor.fetchmany(500):
            yield rows
    finally:
        cursor.close()


def purchase_batches(connection, query, scope):
    from app.services.purchase_reader import _prepare_scope, request_query, _rows, _with_state
    _prepare_scope(connection, scope)
    base, params = request_query(query, scope)
    cursor = connection.cursor()
    created = []
    try:
        # Materialize the selected request rows once so edits cannot shift later pages.
        sort = {'date': 'application_date', 'bill_no': 'bill_no', 'project_code': 'project_code', 'material_code': 'material_code'}[query.sort]
        cursor.execute(f'WITH q AS ({base}) SELECT *, ROW_NUMBER() OVER (ORDER BY {sort} {query.direction}, id {query.direction}) AS export_row INTO #pms_export_selected FROM q', tuple(params))
        created.append('selected')
        cursor.execute('CREATE UNIQUE CLUSTERED INDEX ix_export_row ON #pms_export_selected(export_row)')
        start = 0
        while True:
            rows = _rows(connection, 'SELECT * FROM #pms_export_selected WHERE export_row>%s AND export_row<=%s ORDER BY export_row', [start, start+200])
            if not rows:
                break
            yield _with_state(rows)
            start += len(rows)
    finally:
        try:
            for name in reversed(created):
                cursor.execute(f'DROP TABLE #pms_export_{name}')
        finally:
            cursor.close()


def matches_progress(query, row):
    return not query.progress or query.progress == row.get('progress')


def write_report(db, job, ctx, path, checkpoint):
    fields = {field['key']: field for field in fields_for(job.report)}
    columns = json.loads(job.columns)
    if job.report == 'purchase':
        # Always retain human-readable linkage, even if hidden in the screen layout.
        columns = list(dict.fromkeys(['bill_no', 'line_no', *columns]))
    with ReportWorkbook(path) as book, purchase_connection() as connection:
        main = book.sheet('即时库存' if job.report == 'inventory' else '采购申请主表',
            [(key, fields[key]['label']) for key in columns])
        count = 0
        if job.report == 'inventory':
            from app.services.inventory_reader import InventoryQuery
            from app.api.inventory_reports import authorized_organizations
            query = InventoryQuery.model_validate_json(job.parameters)
            for batch in inventory_batches(connection, query, authorized_organizations(db, ctx)):
                checkpoint(count)
                for row in batch:
                    main.append(row)
                count += len(batch)
                checkpoint(count)
        else:
            from app.services.purchase_reader import PurchaseQuery, load_chains, _decorate_rows
            from app.api.purchase_reports import project_scope, enrich_project_names
            query = PurchaseQuery.model_validate_json(job.parameters)
            orders, receipts = detail_sheets(book)
            for batch in purchase_batches(connection, query, project_scope(db, ctx)):
                checkpoint(count)
                chains = load_chains(connection, batch)
                _decorate_rows(connection, batch, chains=chains)
                enrich_project_names(db, ctx, batch)
                for row in batch:
                    if not matches_progress(query, row):
                        continue
                    append_purchase(main, orders, receipts, row, chains[row['id']])
                    count += 1
                checkpoint(count)
