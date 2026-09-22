import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
import app.models.init_db
from app.services.authorization import get_current_user_context
from app.models.product_line import SysProductLine
from app.schemas.product_line import OrganizationOption


class ProductLineAPI(unittest.TestCase):
    def setUp(self):
        from app.api.product_lines import router
        self.engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.ctx = {'user_id': None, 'permissions': [], 'product_line_ids': []}
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user_context] = lambda: self.ctx
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_module_permissions_reject_each_action(self):
        for method, path, data in (
            ('GET', '/api/product-lines', None),
            ('GET', '/api/product-lines/organizations', None),
            ('GET', '/api/product-lines/options', None),
            ('GET', '/api/product-lines/role-options', None),
            ('POST', '/api/product-lines', {'organization_id': 100}),
            ('PUT', '/api/product-lines/1', {'expected_updated_at': '2026-09-21T00:00:00', 'sort': 2}),
            ('DELETE', '/api/product-lines/1', None),
        ):
            self.assertEqual(self.client.request(method, path, json=data).status_code, 403, path)

    def test_create_uses_verified_source_and_binding_cannot_be_edited(self):
        self.ctx['permissions'] = ['system:product-line:add', 'system:product-line:edit']
        option = OrganizationOption(source_key='kingdee', organization_id=100, code='A', name='金蝶组织', active=True)
        with patch('app.api.product_lines.get_organization', return_value=option) as source:
            response = self.client.post('/api/product-lines', json={'organization_id': 100, 'display_name': '自定义'})
        self.assertEqual(response.status_code, 200, response.text)
        source.assert_called_once_with(100)
        item = response.json()
        self.assertEqual(item['organization_name'], '金蝶组织')
        response = self.client.put('/api/product-lines/' + str(item['id']), json={
            'expected_updated_at': item['updated_at'], 'organization_id': 200})
        self.assertEqual(response.status_code, 422)

    def test_options_only_authorized_and_active_but_labels_keep_disabled_history(self):
        lines = [SysProductLine(source_key='kingdee', organization_id=n, organization_code=str(n),
                 organization_name=str(n), display_name=str(n), name_key=str(n), is_enabled=int(n != 2))
                 for n in (1, 2, 3)]
        self.db.add_all(lines)
        self.db.commit()
        self.ctx.update(permissions=['project:archive:add'], product_line_ids=[lines[0].id, lines[1].id])
        option = OrganizationOption(source_key='kingdee', organization_id=1, code='1', name='1', active=True)
        with patch('app.api.product_lines.get_organization', return_value=option):
            response = self.client.get('/api/product-lines/options')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([r['value'] for r in response.json()['options']], [lines[0].id])
        self.assertEqual(set(response.json()['label_map']), {str(lines[0].id), str(lines[1].id)})

    def test_role_editor_can_read_minimal_choices_without_master_management(self):
        line = SysProductLine(source_key='kingdee', organization_id=1, organization_code='1',
            organization_name='原名', display_name='显示名', name_key='name', is_enabled=0)
        self.db.add(line)
        self.db.commit()
        self.ctx['permissions'] = ['system:role:edit']
        response = self.client.get('/api/product-lines/role-options')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['items'], [{'value': line.id, 'label': '显示名', 'disabled': True}])
        self.assertEqual(self.client.get('/api/product-lines').status_code, 403)

    def test_same_jwt_immediately_loses_and_regains_archive_scope(self):
        from app.api.projects import router as projects_router
        from app.models.user import SysUser
        from app.models.project import PmsProjectArchive
        from app.models.rbac import SysRole, SysMenu, SysRoleMenu, SysUserRole
        from app.models.product_line import SysRoleProductLine
        from app.core.security import user_access_token
        app = self.client.app
        del app.dependency_overrides[get_current_user_context]
        app.include_router(projects_router)
        user = SysUser(username='live-grants', real_name='测试', password_hash='x', status=1)
        role = SysRole(role_code='admin', role_name='可配置管理员', data_scope=4, status=1)
        line = SysProductLine(source_key='kingdee', organization_id=100, organization_code='100',
            organization_name='组织', display_name='产品线', name_key='line')
        self.db.add_all([user, role, line])
        self.db.flush()
        for permission in ('project:archive:view', 'project:archive:edit'):
            menu = SysMenu(menu_name=permission, permission_code=permission, menu_type='B')
            self.db.add(menu)
            self.db.flush()
            self.db.add(SysRoleMenu(role_id=role.id, menu_id=menu.id))
        archive = PmsProjectArchive(project_code='A', project_name='测试', business_product_line_id=line.id)
        self.db.add_all([archive, SysUserRole(user_id=user.id, role_id=role.id),
                         SysRoleProductLine(role_id=role.id, product_line_id=line.id)])
        self.db.commit()
        headers = {'Authorization': 'Bearer ' + user_access_token(user, 'oa')}
        def count():
            result = self.client.get('/api/projects/archives/list', headers=headers)
            self.assertEqual(result.status_code, 200, result.text)
            return result.json()['total']
        self.assertEqual(count(), 1)
        self.db.query(SysRoleProductLine).delete()
        self.db.commit()
        self.assertEqual(count(), 0)
        self.assertEqual(self.client.put(f'/api/projects/archives/{archive.id}', headers=headers,
            json={'customer': '越权'}).status_code, 404)
        self.db.add(SysRoleProductLine(role_id=role.id, product_line_id=line.id))
        self.db.commit()
        self.assertEqual(count(), 1)
        self.db.refresh(archive)
        self.assertIsNone(archive.customer)


if __name__ == '__main__':
    unittest.main()
