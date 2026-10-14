"""Department leaders: temporary database only, no live personnel changes."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEMP = tempfile.TemporaryDirectory()
os.environ['DB_DIALECT'] = 'sqlite'
os.environ['SQLITE_DB_PATH'] = str(Path(TEMP.name) / 'unused.db')

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
import app.models.init_db
from app.api import depts, users
from app.models.rbac import SysDept, SysRole, SysUserRole
from app.models.user import SysUser
from app.models.operation_log import SysOperationLog
from app.services.authorization import get_current_user_context


class DepartmentLeaderContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.first = SysDept(dept_name='第一部门', status=1)
        self.second = SysDept(dept_name='第二部门', status=1)
        self.db.add_all([self.first, self.second])
        self.db.flush()
        self.local = SysUser(username='A001', real_name='同名', password_hash='test-only', dept_id=self.first.id, status=1)
        self.outside = SysUser(username='A002', real_name='同名', password_hash='test-only', dept_id=self.second.id, status=1)
        self.disabled = SysUser(username='A003', real_name='历史负责人', password_hash='test-only', dept_id=self.second.id, status=0)
        self.db.add_all([self.local, self.outside, self.disabled])
        self.db.flush()
        role = SysRole(role_code='existing', role_name='原角色', status=1, data_scope=1)
        self.db.add(role)
        self.db.flush()
        self.db.add(SysUserRole(user_id=self.outside.id, role_id=role.id))
        self.db.commit()
        self.original_roles = [(row.user_id, row.role_id) for row in self.db.query(SysUserRole).all()]
        self.ctx = {'user_id': self.local.id, 'permissions': ['system:user:view', 'system:user:add', 'system:user:edit'],
                    'data_scope': 1, 'product_line_ids': []}
        app = FastAPI()
        app.include_router(depts.router)
        app.include_router(users.router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user_context] = lambda: self.ctx
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_missing_null_disabled_and_nonexistent_leader_rejected_without_writes(self):
        for value in ['missing', None, self.disabled.id, 9999]:
            with self.subTest(value=value):
                data = {'dept_name': '新增部门'}
                if value != 'missing':
                    data['leader_id'] = value
                response = self.client.post('/api/depts', json=data)
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.db.query(SysDept).count(), 2)
        self.assertEqual(self.db.query(SysOperationLog).count(), 0)

    def test_enabled_outside_user_can_lead_two_departments_without_membership_changes(self):
        for dept in [self.first, self.second]:
            response = self.client.put(f'/api/depts/{dept.id}', json={'leader_id': self.outside.id})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(self.db.get(SysDept, dept.id).leader_id, self.outside.id)
        self.assertEqual(self.outside.dept_id, self.second.id)
        self.assertEqual(self.local.dept_id, self.first.id)
        self.assertEqual([(row.user_id, row.role_id) for row in self.db.query(SysUserRole).all()], self.original_roles)
        logs = self.db.query(SysOperationLog).all()
        self.assertEqual(len(logs), 2)
        self.assertTrue(all(log.entity_type == 'sys_dept' for log in logs))
        self.assertIn('leader_id', logs[0].after_data)

    def test_update_merged_department_requires_valid_leader_and_preserves_existing_on_partial_write(self):
        response = self.client.put(f'/api/depts/{self.first.id}', json={'dept_name': '改名'})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.first.dept_name, '第一部门')
        self.first.leader_id = self.outside.id
        self.db.commit()
        for value in [None, self.disabled.id, 9999]:
            response = self.client.put(f'/api/depts/{self.first.id}', json={'leader_id': value, 'dept_name': '改名'})
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(self.first.leader_id, self.outside.id)
            self.assertEqual(self.first.dept_name, '第一部门')
        response = self.client.put(f'/api/depts/{self.first.id}', json={'parent_id': self.second.id})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.first.leader_id, self.outside.id)

    def test_historical_null_and_disabled_leader_readable_with_display_label(self):
        self.second.leader_id = self.disabled.id
        self.db.commit()
        response = self.client.get('/api/depts/tree')
        self.assertEqual(response.status_code, 200, response.text)
        rows = {row['id']: row for row in response.json()}
        self.assertIsNone(rows[self.first.id]['leader_id'])
        self.assertEqual(rows[self.second.id]['leader_label'], '历史负责人（A003）')

    def test_minimal_active_options_include_account_for_same_name_and_no_secret(self):
        response = self.client.get('/api/users/options')
        self.assertEqual(response.status_code, 200, response.text)
        options = response.json()
        self.assertEqual({row['id'] for row in options}, {self.local.id, self.outside.id})
        self.assertEqual({row['username'] for row in options}, {'A001', 'A002'})
        self.assertTrue(all(set(row) == {'id', 'username', 'real_name', 'dept_id'} for row in options))

    def test_write_permissions_still_required(self):
        self.ctx['permissions'] = ['system:user:view']
        response = self.client.post('/api/depts', json={'dept_name': '无权新增', 'leader_id': self.outside.id})
        self.assertEqual(response.status_code, 403, response.text)
        response = self.client.put(f'/api/depts/{self.first.id}', json={'leader_id': self.outside.id})
        self.assertEqual(response.status_code, 403, response.text)


if __name__ == '__main__':
    unittest.main()
