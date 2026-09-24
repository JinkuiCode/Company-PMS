"""Offline contracts for shared typed filtering; no ERP connection."""
import json
from datetime import date, datetime
from decimal import Decimal as D
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.purchase_reader import PurchaseQuery, request_query, list_requests
from app.services.stock_detail_reader import StockDetailQuery, assemble_page
from app.services.business_data_scope import ALL_DATA_SCOPE
from app.services.stock_detail_balance import InventoryKey


def filters(field, operator, value=None, **extra):
    return json.dumps([dict(field=field, operator=operator, value=value, **extra)])


def stock_query(**changes):
    return StockDetailQuery(material='M', organization_ids=[1], start_date='2026-06-01',
                            end_date='2026-06-30', **changes)


class TypedFilters(unittest.TestCase):
    def test_validation_rejects_stale_and_injected_conditions(self):
        for factory, number, day in ((PurchaseQuery, 'approved', 'application_date'),
                                     (stock_query, 'balance_qty', 'bill_date')):
            for value in ('{}', 'null', '[', json.dumps([{}] * 21),
                          filters('bill_no]; DROP TABLE x--', 'equals', 'x'),
                          filters('bill_no', 'greaterThan', 'x'),
                          filters(number, 'contains', '1'), filters(number, 'equals', True),
                          filters(number, 'equals', 'NaN'), filters(number, 'equals', 'Infinity'),
                          filters(number, 'equals', '1e999999999'),
                          filters(number, 'equals', '1e-999999999'),
                          filters(number, 'equals', '1000000000000'),
                          filters(number, 'between', '2', valueEnd='1'),
                          filters(day, 'equals', '2026-02-30'),
                          filters(day, 'contains', '2026'),
                          filters(day, 'between', '2026-06-02', valueEnd='2026-06-01'),
                          filters('bill_no', 'equals', 'x', unknown=True),
                          filters('bill_no', 'equals', 'x', valueEnd='stale'),
                          filters('bill_no', 'isEmpty', 'stale')):
                with self.subTest(factory=factory, value=value), self.assertRaises(ValueError):
                    factory(filters=value)
        for value in ('invalid', '已审核'):
            with self.assertRaises(ValueError):
                PurchaseQuery(filters=filters('document_status', 'equals', value))

    def test_purchase_bound_values_and_calendar_date(self):
        attack = "x%' OR 1=1 --_["
        q = PurchaseQuery(filters=json.dumps([
            dict(field='bill_no', operator='contains', value=attack),
            dict(field='approved', operator='between', value='1.125', valueEnd='5'),
            dict(field='application_date', operator='equals', value='2026-06-01'),
            dict(field='document_status', operator='equals', value='C')]))
        sql, params = request_query(q, ALL_DATA_SCOPE)
        self.assertNotIn(attack, sql)
        self.assertIn("%x~%' OR 1=1 --~_~[%", params)
        self.assertIn(D('1.125'), params)
        self.assertIn(date(2026, 6, 1), params)
        self.assertIn('CAST(', sql)
        self.assertIn(' AND ', sql)

    def test_metadata_is_whitelisted_and_typed(self):
        from app.api.purchase_reports import metadata as purchase_metadata
        from app.api.stock_detail_reports import metadata as stock_metadata
        with patch('app.api.stock_detail_reports.scoped_lines', return_value=[]):
            stock = stock_metadata(None, {})
        for meta in (purchase_metadata({}), stock):
            self.assertIn('filter_fields', meta)
            fields = {f['field']: f for f in meta['filter_fields']}
            self.assertTrue(set(fields) <= {f['key'] for f in meta['fields']})
            self.assertEqual(fields['bill_no']['type'], 'text')
            self.assertIn('contains', fields['bill_no']['operators'])
        fields = {f['field']: f for f in purchase_metadata({})['filter_fields']}
        self.assertEqual(fields['approved']['type'], 'number')
        self.assertEqual(fields['document_status']['type'], 'enum')
        self.assertIn({'value': 'C', 'label': '已审核'}, fields['document_status']['options'])
        self.assertNotIn('project_name', fields)
        self.assertEqual(fields['progress']['type'], 'enum')
        self.assertEqual(fields['progress']['operators'], ['equals', 'notEquals'])
        self.assertEqual({v['value'] for v in fields['progress']['options']},
                         {'not_ordered', 'ordering', 'receiving', 'complete', 'review'})
        self.assertEqual(PurchaseQuery(progress='complete').progress, 'complete')
        for op, value in (('contains', 'complete'), ('isEmpty', None), ('equals', 'unknown'), ('equals', True)):
            with self.assertRaises(ValueError):
                PurchaseQuery(filters=filters('progress', op, value))
        self.assertEqual(stock['filter_semantics']['summary'], 'full_scope')
        self.assertEqual(stock['summary_scope_note'], '完整期间汇总（不随附加条件重算）')
        self.assertEqual(stock['opening_scope_note'], '期初保留完整查询范围（不随附加条件筛选）')

    def test_purchase_count_page_export_share_actual_predicate(self):
        from app.services.report_export_data import purchase_batches
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.execute('CREATE TABLE requests (id INT, bill_no TEXT, approved NUMERIC, application_date TEXT)')
        db.executemany('INSERT INTO requests VALUES (?,?,?,?)',
                       [(i, 'R'+str(i), i, '2026-06-01') for i in range(1, 7)])
        q = PurchaseQuery(filters=filters('approved', 'greaterThan', '3'), page_size=2)
        base, params = request_query(q, ALL_DATA_SCOPE)
        self.assertIn('approved', base.split(' WHERE ')[-1])
        # Execute the generated outer predicate against a local fixture, retaining
        # production list paging and export snapshot/batch orchestration.
        outer = base[base.rfind(') AS filter_source'):]
        selected = 'SELECT * FROM (SELECT * FROM requests' + outer
        cursor = Mock()
        exported = []
        def execute(sql, values=()):
            if 'INTO #pms_export_selected' in sql:
                exported.extend(dict(r) for r in db.execute(selected.replace('%s', '?'), tuple(str(v) if isinstance(v, D) else v for v in values[1:])))
        cursor.execute.side_effect = execute
        connection = Mock()
        connection.cursor.return_value = cursor
        def read(conn, sql, values):
            if '#pms_export_selected' in sql:
                return exported[values[0]:values[1]]
            source = sql.replace(base, selected).replace('%s', '?')
            return [dict(r) for r in db.execute(source, tuple(str(v) if isinstance(v, D) else v for v in values[1:]))]
        with patch('app.services.purchase_reader._prepare_scope'), \
             patch('app.services.purchase_reader._rows', side_effect=read), \
             patch('app.services.purchase_reader._with_state', side_effect=lambda rows: rows), \
             patch('app.services.purchase_reader._decorate_rows'):
            result = list_requests(connection, q, ALL_DATA_SCOPE)
            batches = list(purchase_batches(connection, q, ALL_DATA_SCOPE))
        self.assertEqual(result['total'], 3)
        self.assertEqual([r['id'] for r in result['items']], [6, 5])
        self.assertEqual({r['id'] for b in batches for r in b}, {4, 5, 6})
        db.close()

    def test_stock_filters_after_balance_before_page_and_export(self):
        from app.services.stock_detail_engine import export_rows, quantity_summary
        key = InventoryKey(1, 11, 20, 1, '', 0, 10)
        rows = [dict(row_id=str(i), inventory_key=key, bill_date=date(2026, 6, i),
                     source_order=0, created_at=datetime(2026, 6, i), bill_no='B'+str(i),
                     bill_seq=i, income_qty=D(income), issue_qty=D(issue))
                for i, income, issue in ((1, 10, 0), (2, 0, 3), (3, 2, 0))]
        dataset = dict(rows=rows, openings={key: D(5)}, labels={})
        q = stock_query(filters=filters('balance_qty', 'lessThan', '15'), page_size=1)
        result = assemble_page(q, rows, dataset['openings'], opening_date=q.start_date)
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['items'][0]['bill_no'], 'B2')
        self.assertEqual(result['items'][0]['balance_qty'], D(12))
        self.assertEqual(result['openings'][0]['opening_qty'], D(5))
        self.assertEqual(result['filter_semantics']['openings'], 'full_scope')
        exported = list(export_rows(dataset, q.start_date, conditions=q.conditions()))
        self.assertEqual([r['bill_no'] for r in exported], [None, 'B2', 'B3'])
        self.assertEqual([r['balance_qty'] for r in exported], [D(5), D(12), D(14)])
        self.assertEqual(quantity_summary(dataset)['income_qty'], D(12))
        self.assertEqual(quantity_summary(dataset)['balance_qty'], D(14))

    def test_all_operators_null_dates_and_literal_text(self):
        from app.services.report_filters import matches_filters, sql_conditions
        cases = [('bill_no', 'contains', 'B', None, 'AB_', True),
                 ('bill_no', 'contains', '%', None, 'AB_', False),
                 ('bill_no', 'notContains', '%', None, 'AB_', True),
                 ('bill_no', 'startsWith', 'A', None, 'AB_', True),
                 ('bill_no', 'endsWith', '_', None, 'AB_', True),
                 ('bill_no', 'equals', 'AB_', None, 'AB_', True),
                 ('bill_no', 'notEquals', 'X', None, None, False),
                 ('bill_no', 'isEmpty', None, None, '', True),
                 ('bill_no', 'notEmpty', None, None, None, False),
                 ('balance_qty', 'isEmpty', None, None, D(0), False),
                 ('balance_qty', 'notEmpty', None, None, D(0), True),
                 ('balance_qty', 'greaterThan', '2', None, D('2.01'), True),
                 ('balance_qty', 'greaterOrEqual', '2', None, D(2), True),
                 ('balance_qty', 'lessThan', '2', None, D(2), False),
                 ('balance_qty', 'lessOrEqual', '2', None, D(2), True),
                 ('balance_qty', 'between', '1.125', '2.25', D('2.25'), True),
                 ('bill_date', 'equals', '2026-06-01', None, datetime(2026, 6, 1, 23, 59), True),
                 ('bill_date', 'between', '2026-06-01', '2026-06-02', date(2026, 6, 2), True)]
        for field, op, value, end, actual, expected in cases:
            with self.subTest(field=field, op=op):
                conditions = stock_query(filters=filters(field, op, value, valueEnd=end)).conditions()
                self.assertEqual(matches_filters({field: actual}, conditions), expected)
                sql, params = sql_conditions(conditions)
                self.assertEqual(sql.count('%s'), len(params))
        conditions = stock_query(filters=json.dumps([
            dict(field='bill_no', operator='contains', value='B'),
            dict(field='balance_qty', operator='greaterThan', value='5')])).conditions()
        self.assertFalse(matches_filters({'bill_no': 'B', 'balance_qty': D(4)}, conditions))

    def test_stock_workbook_entrypoint_keeps_openings_and_filtered_balances(self):
        from app.services.report_export_data import write_report
        key = InventoryKey(1, 11, 20, 1, '', 0, 10)
        rows = [dict(row_id=str(i), inventory_key=key, bill_date=date(2026, 6, i),
                     source_order=0, created_at=datetime(2026, 6, i), bill_no='B'+str(i),
                     bill_seq=i, income_qty=D(2), issue_qty=D(0)) for i in (1, 2)]
        q = stock_query(filters=filters('bill_no', 'equals', 'B2'))
        job = SimpleNamespace(report='stock-detail', parameters=q.model_dump_json(),
                              columns='["bill_no","balance_qty"]')
        with tempfile.TemporaryDirectory() as folder, \
             patch('app.api.inventory_reports.authorized_organizations', return_value=[1]), \
             patch('app.services.report_export_data.purchase_connection'), \
             patch('app.services.stock_detail_fetch.read_dataset', return_value=dict(rows=rows, openings={key: D(5)}, labels={})), \
             patch('app.services.report_export_data.ReportWorkbook') as book:
            sheet = book.return_value.__enter__.return_value.sheet.return_value
            write_report(None, job, {}, Path(folder) / 'test.xlsx', lambda count: None)
            exported = [call.args[0] for call in sheet.append.call_args_list]
        self.assertEqual([r['bill_no'] for r in exported], [None, 'B2'])
        self.assertEqual([r['balance_qty'] for r in exported], [D(5), D(9)])
        none = stock_query(filters=filters('bill_no', 'equals', 'absent'))
        result = assemble_page(none, rows, {key: D(5)}, opening_date=none.start_date)
        self.assertEqual(result['total'], 0)
        self.assertEqual(len(result['openings']), 1)

    def test_http_rejects_bad_filters_before_opening_erp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api import purchase_reports, stock_detail_reports
        from app.core.database import get_db
        from app.services.authorization import get_current_user_context
        app = FastAPI()
        app.include_router(purchase_reports.router)
        app.include_router(stock_detail_reports.router)
        app.dependency_overrides[get_db] = lambda: None
        app.dependency_overrides[get_current_user_context] = lambda: {'permissions': [
            'report:purchase:view', 'report:stock-detail:list', 'report:stock-detail:view']}
        with TestClient(app, raise_server_exceptions=False) as client, \
             patch.object(purchase_reports, 'purchase_connection') as purchase_connection, \
             patch.object(stock_detail_reports, 'purchase_connection') as stock_connection:
            for path, params in (('purchase', {}), ('stock-detail', dict(material='M',
                    organization_ids=[1], start_date='2026-06-01', end_date='2026-06-30'))):
                for raw in (filters('bill_no', 'greaterThan', 'x'), filters('bill_no', 'equals', []), '{}'):
                    response = client.get('/api/reports/' + path, params={**params, 'filters': raw})
                    self.assertEqual(response.status_code, 422, response.text)
            purchase_connection.assert_not_called()
            stock_connection.assert_not_called()


if __name__ == '__main__':
    unittest.main()
