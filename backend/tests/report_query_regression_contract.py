"""Adversarial query regressions; all data and connections are offline fixtures."""
import json
import re
import unittest
from decimal import Decimal

import purchase_reader_contract as fixture
from report_query_v2_contract import Connection, V2Cursor, condition, column_condition, column_values
from app.services.inventory_reader import InventoryQuery, KEYS, list_inventory
from app.services.purchase_reader import PurchaseQuery, request_query, list_requests
from app.services.report_column_candidates import inventory_candidates, purchase_candidates
from app.services.report_export_data import inventory_batches
from pymssql import _mssql


class InventoryCursor(V2Cursor):
    def execute(self, sql, params=()):
        if ' OFFSET %s ROWS FETCH NEXT %s ROWS ONLY' in sql:
            sql = sql.replace(' OFFSET %s ROWS FETCH NEXT %s ROWS ONLY', ' LIMIT %s OFFSET %s')
            params = [*params[:-2], params[-1], params[-2]]
        super().execute(sql.replace('COUNT_BIG(*)', 'COUNT(*)'), params)

    def fetchone(self):
        row = self.cursor.fetchone()
        return dict(row) if row is not None else None


class InventoryConnection(Connection):
    def cursor(self):
        return InventoryCursor(self.db)


class ReportQueryRegressions(unittest.TestCase):
    def setUp(self):
        self.source = fixture.ReaderContract()
        self.addCleanup(self.source.doCleanups)
        self.db, _ = self.source.classification_fixture()
        self.connection = Connection(self.db)

    def test_inventory_empty_condition_cannot_bypass_scope_in_any_read_path(self):
        self.db.execute('CREATE TABLE YD_JIN_INVENTORY (' + ','.join(f'[{key}]' for key in KEYS) + ')')
        self.db.execute('CREATE TABLE T_STK_INVENTORY (FID, FSTOCKORGID)')
        for key, stock, org, material, quantity in (
                ('a', None, 100, 'allowed-null', 1),
                ('b', '', 100, 'allowed-empty', 1),
                ('c', ' ', 100, 'allowed-space', 1),
                ('d', None, 200, 'secret-null', 1),
                ('e', '', 200, 'secret-empty', 1),
                ('f', ' ', 200, 'secret-space', 1),
                ('g', None, 100, 'wrong-quantity', 9)):
            self.db.execute('INSERT INTO YD_JIN_INVENTORY(FID,Stock,MaterialCode,FBaseQty) VALUES(?,?,?,?)',
                            (key, stock, material, quantity))
            self.db.execute('INSERT INTO T_STK_INVENTORY VALUES(?,?)', (key, org))
        connection = InventoryConnection(self.db)
        for location in ('top', 'column'):
            with self.subTest(location=location):
                empty = condition('Stock', 'isEmpty') if location == 'top' else '[]'
                columns = column_condition('Stock', 'isEmpty') if location == 'column' else '[]'
                filters = json.dumps([*json.loads(empty), *json.loads(condition('FBaseQty', 'equals', 1))])
                query = InventoryQuery(filters=filters, column_filters=columns, page_size=1, page=2)
                listed = list_inventory(connection, query, [100])
                self.assertEqual(listed['total'], 3)
                self.assertEqual([row['FID'] for row in listed['items']], ['b'])
                candidates = inventory_candidates(connection, query, [100], 'MaterialCode')
                self.assertEqual(candidates['total'], 3)
                self.assertEqual({row['value'] for row in candidates['items']},
                                 {'allowed-null', 'allowed-empty', 'allowed-space'})
                exported = [row for batch in inventory_batches(connection, query, [100]) for row in batch]
                self.assertEqual([row['FID'] for row in exported], ['a', 'b', 'c'])

    def test_purchase_derived_candidates_calculate_without_derived_conditions(self):
        self.db.execute("UPDATE T_PUR_POORDER SET FDATE='2026-06-01'")
        self.db.execute("UPDATE T_STK_INSTOCK SET FDATE='2026-06-02'")
        expected = {'ordered': Decimal(1), 'received': Decimal(1), 'returned': Decimal(0),
                    'net_received': Decimal(1), 'pending_order': Decimal(0),
                    'pending_receipt': Decimal(0), 'progress': 'complete',
                    'last_order_date': '2026-06-01', 'last_stock_date': '2026-06-02'}
        for field, value in expected.items():
            for exclude_self in (False, True):
                with self.subTest(field=field, exclude_self=exclude_self):
                    columns = [*json.loads(column_values('bill_no', ['R4']))]
                    if exclude_self:
                        columns += json.loads(column_values(field, []))
                    query = PurchaseQuery(column_filters=json.dumps(columns), page_size=1)
                    try:
                        result = purchase_candidates(self.connection, query, fixture.GRANTS, field)
                    except Exception as error:
                        self.fail(f'{field} candidates must compute before selection: {error}')
                    self.assertEqual(result['total'], 1)
                    actual = result['items'][0]['value']
                    self.assertEqual(Decimal(str(actual)) if isinstance(value, Decimal) else actual, value)
                    self.assertEqual(len(json.loads(query.column_filters)), len(columns))
        self.db.execute('UPDATE T_PUR_REQUISITION SET FAPPLICATIONORGID=200 WHERE FID=4')
        try:
            result = purchase_candidates(self.connection, PurchaseQuery(column_filters=column_values('bill_no', ['R4'])),
                                         fixture.GRANTS, 'progress')
        except Exception as error:
            self.fail(f'Empty scoped derived candidates must remain valid: {error}')
        self.assertEqual(result['total'], 0)

    def test_purchase_source_candidates_do_not_create_accounting_worksets(self):
        statements = []
        connection = self.connection

        class TracedCursor(V2Cursor):
            def execute(self, sql, params=()):
                statements.append(sql)
                super().execute(sql, params)

        class TracedConnection(Connection):
            def cursor(self):
                return TracedCursor(self.db)

        result = purchase_candidates(TracedConnection(connection.db), PurchaseQuery(), fixture.GRANTS, 'bill_no')
        self.assertEqual(result['total'], 9)
        self.assertFalse(any('SELECT * INTO' in sql for sql in statements))

    def test_null_project_labels_generate_mssql_legal_typed_results(self):
        for labels in ({('P-1', 100): None}, {}):
            with self.subTest(labels=labels):
                query = PurchaseQuery(filters=condition('project_name', 'isEmpty'))
                query._query_labels = {'project_name': labels}
                sql, params = request_query(query, fixture.GRANTS)
                driver_sql = _mssql.substitute_params(sql, tuple(params)).decode('utf-8')
                self.assertNotRegex(driver_sql, r'CASE(?:\s+WHEN .*? THEN NULL)+\s+ELSE NULL END')
                self.assertNotIn('label_source.*,NULL AS [project_name]', driver_sql)
                self.assertEqual(sql.count('%s'), len(params))
                self.assertEqual(list_requests(self.connection, query, fixture.GRANTS)['total'], 9)
                candidates = purchase_candidates(self.connection, query, fixture.GRANTS, 'project_name')
                self.assertEqual([row['value'] for row in candidates['items']], [None])


if __name__ == '__main__':
    unittest.main()
