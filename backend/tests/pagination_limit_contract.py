"""Offline pagination boundaries through real routers, schemas and readers."""
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import system_list_query_contract as system_fixture
import report_query_v2_contract as report_fixture
from app.api import field_catalog, inventory_reports, stock_detail_reports, purchase_reports, projects, product_lines, users
from app.models.erp_task import ErpSyncTask
from app.models.product_line import SysProductLine
from app.models.project import PmsProjectArchive
from app.services import field_catalog as catalog, inventory_reader, stock_detail_reader
from app.services import oa_user_options
from app.services.purchase_reader import PurchaseQuery, PurchaseOverviewQuery
from app.services.stock_detail_balance import InventoryKey
from pydantic import ValidationError


class PaginationLimitContract(unittest.TestCase):
    def setUp(self):
        self.fixture = system_fixture.SystemListQueryContract()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.client, self.db, self.ctx = self.fixture.client, self.fixture.db, self.fixture.ctx
        for api in (field_catalog, inventory_reports, stock_detail_reports, purchase_reports, projects, product_lines, users):
            self.fixture.app.include_router(api.router)
        self.ctx['permissions'] += ['system:dict:view', 'report:inventory:view', 'report:purchase:view',
            'report:stock-detail:list', 'report:stock-detail:view', 'project:list:view',
            'project:archive:view', 'system:product-line:view', 'system:user:view']

    def test_field_catalog_api_and_service_do_not_truncate_500(self):
        rows = [dict(field_code=f'f{i}', field_name=f'Field {i}', description='', module='test',
                     module_name='Test', value_type='text', source_type='system', enum_code=None) for i in range(501)]
        with patch.object(catalog, 'build_field_catalog', return_value=rows):
            for page, count in [(1, 500), (2, 1)]:
                with self.subTest(page=page):
                    response = self.client.get('/api/field-catalog', params={'page_size': 500, 'page': page})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()['page_size'], 500)
                    self.assertEqual(response.json()['total'], 501)
                    self.assertEqual(response.json()['items'], rows[(page - 1) * 500:page * 500])
                    self.assertEqual(len(response.json()['items']), count)
        self.assertEqual(self.client.get('/api/field-catalog', params={'page_size': 501}).status_code, 422)
        self.assertEqual(catalog.query_field_catalog(fields=rows, page_size=500)['items'], rows[:500])

    def test_sync_main_and_archive_lists_page_500_real_rows(self):
        archive_id = self.fixture.visible.id
        self.db.add_all([ErpSyncTask(archive_id=archive_id, project_code=f'B{i}', project_name='Bulk',
            status='queued', attempts=0) for i in range(501)])
        self.db.commit()
        for path in ('/api/sync-tasks', f'/api/sync-tasks/archive/{archive_id}'):
            with self.subTest(path=path):
                first = self.client.get(path, params={'page_size': 500})
                second = self.client.get(path, params={'page_size': 500, 'page': 2})
                self.assertEqual(first.status_code, 200, first.text)
                self.assertEqual(second.status_code, 200, second.text)
                self.assertEqual(first.json()['total'], 505)
                self.assertEqual(len(first.json()['items']), 500)
                self.assertEqual(len(second.json()['items']), 5)
                self.assertFalse({r['id'] for r in first.json()['items']} & {r['id'] for r in second.json()['items']})
                self.assertEqual(self.client.get(path, params={'page_size': 501}).status_code, 422)

    def test_real_report_schemas_accept_500_reject_501(self):
        for model, args in [(PurchaseQuery, {}), (PurchaseOverviewQuery, {}), (inventory_reader.InventoryQuery, {}),
                (stock_detail_reader.StockDetailQuery, dict(material='M', organization_ids=[1], start_date='2026-06-01', end_date='2026-06-30'))]:
            with self.subTest(model=model.__name__):
                self.assertEqual(model(**args, page_size=500).page_size, 500)
                for page_size in (0, 501):
                    with self.assertRaises(ValidationError):
                        model(**args, page_size=page_size)

    def test_report_http_boundaries_and_existing_larger_caps(self):
        self.ctx['product_line_ids'] = []
        @contextmanager
        def connection():
            source = report_fixture.ReportV2()
            source.setUp()
            try:
                yield source.connection
            finally:
                source.doCleanups()
        patched = patch.object(purchase_reports, 'purchase_connection', connection)
        patched.start()
        self.addCleanup(patched.stop)
        stock = dict(material='M', organization_ids=1, start_date='2026-06-01', end_date='2026-06-30')
        bounded = [('/api/reports/purchase', {}), ('/api/reports/purchase/overview', {}),
                   ('/api/reports/inventory', {}), ('/api/reports/stock-detail', stock), ('/api/product-lines', {})]
        for path, params in bounded:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, params={**params, 'page_size': 500}).status_code, 200)
                self.assertEqual(self.client.get(path, params={**params, 'page_size': 501}).status_code, 422)
        for path in ('/api/projects', '/api/projects/archives/list', '/api/users', '/api/operation-logs'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, params={'page_size': 500}).status_code, 200)
                self.assertEqual(self.client.get(path, params={'page_size': 501}).status_code, 200)

    def test_permission_and_candidate_caps_remain_independent(self):
        candidates = [('/api/sync-tasks/column-values', {'field': 'status'}, 101),
            ('/api/operation-logs/column-values', {'field': 'status'}, 101),
            ('/api/reports/inventory/column-options', {'field': 'Stock'}, 201),
            ('/api/reports/purchase/column-options', {'field': 'bill_no'}, 201),
            ('/api/reports/purchase/overview/column-options', {'field': 'project_code'}, 201),
            ('/api/reports/stock-detail/column-options', {'field': 'bill_no'}, 201)]
        for path, params, size in candidates:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, params={**params, 'page_size': size}).status_code, 422)
        self.ctx['permissions'] = []
        for path in ('/api/field-catalog', '/api/sync-tasks', f'/api/sync-tasks/archive/{self.fixture.visible.id}'):
            self.assertEqual(self.client.get(path, params={'page_size': 500}).status_code, 403)

    def test_project_reference_and_archive_reference_page_500_scoped_rows(self):
        self.db.add(SysProductLine(id=1, source_key='kingdee', organization_id=100,
            organization_code='100', organization_name='Test', display_name='Test', name_key='test'))
        self.db.add_all([PmsProjectArchive(project_code=f'REF-{i:04}', project_name=f'Reference {i}',
            manager_id=self.fixture.user.id, business_product_line_id=1, is_enabled=1) for i in range(501)])
        self.fixture.other_line.project_code = 'REF-HIDDEN-LINE'
        self.fixture.other_person.project_code = 'REF-HIDDEN-PERSON'
        self.db.commit()
        requests = [('/api/reports/purchase/reference-options', {'field': field})
                    for field in ('project_code', 'project_name')]
        requests.append(('/api/projects/archives/list', {'enabled': 'all'}))
        for path, params in requests:
            with self.subTest(path=path, params=params):
                base = {**params, 'keyword': 'REF-', 'page_size': 500}
                first = self.client.get(path, params=base)
                second = self.client.get(path, params={**base, 'page': 2})
                self.assertEqual(first.status_code, 200, first.text)
                self.assertEqual(second.status_code, 200, second.text)
                self.assertEqual(first.json()['total'], 501)
                self.assertEqual(len(first.json()['items']), 500)
                self.assertEqual(len(second.json()['items']), 1)
                self.assertFalse({r['id'] for r in first.json()['items']} & {r['id'] for r in second.json()['items']})
                if path.endswith('reference-options'):
                    self.assertTrue(first.json()['has_more'])
                    self.assertFalse(second.json()['has_more'])
                    self.assertEqual(self.client.get(path, params={**base, 'page_size': 501}).status_code, 422)
        self.ctx['product_line_ids'] = []
        response = self.client.get(requests[0][0], params={'field': 'project_code', 'page_size': 500})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['items'], [])
        self.ctx['permissions'] = []
        self.assertEqual(self.client.get(requests[0][0], params={'field': 'project_code', 'page_size': 500}).status_code, 403)

    def test_stock_and_material_reference_api_and_service_500_not_200(self):
        self.db.add(SysProductLine(id=1, source_key='kingdee', organization_id=100,
            organization_code='100', organization_name='Test', display_name='Test', name_key='test'))
        self.db.commit()
        source = sqlite3.connect(':memory:', check_same_thread=False)
        source.row_factory = sqlite3.Row
        self.addCleanup(source.close)
        for table, identity in [('T_BD_STOCK', 'FSTOCKID'), ('T_BD_MATERIAL', 'FMATERIALID')]:
            source.execute(f'CREATE TABLE {table} ({identity}, FUSEORGID, FNUMBER)')
            source.execute(f'CREATE TABLE {table}_L ({identity}, FLOCALEID, FNAME)')
            source.executemany(f'INSERT INTO {table} VALUES (?,?,?)',
                [(i + 1, 100, f'{i:04}') for i in range(501)] + [(999, 200, 'HIDDEN')])
            source.executemany(f'INSERT INTO {table}_L VALUES (?,?,?)',
                [(i + 1, 2052, f'Reference {i}') for i in range(501)] + [(999, 2052, 'Secret')])
        @contextmanager
        def connection():
            yield report_fixture.Connection(source)
        with patch.object(stock_detail_reports, 'purchase_connection', connection):
            for kind in ('stock', 'material'):
                with self.subTest(kind=kind, layer='service'):
                    cursor = report_fixture.Connection(source).cursor()
                    try:
                        try:
                            result = stock_detail_reader.list_reference_candidates(cursor, kind, '', [100], page_size=500)
                        except HTTPException as error:
                            self.fail(f'Reference service must accept 500: {error.status_code} {error.detail}')
                        self.assertEqual(len(result['items']), 500)
                        with self.assertRaises(HTTPException) as error:
                            stock_detail_reader.list_reference_candidates(cursor, kind, '', [100], page_size=501)
                        self.assertEqual(error.exception.status_code, 422)
                    finally:
                        cursor.close()
                with self.subTest(kind=kind):
                    base = {'field': kind, 'page': 1, 'page_size': 500, 'organization_ids': 100}
                    first = self.client.get('/api/reports/stock-detail/options', params=base)
                    second = self.client.get('/api/reports/stock-detail/options', params={**base, 'page': 2})
                    self.assertEqual(first.status_code, 200, first.text)
                    self.assertEqual(second.status_code, 200, second.text)
                    self.assertEqual(first.json()['total'], 501)
                    self.assertEqual(len(first.json()['items']), 500)
                    self.assertEqual(len(second.json()['items']), 1)
                    self.assertTrue(first.json()['has_more'])
                    self.assertFalse(second.json()['has_more'])
                    self.assertEqual(self.client.get('/api/reports/stock-detail/options',
                        params={**base, 'page_size': 501}).status_code, 422)
            self.ctx['product_line_ids'] = []
            response = self.client.get('/api/reports/stock-detail/options',
                params={'field': 'stock', 'page': 1, 'page_size': 500})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['items'], [])
            self.ctx['permissions'] = []
            self.assertEqual(self.client.get('/api/reports/stock-detail/options',
                params={'field': 'stock', 'page': 1, 'page_size': 500}).status_code, 403)

    def test_oa_picker_api_accepts_500_and_reader_binds_full_page_size(self):
        self.ctx['permissions'].append('system:user:add')
        rows = [dict(username=f'EMP-{i:04}', real_name=f'Employee {i}') for i in range(501)]
        calls = []
        def execute(sql, params):
            calls.append((str(sql), params))
            if 'SELECT COUNT(*)' in str(sql):
                return SimpleNamespace(scalar_one=lambda: len(rows))
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows[params['offset']:params['offset'] + params['limit']]))
        with patch.object(self.db, 'get_bind', return_value=SimpleNamespace(dialect=SimpleNamespace(name='mssql'))), \
             patch.object(self.db, 'execute', side_effect=execute):
            for page, count in [(1, 500), (2, 1)]:
                response = self.client.get('/api/users/oa-options', params={'page': page, 'page_size': 500})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['total'], 501)
                self.assertEqual(len(response.json()['items']), count)
            self.assertEqual(self.client.get('/api/users/oa-options', params={'page_size': 501}).status_code, 422)
            self.assertEqual(len(oa_user_options.get_oa_options(self.db, '', 1, 500)['items']), 500)
        page_calls = [(sql, params) for sql, params in calls if 'FETCH NEXT' in sql]
        self.assertEqual([p['limit'] for _, p in page_calls], [500, 500, 500])
        self.assertEqual([p['offset'] for _, p in page_calls], [0, 500, 0])
        self.assertTrue(all('FETCH NEXT :limit ROWS ONLY' in sql for sql, _ in page_calls))
        self.ctx['permissions'] = []
        self.assertEqual(self.client.get('/api/users/oa-options', params={'page_size': 500}).status_code, 403)

    def test_inventory_reader_500_rows_and_second_page_with_real_sql(self):
        source = sqlite3.connect(':memory:')
        self.addCleanup(source.close)
        source.row_factory = sqlite3.Row
        source.execute("ATTACH ':memory:' AS dbo")
        keys = inventory_reader.KEYS
        source.execute('CREATE TABLE dbo.YD_JIN_INVENTORY (' + ','.join(keys) + ')')
        source.execute('CREATE TABLE dbo.T_STK_INVENTORY (FID, FSTOCKORGID)')
        source.executemany('INSERT INTO dbo.YD_JIN_INVENTORY VALUES (' + ','.join('?' for _ in keys) + ')',
            [[i if key == 'FID' else 1 if key == 'FBaseQty' else 'M' for key in keys] for i in range(501)])
        source.executemany('INSERT INTO dbo.T_STK_INVENTORY VALUES (?,?)', [(i, 1) for i in range(501)])
        source.create_function('CONCAT', -1, lambda *args: ''.join(str(v) for v in args if v is not None))

        class Cursor:
            def execute(self, sql, params):
                sql = sql.replace('COUNT_BIG(*)', 'COUNT(*)').replace("N'", "'").replace('%s', '?')
                if ' OFFSET ? ROWS FETCH NEXT ? ROWS ONLY' in sql:
                    sql = sql.replace(' OFFSET ? ROWS FETCH NEXT ? ROWS ONLY', ' LIMIT ? OFFSET ?')
                    params = (*params[:-2], params[-1], params[-2])
                self.cursor = source.execute(sql, params)
            def fetchone(self): return dict(self.cursor.fetchone())
            def fetchall(self): return [dict(row) for row in self.cursor.fetchall()]
            def close(self): self.cursor.close()

        class Connection:
            def cursor(self): return Cursor()

        first = inventory_reader.list_inventory(Connection(), inventory_reader.InventoryQuery(page_size=500), [1])
        second = inventory_reader.list_inventory(Connection(), inventory_reader.InventoryQuery(page_size=500, page=2), [1])
        self.assertEqual(first['total'], 501)
        self.assertEqual([row['FID'] for row in first['items']], list(range(500)))
        self.assertEqual([row['FID'] for row in second['items']], [500])

    def test_stock_assembly_preserves_500_rows_and_full_running_balance(self):
        query = stock_detail_reader.StockDetailQuery(material='M', organization_ids=[1],
            start_date='2026-06-01', end_date='2026-06-30', page_size=500)
        key = InventoryKey(1, 1, 1, 1, 'owner', 1, 1)
        rows = [dict(row_id=f'{i:04}', inventory_key=key, bill_date=date(2026, 6, 1),
            source_order=0, created_at=datetime(2026, 6, 1), bill_no=f'{i:04}', bill_seq=1,
            income_qty=Decimal(1), issue_qty=Decimal(0)) for i in range(501)]
        first = stock_detail_reader.assemble_page(query, rows, {key: Decimal(0)}, opening_date=query.start_date)
        second = stock_detail_reader.assemble_page(query.model_copy(update={'page': 2}), rows,
            {key: Decimal(0)}, opening_date=query.start_date)
        self.assertEqual(first['total'], 501)
        self.assertEqual(len(first['items']), 500)
        self.assertEqual(first['items'][-1]['balance_qty'], Decimal(500))
        self.assertEqual(len(second['items']), 1)
        self.assertEqual(second['items'][0]['balance_qty'], Decimal(501))


if __name__ == '__main__':
    unittest.main(verbosity=2)
