"""Offline display contracts; no external databases, grants or business writes."""
from contextlib import nullcontext
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base
import app.models.init_db
from app.models.product_line import SysProductLine
from app.services.business_data_scope import ALL_DATA_SCOPE
from app.services.report_export_jobs import fields_for
from app.services.report_filters import query_fields
import report_query_v2_contract as query_fixtures
from report_query_v2_contract import Connection, V2Cursor, column_values, condition


class InventoryCursor(V2Cursor):
    def execute(self, sql, params=()):
        sql = sql.replace('COUNT_BIG(', 'COUNT(')
        if ' OFFSET %s ROWS FETCH NEXT %s ROWS ONLY' in sql:
            sql = sql.replace(' OFFSET %s ROWS FETCH NEXT %s ROWS ONLY', ' LIMIT %s OFFSET %s')
            params = [*params[:-2], params[-1], params[-2]]
        super().execute(sql, params)

    def fetchone(self):
        return dict(self.cursor.fetchone())


class InventoryConnection(Connection):
    def cursor(self):
        return InventoryCursor(self.db)


class DisplayContract(unittest.TestCase):
    def setUp(self):
        engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        Base.metadata.create_all(engine)
        self.db = Session(engine)
        self.addCleanup(engine.dispose)
        self.addCleanup(self.db.close)
        self.db.add_all([SysProductLine(id=i, source_key='kingdee', organization_id=org,
            organization_code=str(org), organization_name='Same Organization',
            display_name=name, name_key=name, is_enabled=enabled)
            for i, org, name, enabled in ((1, 100, 'Z Line', 1), (2, 200, 'A Line', 0))])
        self.db.commit()
        self.erp = sqlite3.connect(':memory:', check_same_thread=False)
        self.erp.row_factory = sqlite3.Row
        self.erp.create_function('CONCAT', -1, lambda *args: ''.join(str(v) for v in args if v is not None))
        self.erp.execute('CREATE TABLE T_ORG_ORGANIZATIONS_L(FORGID,FLOCALEID,FNAME)')
        self.erp.executemany('INSERT INTO T_ORG_ORGANIZATIONS_L VALUES(?,2052,?)',
                             [(100, 'Same Organization'), (200, 'Same Organization'), (300, 'Other Organization')])
        self.addCleanup(self.erp.close)
        self.connection = InventoryConnection(self.erp)

    def inventory(self):
        from app.services import inventory_reader as reader
        source_keys = [key for key in reader.KEYS if key != 'product_line_name']
        if 'Organization' not in source_keys:
            source_keys.append('Organization')
        self.erp.execute('CREATE TABLE YD_JIN_INVENTORY (' + ','.join(f'[{key}]' for key in source_keys) + ')')
        self.erp.execute('CREATE TABLE T_STK_INVENTORY(FID,FSTOCKORGID)')
        for org, label in ((100, 'Same Organization'), (200, 'Same Organization'), (300, 'Other Organization')):
            self.erp.execute('INSERT INTO YD_JIN_INVENTORY(FID,Organization,Stock,MaterialCode,FBaseQty) VALUES(?,?,?,?,?)',
                             (str(org), label, 'S', 'P-SAME', org))
            self.erp.execute('INSERT INTO T_STK_INVENTORY VALUES(?,?)', (str(org), org))
        return reader

    def resolve_inventory(self, query):
        from app.services import inventory_reader as reader
        self.assertTrue(hasattr(reader, 'resolve_product_lines'), 'inventory labels must resolve before SQL filtering')
        reader.resolve_product_lines(self.db, query)
        return query

    def inventory_query(self, **parameters):
        from app.services.inventory_reader import InventoryQuery
        try:
            return InventoryQuery(**parameters)
        except ValueError as error:
            self.fail(f'Product-line display query must be accepted: {error}')

    def stock_dataset(self):
        from app.services.stock_detail_balance import InventoryKey
        keys = [InventoryKey(org, 11, 20, 1, '', 0, 10) for org in (100, 200, 300)]
        rows = [dict(inventory_key=key, row_id=str(key.organization_id), bill_date=date(2026, 6, 2),
            source_order=0, created_at=datetime(2026, 6, 2), bill_no='P-SAME', bill_seq=1,
            income_qty=Decimal(2), issue_qty=Decimal(1)) for key in keys]
        return dict(rows=rows, openings={key: Decimal(10) for key in keys}, labels={})

    def test_all_public_field_sets_start_with_product_line_and_drop_project_name(self):
        for report, overview in (('purchase', False), ('purchase', True), ('inventory', False), ('stock-detail', False)):
            with self.subTest(report=report, overview=overview):
                fields = fields_for(report, overview=overview)
                self.assertEqual(fields[0]['key'], 'product_line_name')
                self.assertNotIn('project_name', [f['key'] for f in fields])
                query_report = 'purchase-overview' if overview else report
                self.assertEqual(query_fields(query_report)[0]['field'], 'product_line_name')
                self.assertNotIn('project_name', [f['field'] for f in query_fields(query_report)])
        self.assertNotIn('Organization', [f['key'] for f in fields_for('inventory')])
        self.assertNotIn('Organization', [f['field'] for f in query_fields('inventory')])

    def test_public_catalog_matches_display_not_internal_organization(self):
        from app.services.field_catalog import build_field_catalog
        catalog = build_field_catalog()
        for module in ('purchase_report', 'purchase_overview', 'inventory_report', 'stock_detail_report'):
            fields = sorted([f for f in catalog if f['module'] == module], key=lambda f: f['sort'])
            self.assertEqual(fields[0]['field_code'], 'product_line_name')
            self.assertNotIn('project_name', [f['field_code'] for f in fields])
            if module == 'inventory_report':
                self.assertNotIn('Organization', [f['field_code'] for f in fields])
        self.assertTrue(any(f['module'] == 'project_archive' and f['field_code'] == 'project_name' for f in catalog))

    def test_removed_fields_rejected_for_sort_filters_and_candidates(self):
        from app.services.inventory_reader import InventoryQuery
        from app.services.purchase_reader import PurchaseQuery, PurchaseOverviewQuery
        from app.services.report_column_candidates import candidate_query
        for model, field in ((InventoryQuery, 'Organization'), (PurchaseQuery, 'project_name'), (PurchaseOverviewQuery, 'project_name')):
            with self.assertRaises(ValueError):
                model(column_filters=column_values(field, ['name']))
        with self.assertRaises(ValueError):
            InventoryQuery(sort='Organization')
        with self.assertRaises(ValueError):
            candidate_query(PurchaseQuery(), 'purchase', 'project_name', '', 1, 50)

    def test_inventory_labels_use_ids_before_count_sort_and_paging(self):
        reader = self.inventory()
        query = self.resolve_inventory(self.inventory_query(sort='product_line_name', page_size=1))
        result = reader.list_inventory(self.connection, query, [100, 200])
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['items'][0]['product_line_name'], 'A Line')
        self.assertNotIn('Organization', result['items'][0])
        self.assertNotIn('organization_id', result['items'][0])
        self.assertEqual(reader.list_inventory(self.connection, query.model_copy(update={'page': 2}), [100, 200])['items'][0]['product_line_name'], 'Z Line')

    def test_inventory_filter_candidates_and_export_share_labels_and_scope(self):
        from app.services.report_column_candidates import inventory_candidates
        from app.services.report_export_data import inventory_batches
        reader = self.inventory()
        query = self.resolve_inventory(self.inventory_query(column_filters=column_values('product_line_name', ['A Line'])))
        listed = reader.list_inventory(self.connection, query, [100, 200])
        self.assertEqual(listed['total'], 1)
        self.assertEqual(listed['items'][0]['FID'], '200')
        exported = [r for batch in inventory_batches(self.connection, query, [100, 200]) for r in batch]
        self.assertEqual([r['FID'] for r in exported], ['200'])
        candidates = inventory_candidates(self.connection, query, [100, 200], 'product_line_name')
        self.assertEqual({r['value'] for r in candidates['items']}, {'Z Line', 'A Line'})
        self.assertEqual(inventory_candidates(self.connection, query, [100], 'product_line_name')['items'], [{'value': 'Z Line', 'label': 'Z Line'}])

    def test_unconfigured_inventory_visible_only_in_existing_all_scope(self):
        reader = self.inventory()
        query = self.resolve_inventory(self.inventory_query(filters=condition('product_line_name', 'contains', '未配置产品线')))
        self.assertEqual(reader.list_inventory(self.connection, query, [100, 200])['total'], 0)
        result = reader.list_inventory(self.connection, query, ALL_DATA_SCOPE)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['product_line_name'], 'Other Organization（未配置产品线）')
        self.assertEqual(reader.list_inventory(self.connection, query, [])['total'], 0)
        self.assertEqual(reader.effective_organizations(reader.InventoryQuery(organization_id=300), [100]), [])

    def test_stock_labels_cover_movements_openings_filters_sort_candidates_export(self):
        from app.api import stock_detail_reports as api
        from app.services.stock_detail_reader import StockDetailQuery, assemble_page
        from app.services.stock_detail_engine import export_rows
        from app.services.report_column_candidates import stock_candidates
        self.assertTrue(hasattr(api, 'enrich_stock_product_lines'), 'stock dataset labels must resolve before filtering')
        dataset = self.stock_dataset()
        api.enrich_stock_product_lines(self.db, self.connection, dataset)
        self.assertEqual([r['product_line_name'] for r in dataset['rows']], ['Z Line', 'A Line', 'Other Organization（未配置产品线）'])
        self.assertEqual([r['product_line_name'] for r in dataset['labels'].values()], ['Z Line', 'A Line', 'Other Organization（未配置产品线）'])
        query = StockDetailQuery(material='M', organization_ids=[100, 200, 300], start_date='2026-06-01',
            end_date='2026-06-30', sort='product_line_name', page_size=1,
            column_filters=column_values('product_line_name', ['A Line']))
        page = assemble_page(query, dataset['rows'], dataset['openings'], opening_date=query.start_date, opening_labels=dataset['labels'])
        self.assertEqual(page['total'], 1)
        self.assertEqual(page['items'][0]['balance_qty'], Decimal(11))
        self.assertEqual(page['items'][0]['product_line_name'], 'A Line')
        self.assertEqual([r['product_line_name'] for r in page['openings']], ['A Line'])
        exported = list(export_rows(dataset, query.start_date, conditions=query.conditions(), column_conditions=query.column_conditions(), sort=query.sort))
        self.assertEqual([r['product_line_name'] for r in exported], ['A Line', 'A Line'])
        self.assertEqual(stock_candidates(query, dataset, 'product_line_name')['total'], 3)

    def test_inventory_worker_resolves_labels_and_writes_real_workbook(self):
        from app.services.report_export_data import write_report
        reader = self.inventory()
        query = self.inventory_query(filters=condition('product_line_name', 'equals', 'A Line'))
        job = SimpleNamespace(report='inventory', parameters=query.model_dump_json(), columns='["product_line_name","FBaseQty"]')
        with tempfile.TemporaryDirectory() as directory, patch('app.services.report_export_data.purchase_connection', return_value=nullcontext(self.connection)):
            path = Path(directory) / 'report.xlsx'
            write_report(self.db, job, {'product_line_ids': [1, 2]}, path, lambda n: None)
            with zipfile.ZipFile(path) as book:
                sheet = book.read('xl/worksheets/sheet1.xml').decode()
            self.assertIn('A Line', sheet)
            self.assertNotIn('Z Line', sheet)
            self.assertNotIn('Other Organization', sheet)

    def test_purchase_product_line_sort_shared_by_list_and_export(self):
        from app.services import purchase_reader as reader
        from app.services.report_export_data import purchase_batches, overview_batches
        from app.services.purchase_query_labels import resolve_query_labels
        source = query_fixtures.ReportV2()
        source.setUp()
        self.addCleanup(source.doCleanups)
        source.db.execute('UPDATE T_PUR_REQUISITION SET FAPPLICATIONORGID=200 WHERE FID=1')
        for model, read, export in ((reader.PurchaseQuery, reader.list_requests, purchase_batches),
                                   (reader.PurchaseOverviewQuery, reader.list_overview, overview_batches)):
            with self.subTest(model=model.__name__):
                try:
                    query = model(sort='product_line_name', direction='asc', page_size=1)
                except ValueError as error:
                    self.fail(f'Product-line sorting must be accepted: {error}')
                resolve_query_labels(self.db, {}, query)
                result = read(source.connection, query, ALL_DATA_SCOPE)
                self.assertEqual(result['items'][0]['organization_id'], 200)
                exported = [r for batch in export(source.connection, query, ALL_DATA_SCOPE) for r in batch]
                self.assertEqual(exported[0]['organization_id'], 200)
                self.assertEqual(exported[-1]['organization_id'], 100)
                self.assertEqual(len(exported), result['total'])

    def test_http_inventory_mapping_and_removed_columns(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api import inventory_reports as api
        from app.core.database import get_db
        from app.services.authorization import get_current_user_context
        self.inventory()
        app = FastAPI()
        app.include_router(api.router)
        ctx = dict(user_id=1, product_line_ids=[1, 2], permissions=['report:inventory:view'])
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user_context] = lambda: ctx
        with TestClient(app) as client, patch.object(api, 'purchase_connection', return_value=nullcontext(self.connection)):
            response = client.get('/api/reports/inventory', params={'organization_id': 200, 'sort': 'product_line_name'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['items'][0]['product_line_name'], 'A Line')
            response = client.get('/api/reports/inventory/column-options', params={'field': 'product_line_name'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual({r['value'] for r in response.json()['items']}, {'A Line', 'Z Line'})
            for field in ('Organization', 'project_name'):
                self.assertEqual(client.get('/api/reports/inventory/column-options', params={'field': field}).status_code, 422)
            ctx['product_line_ids'] = []
            self.assertEqual(client.get('/api/reports/inventory').json()['total'], 0)

    def test_default_purchase_export_retains_product_line_first_on_all_sheets(self):
        from app.services.purchase_reader import PurchaseQuery
        from app.services.report_export_data import write_report
        source = query_fixtures.ReportV2()
        source.setUp()
        self.addCleanup(source.doCleanups)
        job = SimpleNamespace(report='purchase', parameters=PurchaseQuery().model_dump_json(),
                              columns='["product_line_name","project_code"]')
        with tempfile.TemporaryDirectory() as directory, \
                patch('app.services.report_export_data.purchase_connection', return_value=nullcontext(source.connection)):
            path = Path(directory) / 'purchase.xlsx'
            write_report(self.db, job, {'permissions': ['business:data:all']}, path, lambda n: None)
            with zipfile.ZipFile(path) as book:
                for i in (1, 2, 3):
                    xml = ET.fromstring(book.read(f'xl/worksheets/sheet{i}.xml'))
                    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    first = xml.find('.//s:row/s:c/s:is/s:t', ns)
                    self.assertEqual(first.text, '产品线')

    def test_http_stock_scope_and_worker_enrich_before_filters(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api import stock_detail_reports as api
        from app.core.database import get_db
        from app.services.authorization import get_current_user_context
        from app.services.report_export_data import write_report
        app = FastAPI()
        app.include_router(api.router)
        ctx = dict(user_id=1, product_line_ids=[1, 2], permissions=['report:stock-detail:list', 'report:stock-detail:view'])
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user_context] = lambda: ctx
        parameters = dict(material='M', organization_ids=[100, 200, 300], start_date='2026-06-01', end_date='2026-06-30',
            sort='product_line_name', column_filters=column_values('product_line_name', ['A Line']))

        def scoped_dataset(connection, query, organizations):
            dataset = self.stock_dataset()
            dataset['rows'] = [r for r in dataset['rows'] if r['inventory_key'].organization_id in organizations]
            dataset['openings'] = {k: v for k, v in dataset['openings'].items() if k.organization_id in organizations}
            return dataset

        with TestClient(app) as client, patch.object(api, 'purchase_connection', return_value=nullcontext(self.connection)), \
                patch.object(api, 'read_dataset', side_effect=scoped_dataset) as read:
            response = client.get('/api/reports/stock-detail', params=parameters)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(read.call_args.args[2], [100, 200])
            self.assertEqual(response.json()['items'][0]['product_line_name'], 'A Line')
            self.assertEqual(response.json()['openings'][0]['product_line_name'], 'A Line')
            candidates = client.get('/api/reports/stock-detail/column-options', params={
                'field': 'product_line_name', 'parameters': json.dumps(parameters)})
            self.assertEqual(candidates.status_code, 200, candidates.text)
            self.assertEqual({r['value'] for r in candidates.json()['items']}, {'A Line', 'Z Line'})
            unconfigured = {**parameters, 'column_filters': column_values('product_line_name', ['Other Organization（未配置产品线）'])}
            self.assertEqual(client.get('/api/reports/stock-detail', params=unconfigured).json()['total'], 0)
            ctx['permissions'].append('business:data:all')
            response = client.get('/api/reports/stock-detail', params=unconfigured)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['total'], 1)
            self.assertEqual(response.json()['items'][0]['product_line_name'], 'Other Organization（未配置产品线）')
            ctx['permissions'].pop()
        job = SimpleNamespace(report='stock-detail', parameters=json.dumps(parameters), columns='["product_line_name","balance_qty"]')
        with tempfile.TemporaryDirectory() as directory, \
                patch('app.services.report_export_data.purchase_connection', return_value=nullcontext(self.connection)), \
                patch('app.services.stock_detail_fetch.read_dataset', side_effect=scoped_dataset) as read:
            path = Path(directory) / 'stock.xlsx'
            write_report(self.db, job, ctx, path, lambda n: None)
            self.assertEqual(read.call_args.args[2], [100, 200])
            with zipfile.ZipFile(path) as book:
                sheet = book.read('xl/worksheets/sheet1.xml').decode()
            self.assertEqual(sheet.count('A Line'), 2)
            self.assertNotIn('Z Line', sheet)
            self.assertNotIn('Other Organization', sheet)


if __name__ == '__main__':
    unittest.main()
