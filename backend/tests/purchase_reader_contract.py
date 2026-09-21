"""Reader contracts use a small relational ERP fixture, never production writes."""
import importlib.util
from pathlib import Path
import sys
import unittest
import sqlite3
import re
from datetime import date


class SqliteCursor:
    def __init__(self, db):
        self.cursor = db.cursor()

    def execute(self, sql, params):
        sql = sql.replace('dbo.', '').replace('%s', '?').replace("N'", "'").replace('#pms_', 'temp_pms_')
        # SQLite ignores DECIMAL scale; emulate the report's display rounding so
        # classification tests cannot accidentally depend on its unrounded casts.
        sql = sql.replace('CAST(', 'ROUND(').replace(' AS decimal(28,8))', ', 8)')
        match = re.fullmatch(r'WITH workset AS \((.*)\) SELECT \* INTO (\w+) FROM workset', sql, re.S)
        if match:
            sql = f'CREATE TEMP TABLE {match[2]} AS {match[1]}'
        self.cursor.execute(sql, tuple(value.isoformat() if isinstance(value, date) else value for value in params))

    def fetchall(self):
        return [dict(row) for row in self.cursor.fetchall()]

    def close(self):
        self.cursor.close()


class FixtureConnection:
    def __init__(self, db):
        self.db = db

    def cursor(self):
        return SqliteCursor(self.db)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ReaderContract(unittest.TestCase):
    def reader(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.purchase_reader'),
                             'The approved read-only ERP adapter is not implemented')
        from app.services import purchase_reader
        return purchase_reader

    def test_states_are_decoded_not_treated_as_truthy(self):
        reader = self.reader()
        self.assertIs(reader.effective_state('C', 'A'), True)
        self.assertIs(reader.effective_state('C', 'B'), False)
        for state in ('A', 'B', 'D', 'Z'):
            self.assertIs(reader.effective_state(state, 'A'), False)
        self.assertIsNone(reader.effective_state('NEW', 'A'))
        self.assertIsNone(reader.effective_state('C', None))

    def test_scope_is_fail_closed_and_parameterized(self):
        reader = self.reader()
        sql, params = reader.scope_clause('project_code', [])
        self.assertEqual(sql, '1=0')
        self.assertEqual(params, [])
        code = "X'; DROP TABLE demo;--"
        sql, params = reader.scope_clause('project_code', [code, 'A'])
        self.assertNotIn(code, sql)
        self.assertEqual(params, [code, 'A'])
        self.assertEqual(reader.scope_clause('project_code', None), ('1=1', []))
        with self.assertRaises(ValueError):
            reader.scope_clause('project_code', ['x'] * 2001)

    def test_receipt_edges_check_source_identity(self):
        reader = self.reader()
        stock = dict(id=8, bill_id=9, order_id=4, material_id=5, base_unit_id=6, base_qty=3)
        order = dict(id=4, bill_id=40, material_id=5, base_unit_id=6)
        edge = dict(source_table='t_PUR_POOrderEntry', source_id=4, source_bill_id=40, base_qty=3)
        self.assertTrue(reader.receipt_source_valid(stock, [edge], order, {}))
        self.assertFalse(reader.receipt_source_valid(stock, [dict(edge, source_bill_id=41)], order, {}))
        self.assertFalse(reader.receipt_source_valid(stock, [edge, edge], order, {}))
        self.assertFalse(reader.receipt_source_valid(stock, [dict(edge, base_qty=2)], order, {}))
        self.assertFalse(reader.receipt_source_valid(dict(stock, material_id=999), [edge], order, {}))

    def test_receiving_route_requires_same_order_material_and_unit(self):
        reader = self.reader()
        stock = dict(id=8, bill_id=9, order_id=4, material_id=5, base_unit_id=6, base_qty=3)
        order = dict(id=4, bill_id=40, material_id=5, base_unit_id=6)
        edge = dict(source_table='T_PUR_ReceiveEntry', source_id=7, source_bill_id=70, base_qty=3)
        receiving = dict(id=7, bill_id=70, order_id=4, material_id=5, base_unit_id=6)
        self.assertTrue(reader.receipt_source_valid(stock, [edge], order, {7: receiving}))
        self.assertFalse(reader.receipt_source_valid(stock, [edge], order, {7: dict(receiving, order_id=41)}))

    def test_limits_and_sort_are_not_arbitrary_sql(self):
        reader = self.reader()
        for bad in (0, -1, 501):
            with self.assertRaises(ValueError):
                reader.PurchaseQuery(page_size=bad)
        with self.assertRaises(ValueError):
            reader.PurchaseQuery(sort='FBILLNO; DROP TABLE demo')
        with self.assertRaises(ValueError):
            reader.PurchaseQuery(date_from='2026-09-22', date_to='2026-09-01')

    def classification_fixture(self):
        import runpy
        schema = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/provision_purchase_reader.py'))['TABLES']
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        self.addCleanup(db.close)
        for table, fields in schema.items():
            db.execute(f'CREATE TABLE {table} ({", ".join(fields.split())})')
        def put(table, **values):
            db.execute(f'INSERT INTO {table} ({",".join(values)}) VALUES ({",".join("?" for _ in values)})', tuple(values.values()))
        # Each row is independently classified; the displayed unit is 1/3 of a base unit.
        for number, ordered, received in [(1, 0, 0), (2, 1, 0), (3, 3, 0),
                                           (4, 3, 3), (5, 4, 0), (6, 3.000000001, 0),
                                           (7, 2.999999999, 0), (8, 3, 3.000000001),
                                           (9, 3, 2.999999999)]:
            put('T_PUR_REQUISITION', FID=number, FBILLNO=f'R{number}', FAPPLICATIONDATE='2026-01-01',
                FDOCUMENTSTATUS='C', FCANCELSTATUS='A')
            put('T_PUR_REQENTRY', FENTRYID=number, FID=number, FSEQ=1, FMATERIALID=10,
                FUNITID=2, FBASEUNITID=1, FREQQTY=1, FAPPROVEQTY=1, FBASEUNITQTY=3)
            if not ordered:
                continue
            put('T_PUR_POORDER', FID=number, FDOCUMENTSTATUS='C', FCANCELSTATUS='A')
            put('T_PUR_POORDERENTRY', FENTRYID=number, FID=number, FMATERIALID=10, FBASEUNITID=1)
            put('T_PUR_POORDERENTRY_LK', FENTRYID=number, FLINKID=number, FSTABLENAME='T_PUR_REQENTRY',
                FSID=number, FSBILLID=number, FBASEUNITQTY=ordered)
            if received:
                put('T_STK_INSTOCK', FID=number, FDOCUMENTSTATUS='C', FCANCELSTATUS='A')
                put('T_STK_INSTOCKENTRY', FENTRYID=number, FID=number, FPOORDERENTRYID=number,
                    FMATERIALID=10, FBASEUNITID=1, FBASEUNITQTY=received)
                put('T_STK_INSTOCKENTRY_LK', FENTRYID=number, FSTABLENAME='T_PUR_POORDERENTRY',
                    FSID=number, FSBILLID=number, FBASEUNITQTY=received)
        return db, FixtureConnection(db)

    def assert_classification_sets(self, connection, expected):
        reader = self.reader()
        plain = reader.list_requests(connection, reader.PurchaseQuery(), None)
        for progress in ('not_ordered', 'ordering', 'receiving', 'complete', 'review'):
            ids = expected.get(progress, set())
            with self.subTest(progress=progress, path='python'):
                self.assertEqual({row['id'] for row in plain['items'] if row['progress'] == progress}, ids)
            with self.subTest(progress=progress, path='sql_filter'):
                selected = reader.list_requests(connection, reader.PurchaseQuery(progress=progress), None)
                self.assertEqual({row['id'] for row in selected['items']}, ids)
                self.assertEqual(selected['total'], len(ids))
                self.assertTrue(all(row['progress'] == progress for row in selected['items']))
                # Count and membership must also survive server pagination.
                paged_ids = set()
                for page in range(1, len(ids) + 2):
                    part = reader.list_requests(connection, reader.PurchaseQuery(progress=progress, page=page, page_size=1), None)
                    self.assertEqual(part['total'], len(ids))
                    paged_ids.update(row['id'] for row in part['items'])
                self.assertEqual(paged_ids, ids)

    def test_progress_filter_sets_use_unrounded_base_balances(self):
        _, connection = self.classification_fixture()
        self.assert_classification_sets(connection, dict(not_ordered={1}, ordering={2, 7},
            receiving={3, 9}, complete={4}, review={5, 6, 8}))

    def test_orphan_links_are_review_even_when_all_orders_are_missing(self):
        db, connection = self.classification_fixture()
        db.execute('DELETE FROM T_PUR_POORDERENTRY WHERE FENTRYID IN (2,3)')
        self.assert_classification_sets(connection, dict(not_ordered={1}, ordering={7},
            receiving={9}, complete={4}, review={2, 3, 5, 6, 8}))
        reader = self.reader()
        chain = reader.load_chains(connection, [reader.load_request(connection, 3, None)])[3]
        self.assertIsNone(chain['summary']['ordered'])
        self.assertIn('order_source_mismatch', chain['summary']['issues'])

    def test_null_source_identity_is_review(self):
        db, connection = self.classification_fixture()
        db.execute('UPDATE T_PUR_POORDERENTRY_LK SET FSBILLID=NULL WHERE FENTRYID=2')
        db.execute('UPDATE T_PUR_POORDERENTRY SET FMATERIALID=NULL WHERE FENTRYID=3')
        db.execute('UPDATE T_PUR_POORDERENTRY SET FBASEUNITID=NULL WHERE FENTRYID=4')
        self.assert_classification_sets(connection, dict(not_ordered={1}, ordering={7},
            receiving={9}, complete=set(), review={2, 3, 4, 5, 6, 8}))

    def test_null_stock_and_return_sources_fail_closed(self):
        for target, column in [('T_STK_INSTOCKENTRY', 'FMATERIALID'),
                               ('T_STK_INSTOCKENTRY', 'FBASEUNITID'),
                               ('T_PUR_MRBENTRY', 'FBASEUNITQTY'),
                               ('T_PUR_MRBENTRY', 'FMATERIALID'),
                               ('T_PUR_MRBENTRY', 'FBASEUNITID'),
                               ('T_PUR_MRBENTRY_LK', 'FSBILLID')]:
            with self.subTest(target=target, column=column):
                db, connection = self.classification_fixture()
                db.execute("INSERT INTO T_PUR_MRB (FID,FDOCUMENTSTATUS,FCANCELSTATUS) VALUES (4,'C','A')")
                db.execute('INSERT INTO T_PUR_MRBENTRY (FENTRYID,FID,FPOORDERENTRYID,FMATERIALID,FBASEUNITID,FBASEUNITQTY) VALUES (4,4,4,10,1,1)')
                db.execute("INSERT INTO T_PUR_MRBENTRY_LK (FENTRYID,FLINKID,FSTABLENAME,FSID,FSBILLID,FBASEUNITQTY) VALUES (4,4,'T_STK_INSTOCKENTRY',4,4,1)")
                db.execute(f'UPDATE {target} SET {column}=NULL WHERE FENTRYID=4')
                self.assert_classification_sets(connection, dict(not_ordered={1}, ordering={2, 7},
                    receiving={3, 9}, complete=set(), review={4, 5, 6, 8}))

    def test_public_document_statuses_include_all_distinct_labels(self):
        db, connection = self.classification_fixture()
        for number, status in [(20, 'A'), (21, 'B'), (22, 'NEW'), (23, 'OTHER'), (24, 'C')]:
            db.execute('INSERT INTO T_PUR_POORDER (FID,FDOCUMENTSTATUS,FCANCELSTATUS) VALUES (?,?,?)', (number, status, 'A'))
            db.execute('INSERT INTO T_PUR_POORDERENTRY (FENTRYID,FID,FMATERIALID,FBASEUNITID) VALUES (?,?,10,1)', (number, number))
            db.execute("INSERT INTO T_PUR_POORDERENTRY_LK (FENTRYID,FLINKID,FSTABLENAME,FSID,FSBILLID,FBASEUNITQTY) VALUES (?,?,'T_PUR_REQENTRY',4,4,0)", (number, number))
            db.execute('INSERT INTO T_STK_INSTOCK (FID,FDOCUMENTSTATUS,FCANCELSTATUS) VALUES (?,?,?)', (number, status, 'A'))
            db.execute('INSERT INTO T_STK_INSTOCKENTRY (FENTRYID,FID,FPOORDERENTRYID,FMATERIALID,FBASEUNITID,FBASEUNITQTY) VALUES (?,?,?,10,1,0)', (number, number, number))
            db.execute("INSERT INTO T_STK_INSTOCKENTRY_LK (FENTRYID,FSTABLENAME,FSID,FSBILLID,FBASEUNITQTY) VALUES (?,'T_PUR_POORDERENTRY',?,?,0)", (number, number, number))
        reader = self.reader()
        rows = reader.list_requests(connection, reader.PurchaseQuery(), None)['items']
        row = next(row for row in rows if row['id'] == 4)
        for key in ('order_statuses', 'stock_statuses'):
            self.assertIn(key, row)
            self.assertEqual(set(row[key].split('、')), {'创建', '审核中', '已审核', '未知状态'})
            self.assertEqual(row[key].count('未知状态'), 1)
        empty = next(row for row in rows if row['id'] == 1)
        self.assertEqual(empty['order_statuses'], '')
        self.assertEqual(empty['stock_statuses'], '')
        db.execute('UPDATE T_PUR_POORDERENTRY_LK SET FSBILLID=99 WHERE FENTRYID IN (20,21,22,23)')
        row = reader.list_requests(connection, reader.PurchaseQuery(keyword='R4'), None)['items'][0]
        self.assertEqual(row['order_statuses'], '已审核')
        self.assertEqual(row['stock_statuses'], '已审核')

    def test_relational_paging_filters_and_split_totals(self):
        reader = self.reader()
        self.assertTrue(hasattr(reader, 'list_requests'), 'Server-side report paging is missing')
        import runpy
        schema = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/provision_purchase_reader.py'))['TABLES']
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.row_factory = sqlite3.Row
        for table, fields in schema.items():
            db.execute(f'CREATE TABLE {table} ({", ".join(fields.split())})')
        def put(table, **values):
            db.execute(f'INSERT INTO {table} ({",".join(values)}) VALUES ({",".join("?" for _ in values)})', tuple(values.values()))
        put('T_BAS_ASSISTANTDATAENTRY', FENTRYID='project', FNUMBER='P-1')
        for number in range(1, 1006):
            put('T_PUR_REQUISITION', FID=number, FBILLNO=f'R{number:04}', FAPPLICATIONDATE='2026-09-01',
                FDOCUMENTSTATUS='C', FCANCELSTATUS='A', FCLOSESTATUS='A')
            put('T_PUR_REQENTRY', FENTRYID=number, FID=number, FSEQ=1, FMATERIALID=10,
                FUNITID=1, FBASEUNITID=1, FREQQTY=18, FAPPROVEQTY=18, FBASEUNITQTY=18,
                F_TWBJ_ASSISTANT_83G='project')
        put('T_PUR_REQUISITION', FID=9000, FBILLNO='HISTORY', FAPPLICATIONDATE='2025-12-31', FDOCUMENTSTATUS='C', FCANCELSTATUS='A')
        put('T_PUR_REQENTRY', FENTRYID=9000, FID=9000, FSEQ=1, FMATERIALID=10,
            FUNITID=1, FBASEUNITID=1, FREQQTY=18, FAPPROVEQTY=18, FBASEUNITQTY=18,
            F_TWBJ_ASSISTANT_83G='project')
        for order_id, qty in ((2001, 10), (2002, 8)):
            put('T_PUR_POORDER', FID=order_id, FBILLNO=f'O{order_id}', FDATE='2026-09-02', FDOCUMENTSTATUS='C', FCANCELSTATUS='A')
            put('T_PUR_POORDERENTRY', FENTRYID=order_id, FID=order_id, FSEQ=1, FMATERIALID=10, FBASEUNITID=1, FUNITID=1, FQTY=qty, FBASEUNITQTY=qty)
            put('T_PUR_POORDERENTRY_LK', FENTRYID=order_id, FLINKID=order_id, FSTABLENAME='t_PUR_ReqEntry', FSID=1, FSBILLID=1, FBASEUNITQTY=qty, FBASEUNITQTYOLD=18)
        for stock_id, qty in ((3001, 3), (3002, 5)):
            put('T_STK_INSTOCK', FID=stock_id, FBILLNO=f'S{stock_id}', FDATE='2026-09-03', FDOCUMENTSTATUS='C', FCANCELSTATUS='A')
            put('T_STK_INSTOCKENTRY', FENTRYID=stock_id, FID=stock_id, FSEQ=1, FMATERIALID=10, FBASEUNITID=1, FUNITID=1,
                FPOORDERENTRYID=2002, FREALQTY=qty, FBASEUNITQTY=qty)
            put('T_STK_INSTOCKENTRY_LK', FENTRYID=stock_id, FLINKID=stock_id, FSTABLENAME='T_PUR_POORDERENTRY', FSID=2002, FSBILLID=2002, FBASEUNITQTY=qty)
        connection = FixtureConnection(db)
        self.assertIsNone(reader.load_request(connection, 9000, None), 'Pre-2026 details must be excluded too')
        self.assertTrue(hasattr(reader, 'list_options'), 'Scoped report candidates are missing')
        self.assertEqual(reader.list_options(connection, 'project', '', [])['items'], [])
        self.assertEqual(reader.list_options(connection, 'project', 'P-', None)['items'], [{'value': 'P-1', 'label': 'P-1'}])
        page = reader.list_requests(connection, reader.PurchaseQuery(), None)
        self.assertEqual(page['total'], 1005)
        self.assertEqual(len(page['items']), 50)
        last = reader.list_requests(connection, reader.PurchaseQuery(page=21), ['P-1'])
        self.assertEqual(len(last['items']), 5)
        empty = reader.list_requests(connection, reader.PurchaseQuery(), [])
        self.assertEqual(empty['total'], 0)
        selected = reader.list_requests(connection, reader.PurchaseQuery(progress='receiving'), None)
        self.assertEqual(selected['total'], 1)
        row = selected['items'][0]
        self.assertEqual(row['id'], 1)
        self.assertEqual(row['ordered'], 18)
        self.assertEqual(row['net_received'], 8)
        self.assertEqual(row['pending_receipt'], 10)
        self.assertEqual(reader.list_requests(connection, reader.PurchaseQuery(keyword="' OR 1=1 --"), None)['total'], 0)
        self.assertEqual(reader.list_requests(connection, reader.PurchaseQuery(date_from='2026-09-02'), None)['total'], 0)
        self.assertEqual(reader.list_requests(connection, reader.PurchaseQuery(date_to='2026-08-31'), None)['total'], 0)
        detail = reader.load_chains(connection, [reader.load_request(connection, 1, None)])[1]
        self.assertEqual(detail['summary']['ordered'], 18)
        self.assertEqual(detail['summary']['received'], 8)
        # A current stock-source return reduces net receipts, never ordered qty.
        put('T_PUR_MRB', FID=4001, FBILLNO='RETURN', FDATE='2026-09-04', FDOCUMENTSTATUS='C', FCANCELSTATUS='A')
        put('T_PUR_MRBENTRY', FENTRYID=4001, FID=4001, FMATERIALID=10, FBASEUNITID=1, FPOORDERENTRYID=2002, FBASEUNITQTY=2)
        put('T_PUR_MRBENTRY_LK', FENTRYID=4001, FLINKID=4001, FSTABLENAME='T_STK_INSTOCKENTRY', FSID=3001, FSBILLID=3001, FBASEUNITQTY=2)
        row = reader.list_requests(connection, reader.PurchaseQuery(keyword='R0001'), None)['items'][0]
        self.assertEqual(row['returned'], 2)
        self.assertEqual(row['net_received'], 6)
        # Merging another requisition into this order makes receipt allocation unknown.
        put('T_PUR_POORDERENTRY_LK', FENTRYID=2002, FLINKID=5001, FSTABLENAME='T_PUR_REQENTRY', FSID=2, FSBILLID=2, FBASEUNITQTY=1)
        row = reader.list_requests(connection, reader.PurchaseQuery(keyword='R0001'), None)['items'][0]
        self.assertIsNone(row['net_received'])
        self.assertEqual(row['progress'], 'review')
        chain = reader.load_chains(connection, [reader.load_request(connection, 1, None)])[1]
        self.assertNotIn(2002, [order['id'] for order in chain['orders']], 'Do not disclose a merged order and receipts from another request')
        db.execute('DELETE FROM T_PUR_POORDERENTRY_LK WHERE FLINKID=5001')
        db.execute('UPDATE T_PUR_POORDERENTRY_LK SET FSBILLID=99 WHERE FLINKID=2001')
        chain = reader.load_chains(connection, [reader.load_request(connection, 1, None)])[1]
        self.assertNotIn(2001, [order['id'] for order in chain['orders']], 'Wrong source header must not expose a document')
        db.execute('UPDATE T_PUR_POORDERENTRY_LK SET FSBILLID=1 WHERE FLINKID=2001')
        db.execute('UPDATE T_PUR_MRBENTRY SET FBASEUNITQTY=4 WHERE FENTRYID=4001')
        row = reader.list_requests(connection, reader.PurchaseQuery(keyword='R0001'), None)['items'][0]
        self.assertIsNone(row['net_received'], 'Return entry and allocation quantity mismatch must fail closed')
        reviewed = reader.list_requests(connection, reader.PurchaseQuery(keyword='R0001', progress='review'), None)['items'][0]
        for field in ('ordered', 'received', 'returned', 'net_received', 'pending_order', 'pending_receipt'):
            self.assertEqual(row[field], reviewed[field], f'SQL/Python mismatch: {field}')
        self.assertEqual(reviewed['received'], 8, 'Return anomaly must not erase confirmed receipts')
        db.execute("UPDATE T_PUR_REQUISITION SET FAPPLICATIONDATE='2026-01-01' WHERE FID=2")
        boundary = reader.list_requests(connection, reader.PurchaseQuery(date_from='2025-01-01', date_to='2026-01-01'), None)
        self.assertEqual([item['id'] for item in boundary['items']], [2])
        self.assertIsNotNone(reader.load_request(connection, 2, None))
        self.assertEqual(reader.list_requests(connection, reader.PurchaseQuery(date_to='2025-12-31'), None)['total'], 0)


if __name__ == '__main__':
    unittest.main()
