from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.database import get_db
from app.services.authorization import get_current_user_context


class ApiContract(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('app.api.stock_detail_reports'))
        from app.api import stock_detail_reports
        self.api = stock_detail_reports
        self.ctx = {'user_id': 1, 'permissions': ['report:stock-detail:list', 'report:stock-detail:view']}
        app = FastAPI()
        app.include_router(self.api.router)
        app.dependency_overrides[get_db] = lambda: None
        app.dependency_overrides[get_current_user_context] = lambda: self.ctx
        self.client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)
        self.scope = patch.object(self.api, 'authorized_organizations', return_value=[1])
        self.scope.start()
        self.addCleanup(self.scope.stop)

    def params(self):
        return dict(material='M1', start_date='2026-06-01', end_date='2026-06-30')

    def test_all_routes_require_current_list_permission(self):
        self.ctx['permissions'] = []
        for path, params in (('', self.params()), ('/metadata', {}), ('/options', {'field': 'stock'})):
            self.assertEqual(self.client.get('/api/reports/stock-detail' + path, params=params).status_code, 403)

    def test_blank_material_never_opens_erp(self):
        with patch.object(self.api, 'purchase_connection') as connection:
            for value in ('', '   '):
                self.assertEqual(self.client.get('/api/reports/stock-detail', params={**self.params(), 'material': value}).status_code, 422)
            connection.assert_not_called()

    def test_menu_alone_does_not_grant_business_data(self):
        self.ctx['permissions'] = ['report:stock-detail:list']
        with patch.object(self.api, 'purchase_connection') as connection:
            self.assertEqual(self.client.get('/api/reports/stock-detail', params=self.params()).status_code, 403)
            self.assertEqual(self.client.get('/api/reports/stock-detail/options?field=stock').status_code, 403)
            connection.assert_not_called()

    def test_empty_scope_never_opens_erp(self):
        with patch.object(self.api, 'authorized_organizations', return_value=[]), patch.object(self.api, 'purchase_connection') as connection:
            response = self.client.get('/api/reports/stock-detail', params=self.params())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['total'], 0)
            self.assertEqual(self.client.get('/api/reports/stock-detail/options?field=stock').json()['items'], [])
            connection.assert_not_called()

    def test_data_source_errors_do_not_leak_details(self):
        with patch.object(self.api, 'purchase_connection', side_effect=RuntimeError('PRIVATE_CONNECTION')):
            response = self.client.get('/api/reports/stock-detail', params=self.params())
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('PRIVATE_CONNECTION', response.text)

    def test_text_warehouse_and_unknown_option_are_rejected(self):
        self.assertEqual(self.client.get('/api/reports/stock-detail', params={**self.params(), 'stock_id': '研发仓'}).status_code, 422)
        self.assertEqual(self.client.get('/api/reports/stock-detail/options?field=price').status_code, 422)


if __name__ == '__main__':
    unittest.main()
