import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from contextlib import contextmanager
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base
import app.models.init_db
from app.models.rbac import SysRole, SysRoleMenu, SysMenu
from app.models.project import PmsProjectArchive
from app.models.product_line import SysProductLine
from app.services.purchase_reader import ProjectOrganizationGrant
from fastapi import HTTPException


class ReportApiContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('app.api.purchase_reports'), 'Report API is not implemented')
        from app.api import purchase_reports
        return purchase_reports

    def line(self):
        line = SysProductLine(source_key='kingdee', organization_id=100, organization_code='100',
            organization_name='100', display_name='100', name_key='100')
        self.db.add(line)
        self.db.flush()
        return line

    def test_permissions_are_separate_and_never_replenished(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.purchase_migration'), 'Report permissions are missing')
        from app.services.purchase_migration import initialize_purchase_reports
        admin = SysRole(role_name='Admin', role_code='admin')
        business = SysRole(role_name='Business', role_code='business_admin')
        self.db.add_all([admin, business]); self.db.commit()
        initialize_purchase_reports(self.db)
        view = self.db.query(SysMenu).filter_by(permission_code='report:purchase:view').one()
        export = self.db.query(SysMenu).filter_by(permission_code='report:purchase:export').one()
        self.assertNotEqual(view.id, export.id)
        self.assertEqual(self.db.query(SysRoleMenu).filter_by(role_id=business.id).count(), 0)
        from app.services.role_home import validate_role_home
        ids = [row.menu_id for row in self.db.query(SysRoleMenu).filter_by(role_id=admin.id)]
        validate_role_home(self.db, view.parent_id, ids)
        self.db.query(SysRoleMenu).filter_by(role_id=admin.id, menu_id=export.id).delete(); self.db.commit()
        initialize_purchase_reports(self.db)
        self.assertEqual(self.db.query(SysRoleMenu).filter_by(role_id=admin.id, menu_id=export.id).count(), 0)

    def test_menu_creation_preserves_existing_ids(self):
        from app.services.purchase_migration import initialize_purchase_reports
        self.db.add(SysMenu(id=4, menu_name='既有目录', menu_type='M', parent_id=0))
        self.db.commit()
        initialize_purchase_reports(self.db)
        self.assertEqual(self.db.get(SysMenu, 4).menu_name, '既有目录')
        page = self.db.query(SysMenu).filter_by(permission_code='report:purchase:list').one()
        self.assertEqual(self.db.get(SysMenu, page.parent_id).menu_name, '报表中心')

    def test_scope_always_requires_explicit_project_organization_pairs(self):
        api = self.api()
        line = SysProductLine(source_key='kingdee', organization_id=100, organization_code='100',
            organization_name='100', display_name='100', name_key='100')
        self.db.add(line)
        self.db.flush()
        self.db.add_all([PmsProjectArchive(project_code='A', project_name='A', manager_id=7, business_product_line_id=line.id),
                         PmsProjectArchive(project_code='B', project_name='B', manager_id=8)])
        self.db.commit()
        self.assertEqual(api.project_scope(self.db, {'data_scope': 4, 'product_category_ids': None}), [])
        self.assertEqual(api.project_scope(self.db, {'data_scope': 1, 'user_id': 7,
            'product_line_ids': [line.id]}), [ProjectOrganizationGrant('A', 100)])
        self.assertEqual(api.project_scope(self.db, {'data_scope': 4, 'product_line_ids': []}), [])

    def test_export_requires_view_and_export(self):
        api = self.api()
        for permissions in ([], ['report:purchase:view'], ['report:purchase:export']):
            with self.assertRaises(HTTPException) as result:
                api.ensure_export_permission({'permissions': permissions})
            self.assertEqual(result.exception.status_code, 403)
        api.ensure_export_permission({'permissions': ['report:purchase:view', 'report:purchase:export']})
        self.assertEqual(api.public_row({'requested': Decimal('123456789.1234567890')})['requested'], '123456789.1234567890')

    def test_detail_out_of_scope_is_404_and_never_loads_children(self):
        api = self.api()
        @contextmanager
        def connection():
            yield object()
        with patch.object(api, 'purchase_connection', connection), patch.object(api, 'load_request', return_value=None), patch.object(api, 'load_chains') as children:
            with self.assertRaises(HTTPException) as result:
                api.detail(1, self.db, {'permissions': ['report:purchase:view'], 'data_scope': 4, 'product_category_ids': None})
            self.assertEqual(result.exception.status_code, 404)
            children.assert_not_called()

    def test_catalog_contains_report_fields_with_chinese_sources(self):
        from app.services.field_catalog import build_field_catalog
        fields = [row for row in build_field_catalog() if row['module'] == 'purchase_report']
        self.assertGreaterEqual(len(fields), 20)
        self.assertTrue(all(not row['editable'] for row in fields))
        self.assertTrue(any(row['field_code'] == 'pending_receipt' and row['description'] for row in fields))

    def test_project_names_are_from_pms_not_kingdee(self):
        api = self.api()
        self.assertTrue(hasattr(api, 'enrich_project_names'))
        line = self.line()
        self.db.add(PmsProjectArchive(project_code='A', project_name='PMS 名称', manager_id=7, business_product_line_id=line.id))
        self.db.commit()
        rows = [{'project_code': 'A', 'project_name': '金蝶名称'}, {'project_code': 'B', 'project_name': '不能回退'}]
        api.enrich_project_names(self.db, {'data_scope': 1, 'user_id': 7, 'product_line_ids': [line.id]}, rows)
        self.assertEqual(rows[0]['project_name'], 'PMS 名称')
        self.assertIsNone(rows[1]['project_name'])

    def test_http_permissions_dates_and_safe_service_errors(self):
        api = self.api()
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.services.authorization import get_current_user_context
        from app.core.database import get_db
        app = FastAPI(); app.include_router(api.router)
        ctx = {'user_id': 1, 'permissions': [], 'data_scope': 4, 'product_category_ids': None}
        app.dependency_overrides[get_current_user_context] = lambda: ctx
        app.dependency_overrides[get_db] = lambda: self.db
        with TestClient(app, raise_server_exceptions=False) as client:
            for path in ('', '/metadata', '/options?field=project', '/1', '/export'):
                self.assertEqual(client.get('/api/reports/purchase' + path).status_code, 403)
            ctx['permissions'] = ['report:purchase:view']
            self.assertEqual(client.get('/api/reports/purchase/metadata').status_code, 200)
            self.assertEqual(client.get('/api/reports/purchase?date_from=2026-09-02&date_to=2026-09-01').status_code, 422)
            with patch.object(api, 'purchase_connection', side_effect=RuntimeError('PRIVATE INTERNAL ERROR')):
                response = client.get('/api/reports/purchase')
                self.assertEqual(response.status_code, 503)
                self.assertNotIn('PRIVATE', response.text)

    def test_legacy_export_is_retired_without_querying_erp(self):
        api = self.api()
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.services.authorization import get_current_user_context
        from app.core.database import get_db
        app = FastAPI(); app.include_router(api.router)
        line = self.line()
        ctx = {'user_id': 7, 'permissions': ['report:purchase:view', 'report:purchase:export'], 'data_scope': 1, 'product_line_ids': [line.id]}
        app.dependency_overrides[get_current_user_context] = lambda: ctx
        app.dependency_overrides[get_db] = lambda: self.db
        self.db.add(PmsProjectArchive(project_code='A', project_name='PMS 项目', manager_id=7, business_product_line_id=line.id)); self.db.commit()
        @contextmanager
        def connection():
            yield object()
        data = {'total': 1, 'items': [{'id': 1, 'project_code': 'A', 'bill_no': '=1+1', 'close_status': 'B', 'document_status': 'C', 'progress': 'complete'}]}
        with TestClient(app) as client, patch.object(api, 'list_requests') as query:
            response = client.get('/api/reports/purchase/export?date_from=2026-01-01&page=2')
            self.assertEqual(response.status_code, 410)
            query.assert_not_called()


if __name__ == '__main__':
    unittest.main()
