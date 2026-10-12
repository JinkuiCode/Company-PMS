"""Initialization switch defaults, live gating, and rollback escape hatch."""
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import app.models.init_db
from app.core.database import Base, get_db
from app.models.parameter import SysParameter
from app.models.user import SysUser
from app.services import parameter

CODE = 'archive.initialization_enabled'


class InitializationParameterContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(SysUser(id=1, username='fixture', real_name='测试', password_hash='unused'))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def disable(self):
        self.db.add(SysParameter(code=CODE, value_text='false', version=1))
        self.db.commit()

    def test_boolean_parameter_default_metadata_and_edit(self):
        item = next((i for i in json.loads(parameter.list_parameters(self.db).body)['items'] if i['code'] == CODE), None)
        self.assertIsNotNone(item, 'initialization parameter must be registered')
        self.assertEqual((item['value_type'], item['value'], item['version']), ('boolean', 'true', 0))
        parameter.update_parameter(self.db, CODE, 'false', 0, 1)
        self.assertFalse(parameter.archive_initialization_enabled(self.db))
        parameter.update_parameter(self.db, CODE, 'true', 1, 1)
        self.assertTrue(parameter.archive_initialization_enabled(self.db))
        for value in ('1', 'True', '', 'yes'):
            with self.assertRaises(HTTPException) as caught:
                parameter.update_parameter(self.db, CODE, value, 2, 1)
            self.assertEqual(caught.exception.status_code, 422)

    def test_disabled_gate_precedes_payload_processing_in_all_services(self):
        from app.services import offline_archive_import as imports, offline_archive_workbook as workbook
        self.disable()
        all_scope = {'permissions': ['business:data:all'], 'user_id': 1}
        operations = [lambda: imports.preview_import(self.db, {}, all_scope),
                      lambda: imports.apply_import(self.db, {}, 1, all_scope),
                      lambda: imports.assign_product_line(self.db, {}, 1, all_scope),
                      lambda: workbook.prepare_workbook(self.db, b'invalid')]
        for operation in operations:
            with self.assertRaises(HTTPException) as caught:
                operation()
            self.assertEqual(caught.exception.status_code, 409)
            self.assertEqual(caught.exception.detail['code'], 'ARCHIVE_INITIALIZATION_DISABLED')

    def test_disabled_does_not_gate_rollback(self):
        from app.services.offline_archive_import import rollback_import
        self.disable()
        with self.assertRaises(HTTPException) as caught:
            rollback_import(self.db, 987, 1, {'permissions': ['business:data:all']})
        self.assertEqual((caught.exception.status_code, caught.exception.detail), (409, '批次不存在或已回退'))

    def test_status_route_requires_archive_view_and_returns_boolean(self):
        from app.api.offline_archives import router
        from app.services.authorization import get_current_user_context
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        context = {'user_id': 1, 'permissions': []}
        app.dependency_overrides[get_current_user_context] = lambda: context
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/offline-archives/initialization-status').status_code, 403)
            context['permissions'] = ['project:archive:view']
            response = client.get('/api/offline-archives/initialization-status')
            self.assertEqual((response.status_code, response.json()), (200, {'enabled': True}))
            self.disable()
            self.assertEqual(client.get('/api/offline-archives/initialization-status').json(), {'enabled': False})
            context['permissions'] = []
            self.assertEqual(client.post('/api/offline-archives/preview', json={}).status_code, 403)
            for route in ('preview', 'apply', 'assign-product-line'):
                context['permissions'] = ['project:archive:import', 'project:archive:assign-line']
                response = client.post('/api/offline-archives/' + route, json={})
                self.assertEqual(response.status_code, 409, response.text)
            response = client.post('/api/offline-archives/workbook', files={'file': ('x.xlsx', b'invalid')})
            self.assertEqual(response.status_code, 409)


if __name__ == '__main__':
    unittest.main()
