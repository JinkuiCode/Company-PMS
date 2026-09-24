from datetime import date, datetime
from decimal import Decimal as D
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from app.services import report_export_jobs
from app.services.stock_detail_balance import InventoryKey


class ExportContract(unittest.TestCase):
    def test_export_without_organization_is_rejected_before_database_access(self):
        ctx = {'permissions': ['report:stock-detail:list', 'report:stock-detail:view', 'report:stock-detail:export']}
        with self.assertRaises(HTTPException) as result:
            report_export_jobs.create_job(None, ctx, 'stock-detail',
                {'material': 'M1', 'start_date': '2026-06-01', 'end_date': '2026-06-30'}, ['material_code'])
        self.assertEqual(result.exception.status_code, 422)
    def test_export_rechecks_multi_organization_scope(self):
        from app.services.report_export_data import write_report
        job = SimpleNamespace(report='stock-detail', parameters='{"material":"M1","start_date":"2026-06-01","end_date":"2026-06-30","organization_ids":[1,2,99]}', columns='["material_code"]')
        with tempfile.TemporaryDirectory() as folder, \
             patch('app.api.inventory_reports.authorized_organizations', return_value=[2]), \
             patch('app.services.report_export_data.purchase_connection'), \
             patch('app.services.stock_detail_fetch.read_dataset', return_value=dict(rows=[], openings={}, labels={})) as read:
            write_report(None, job, {}, Path(folder) / 'scoped.xlsx', lambda count: None)
            self.assertEqual(read.call_args.args[2], [2])

    def test_empty_export_scope_does_not_connect_to_erp(self):
        from app.services.report_export_data import write_report
        job = SimpleNamespace(report='stock-detail', parameters='{"material":"M1","start_date":"2026-06-01","end_date":"2026-06-30","organization_ids":[1]}', columns='["material_code"]')
        with tempfile.TemporaryDirectory() as folder, patch('app.api.inventory_reports.authorized_organizations', return_value=[]), patch('app.services.report_export_data.purchase_connection') as connection:
            write_report(None, job, {}, Path(folder) / 'empty.xlsx', lambda count: None)
            connection.assert_not_called()
    def test_export_requires_list_and_separate_export_permission(self):
        report_export_jobs.check_permission({'permissions': ['report:stock-detail:list', 'report:stock-detail:view', 'report:stock-detail:export']}, 'stock-detail')
        for permissions in ([], ['report:stock-detail:list'], ['report:stock-detail:export'], ['report:stock-detail:list', 'report:stock-detail:export']):
            with self.assertRaises(HTTPException):
                report_export_jobs.check_permission({'permissions': permissions}, 'stock-detail')

    def test_export_fields_exclude_financial_information(self):
        fields = report_export_jobs.fields_for('stock-detail')
        self.assertEqual(len(fields), 15)
        self.assertIn('balance_qty', [field['key'] for field in fields])
        self.assertFalse(any('price' in field['key'] or 'amount' in field['key'] for field in fields))

    def test_export_keeps_all_rows_beyond_ten_thousand(self):
        from app.services.stock_detail_engine import export_rows
        key = InventoryKey(1, 11, 20, 1, '', 0, 10)
        rows = [dict(row_id=str(i), inventory_key=key, bill_date=date(2026, 6, 1), source_order=0,
                     created_at=datetime(2026, 6, 1), bill_no='B', bill_seq=i,
                     income_qty=D(1), issue_qty=D(0), price=D(999)) for i in range(10001)]
        result = list(export_rows(dict(rows=rows, openings={key: D(5)}, labels={}), date(2026, 6, 1)))
        self.assertEqual(len(result), 10002)
        self.assertEqual(result[0]['opening_qty'], D(5))
        self.assertEqual(result[-1]['balance_qty'], D(10006))
        self.assertNotIn('price', result[-1])


if __name__ == '__main__':
    unittest.main()
