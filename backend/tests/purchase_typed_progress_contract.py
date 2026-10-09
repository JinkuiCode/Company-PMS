"""Execute real accounting/filter SQL on the offline relational ERP fixture."""
from datetime import date
from contextlib import nullcontext
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import purchase_reader_contract as fixture
from app.services import purchase_reader as reader
from app.services.report_export_data import purchase_batches


class ExportCursor(fixture.SqliteCursor):
    def execute(self, sql, params=()):
        # Adapt only SQL Server syntax; accounting and filter predicates are real.
        sql = re.sub(r'CAST\((filter_source\.\[\w+\]) AS date\)', r'date(\1)', sql)
        match = re.fullmatch(r'WITH q AS \((.*)\) (SELECT .*?) INTO (#pms_export_selected) FROM q', sql, re.S)
        if match:
            sql = f'CREATE TEMP TABLE {match[3]} AS WITH q AS ({match[1]}) {match[2]} FROM q'
        sql = sql.replace('CREATE UNIQUE CLUSTERED INDEX', 'CREATE UNIQUE INDEX')
        super().execute(sql, [float(p) if isinstance(p, Decimal) else p for p in params])


class Connection(fixture.FixtureConnection):
    def cursor(self):
        return ExportCursor(self.db)


class ProgressFilters(unittest.TestCase):
    def setUp(self):
        self.source = fixture.ReaderContract()
        self.addCleanup(self.source.doCleanups)
        self.db, _ = self.source.classification_fixture()
        self.connection = Connection(self.db)

    def test_progress_additional_and_legacy_count_page_export_parity(self):
        cases = [('', 'equals', 'complete', {4}),
                 ('', 'notEquals', 'review', {1, 2, 3, 4, 7, 9}),
                 ('receiving', 'equals', 'receiving', {3, 9}),
                 ('receiving', 'notEquals', 'review', {3, 9}),
                 ('receiving', 'equals', 'complete', set()),
                 ('review', 'notEquals', 'review', set())]
        for legacy, operator, value, expected in cases:
            with self.subTest(legacy=legacy, operator=operator, value=value):
                q = reader.PurchaseQuery(progress=legacy, page_size=1, filters=json.dumps([
                    dict(field='progress', operator=operator, value=value),
                    dict(field='requested', operator='greaterOrEqual', value='1'),
                    dict(field='approved', operator='equals', value='1')]))
                base, params = reader.request_query(q, fixture.GRANTS)
                self.assertNotIn('filter_source.[progress]', base)
                self.assertNotIn(value, params)
                ids = set()
                for page in range(1, len(expected) + 2):
                    part = reader.list_requests(self.connection, q.model_copy(update={'page': page}), fixture.GRANTS)
                    self.assertEqual(part['total'], len(expected))
                    self.assertLessEqual(len(part['items']), 1)
                    ids.update(row['id'] for row in part['items'])
                self.assertEqual(ids, expected)
                batches = list(purchase_batches(self.connection, q, fixture.GRANTS))
                self.assertEqual({row['id'] for batch in batches for row in batch}, expected)
                self.assertEqual(self.db.execute("SELECT name FROM sqlite_temp_master WHERE name LIKE 'temp_pms_purchase_%' OR name LIKE 'temp_pms_export_%'").fetchall(), [])

    def test_legacy_only_and_final_workbook_use_same_progress_membership(self):
        from app.services.report_export_data import write_report
        for legacy, conditions, expected in (
                ('review', [], {5, 6, 8}),
                ('', [dict(field='progress', operator='equals', value='ordering')], {2, 7}),
                ('receiving', [dict(field='progress', operator='notEquals', value='review')], {3, 9}),
                ('complete', [dict(field='progress', operator='notEquals', value='complete')], set())):
            with self.subTest(legacy=legacy, conditions=conditions):
                q = reader.PurchaseQuery(progress=legacy, filters=json.dumps(conditions), page_size=1)
                result = reader.list_requests(self.connection, q, fixture.GRANTS)
                self.assertEqual(result['total'], len(expected))
                job = SimpleNamespace(report='purchase', parameters=q.model_dump_json(), columns='["progress"]')
                main, orders, receipts = Mock(), Mock(), Mock()
                with tempfile.TemporaryDirectory() as folder, \
                     patch('app.services.report_export_data.purchase_connection', return_value=nullcontext(self.connection)), \
                     patch('app.api.purchase_reports.project_scope', return_value=fixture.GRANTS), \
                     patch('app.api.purchase_reports.enrich_project_names'), \
                     patch('app.api.purchase_reports.enrich_product_lines'), \
                     patch('app.services.report_export_data.ReportWorkbook') as book:
                    book.return_value.__enter__.return_value.sheet.side_effect = [main, orders, receipts]
                    write_report(None, job, {}, Path(folder) / 'test.xlsx', lambda count: None)
                self.assertEqual({call.args[0]['id'] for call in main.append.call_args_list}, expected)

    def test_requested_approved_aliases_and_calendar_dates_execute(self):
        self.db.execute("UPDATE T_PUR_REQUISITION SET FAPPLICATIONDATE='2026-06-01 23:59:59' WHERE FID=4")
        q = reader.PurchaseQuery(filters=json.dumps([
            dict(field='requested', operator='equals', value='1'),
            dict(field='approved', operator='between', value='0.5', valueEnd='1.5'),
            dict(field='application_date', operator='equals', value='2026-06-01')]))
        sql, params = reader.request_query(q, fixture.GRANTS)
        self.assertIn('e.FREQQTY AS requested', sql)
        self.assertIn('e.FAPPROVEQTY AS approved', sql)
        self.assertIn('filter_source.[requested]', sql)
        self.assertIn('filter_source.[approved]', sql)
        self.assertEqual([type(p) for p in params[-4:]], [Decimal, Decimal, Decimal, date])
        result = reader.list_requests(self.connection, q, fixture.GRANTS)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['id'], 4)
        self.assertEqual([row['id'] for b in purchase_batches(self.connection, q, fixture.GRANTS) for row in b], [4])
        for field in ('requested', 'approved', 'application_date', 'progress'):
            for value in (True, False):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    reader.PurchaseQuery(filters=json.dumps([dict(field=field, operator='equals', value=value)]))
        for value in (20260601, '2026-06-01T00:00:00', '2026-02-30'):
            with self.assertRaises(ValueError):
                reader.PurchaseQuery(filters=json.dumps([dict(field='application_date', operator='equals', value=value)]))


if __name__ == '__main__':
    unittest.main()
