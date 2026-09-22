import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from unittest.mock import patch
from contextlib import contextmanager
from threading import Event
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class WorkbookTests(unittest.TestCase):
    def test_purchase_export_indexes_snapshot_and_filters_after_summary(self):
        from app.services.report_export_data import purchase_batches, matches_progress
        from app.services.purchase_reader import PurchaseQuery
        class Cursor:
            calls = []
            def execute(self, sql, params=()): self.calls.append(sql)
            def close(self): pass
        class Connection:
            def cursor(self): return cursor
        cursor = Cursor()
        with patch('app.services.purchase_reader._prepare_scope'), \
                patch('app.services.purchase_reader.request_query', return_value=('SELECT 1 AS id', [])), \
                patch('app.services.purchase_reader._rows', return_value=[]):
            list(purchase_batches(Connection(), PurchaseQuery(progress='complete'), []))
        self.assertTrue(any('CREATE UNIQUE CLUSTERED INDEX' in sql for sql in cursor.calls))
        self.assertFalse(matches_progress(PurchaseQuery(progress='not_ordered'), {'progress': 'complete'}))
        self.assertTrue(matches_progress(PurchaseQuery(progress='complete'), {'progress': 'complete'}))

    def test_purchase_detail_workbook_has_parent_links(self):
        from app.services.report_export_data import append_purchase
        from app.services.report_workbook import ReportWorkbook
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'purchase.xlsx'
            with ReportWorkbook(path) as book:
                from app.services.report_export_data import detail_sheets
                orders, receipts = detail_sheets(book)
                main = book.sheet('采购申请主表', [('bill_no', '申请单编号')])
                append_purchase(main, orders, receipts, {'bill_no': 'REQ1', 'line_no': 2}, {
                    'orders': [{'id': 7, 'bill_no': 'PO1', 'line_no': 3, 'supplier_name': '供应商甲'}],
                    'receipts': [{'bill_no': 'IN1', 'line_no': 1, 'order_id': 7}], 'summary': {}})
            with zipfile.ZipFile(path) as archive:
                xml = ''.join(archive.read(n).decode() for n in archive.namelist() if n.startswith('xl/worksheets/sheet'))
                self.assertEqual(xml.count('REQ1'), 3)
                self.assertEqual(xml.count('PO1'), 2)
                self.assertIn('IN1', xml)

    def test_streaming_splits_without_truncation_and_writes_literals(self):
        from app.services.report_workbook import ReportWorkbook
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'report.xlsx'
            with ReportWorkbook(path, row_limit=3) as book:
                sheet = book.sheet('采购申请主表', [('code', '编码'), ('qty', '数量')])
                for i in range(5):
                    sheet.append({'code': '=1+1' if i == 0 else f'00{i}', 'qty': i})
            with zipfile.ZipFile(path) as archive:
                names = [n for n in archive.namelist() if n.startswith('xl/worksheets/sheet')]
                self.assertEqual(len(names), 3)
                ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                roots = [ET.fromstring(archive.read(n)) for n in names]
                self.assertEqual(sum(len(r.findall('.//x:row', ns))-1 for r in roots), 5)
                self.assertFalse(any(r.findall('.//x:f', ns) for r in roots))
                self.assertIn('=1+1', archive.read(names[0]).decode())

    def test_inventory_id_not_exposed_or_filterable(self):
        from app.services.inventory_fields import report_fields
        from app.services.inventory_reader import Condition
        self.assertNotIn('FID', [f['key'] for f in report_fields()])
        with self.assertRaises(ValueError):
            Condition(field='FID', operator='equals', value='secret')


class JobTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.core.database import Base
        import app.models.init_db
        from app.models.report_export import ReportExportJob
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.ctx = {'user_id': 7, 'permissions': ['report:inventory:view', 'report:inventory:export']}

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_job_validates_columns_and_independent_permissions(self):
        from fastapi import HTTPException
        from app.services.report_export_jobs import create_job, get_job
        with patch('app.services.report_export_jobs.scope_signature', return_value='scope'):
            with self.assertRaises(HTTPException):
                create_job(self.db, {'user_id': 7, 'permissions': ['report:inventory:view']}, 'inventory', {}, ['Stock'])
            with self.assertRaises(HTTPException):
                create_job(self.db, self.ctx, 'inventory', {}, ['FID'])
            job = create_job(self.db, self.ctx, 'inventory', {}, ['Stock', 'MaterialCode'])
            self.assertEqual(job.status, 'queued')
            self.assertEqual(get_job(self.db, self.ctx, job.id).id, job.id)
            with self.assertRaises(HTTPException):
                get_job(self.db, dict(self.ctx, user_id=8), job.id)
            with self.assertRaises(HTTPException):
                create_job(self.db, self.ctx, 'inventory', {}, ['Stock'])

    def test_scope_change_blocks_download(self):
        from fastapi import HTTPException
        from app.services.report_export_jobs import create_job, get_job
        with patch('app.services.report_export_jobs.scope_signature', return_value='old'):
            job = create_job(self.db, self.ctx, 'inventory', {}, ['Stock'])
        with patch('app.services.report_export_jobs.scope_signature', return_value='new'):
            with self.assertRaises(HTTPException) as error:
                get_job(self.db, self.ctx, job.id, download=True)
            self.assertEqual(error.exception.status_code, 403)

    def test_api_create_and_poll_own_job(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.report_exports import router
        from app.core.database import get_db
        from app.services.authorization import get_current_user_context
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user_context] = lambda: self.ctx
        # Direct endpoint tests avoid sharing the test's single SQLite connection across threads.
        from app.api.report_exports import ExportRequest, create, status
        with patch('app.services.report_export_jobs.scope_signature', return_value='scope'):
            result = create(ExportRequest(report='inventory', parameters={}, columns=['Stock']), None, self.db, self.ctx)
            self.assertEqual(status(result['id'], self.db, self.ctx)['status'], 'queued')

    def test_worker_exports_more_than_ten_thousand_rows_and_cleans_expired_file(self):
        from app.services import report_export_jobs as jobs
        @contextmanager
        def connection():
            yield object()
        def batches(*args):
            for start in range(0, 10001, 500):
                yield [{'Stock': f'仓库{i}'} for i in range(start, min(start+500, 10001))]
        with tempfile.TemporaryDirectory() as folder, patch.object(jobs, 'EXPORT_ROOT', Path(folder)), \
                patch.object(jobs, 'scope_signature', return_value='scope'), \
                patch.object(jobs, 'build_authorization_context', return_value=self.ctx), \
                patch('app.services.report_export_data.purchase_connection', connection), \
                patch('app.services.report_export_data.inventory_batches', batches):
            job = jobs.create_job(self.db, self.ctx, 'inventory', {}, ['Stock'])
            jobs.run_next(self.db, Event())
            self.assertEqual(job.status, 'success', job.message)
            self.assertEqual(job.processed, 10001)
            with zipfile.ZipFile(jobs.job_file(job)) as archive:
                self.assertEqual(archive.read('xl/worksheets/sheet1.xml').count(b'<row '), 10002)
            job.finished_at = datetime.now()-timedelta(hours=25)
            self.db.commit()
            jobs.run_next(self.db, Event())
            self.assertEqual(job.status, 'expired')
            self.assertFalse(jobs.job_file(job).exists())

    def test_revocation_mid_export_deletes_partial_file(self):
        from app.services import report_export_jobs as jobs
        from app.services.report_workbook import ReportWorkbook
        def write(db, job, ctx, path, checkpoint):
            with ReportWorkbook(path) as book:
                book.sheet('库存', [('Stock', '仓库')]).append({'Stock': 'secret'})
            self.ctx['permissions'] = ['report:inventory:view']
            checkpoint(1)
        with tempfile.TemporaryDirectory() as folder, patch.object(jobs, 'EXPORT_ROOT', Path(folder)), \
                patch.object(jobs, 'scope_signature', return_value='scope'), \
                patch.object(jobs, 'build_authorization_context', return_value=self.ctx), \
                patch('app.services.report_export_data.write_report', write):
            job = jobs.create_job(self.db, self.ctx, 'inventory', {}, ['Stock'])
            jobs.run_next(self.db, Event())
            self.assertEqual(job.status, 'failed')
            self.assertFalse(jobs.job_file(job).exists())

    def test_restart_marks_incomplete_job_failed(self):
        from app.services import report_export_jobs as jobs
        with tempfile.TemporaryDirectory() as folder, patch.object(jobs, 'EXPORT_ROOT', Path(folder)), \
                patch.object(jobs, 'scope_signature', return_value='scope'):
            job = jobs.create_job(self.db, self.ctx, 'inventory', {}, ['Stock'])
            job.status = 'running'; self.db.commit()
            jobs.job_file(job).write_bytes(b'partial')
            jobs.run_next(self.db, Event())
            self.assertEqual(job.status, 'failed')
            self.assertFalse(jobs.job_file(job).exists())


if __name__ == '__main__':
    unittest.main()
