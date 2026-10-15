"""Explicit maintenance is separate from ordinary responsibility/approval rules."""
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import archive_change_contract as fixture
from app.models.operation_log import SysOperationLog
from app.models.erp_task import ErpSyncTask

PERMISSIONS = ['project:archive:view', 'project:archive:edit', 'project:archive:maintain']


class ArchiveMaintenance(unittest.TestCase):
    actor = fixture.ArchiveChangeContract.actor
    snapshot = fixture.ArchiveChangeContract.snapshot
    tearDown = fixture.ArchiveChangeContract.tearDown
    submit = fixture.ArchiveChangeContract.submit
    payload = fixture.ArchiveChangeContract.payload

    def setUp(self):
        fixture.ArchiveChangeContract.setUp(self)
        self.actor(self.other, permissions=PERMISSIONS.copy())

    def body(self, **updates):
        return dict(updates=updates, expected_version=self.snapshot()['change_version'], reason='修正历史业务资料')

    def save(self, body):
        return self.client.put(f'/api/projects/archives/{self.archive.id}/maintenance', json=body)

    def test_maintenance_is_explicit_and_does_not_open_ordinary_editing(self):
        row = self.snapshot()
        self.assertFalse(row['can_edit'])
        self.assertTrue(row['can_maintain'])
        normal = self.client.put(f'/api/projects/archives/{self.archive.id}', json={
            'customer': '普通路径拒绝', 'expected_version': row['change_version']})
        self.assertEqual(normal.status_code, 403)
        result = self.save(self.body(customer='修正客户'))
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['mode'], 'maintenance')
        self.db.refresh(self.archive)
        self.assertEqual(self.archive.customer, '修正客户')
        self.assertEqual(self.db.query(self.Change).count(), 0)
        logs = self.db.query(SysOperationLog).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].action, 'maintain')
        self.assertIn('修正历史业务资料', logs[0].summary)
        self.assertEqual(json.loads(logs[0].diff_data)['customer']['after'], '修正客户')

    def test_preview_is_read_only_and_returns_server_chinese_differences(self):
        body = self.body(customer='新客户')
        body.pop('reason')
        response = self.client.post(f'/api/projects/archives/{self.archive.id}/maintenance/preview',
                                   json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['differences'][0]['field_label'], '客户')
        self.db.refresh(self.archive)
        self.assertIsNone(self.archive.customer)
        self.assertEqual(self.db.query(SysOperationLog).count(), 0)

    def test_each_action_permission_is_required(self):
        body = self.body(customer='不可修改')
        for permission in PERMISSIONS:
            self.actor(self.other, permissions=[item for item in PERMISSIONS if item != permission] + ['business:data:all'])
            self.assertEqual(self.save(body).status_code, 403, permission)

    def test_cross_product_line_and_empty_scope_cannot_maintain(self):
        body = self.body(customer='越权')
        self.actor(self.other, permissions=PERMISSIONS, lines=[])
        self.assertEqual(self.save(body).status_code, 404)

    def test_blank_reason_and_no_business_change_are_rejected(self):
        body = self.body(customer='新客户')
        self.assertEqual(self.save({**body, 'reason': '   '}).status_code, 422)
        self.assertEqual(self.save(self.body(project_name=self.archive.project_name)).status_code, 422)
        self.assertEqual(self.db.query(SysOperationLog).count(), 0)

    def test_stale_version_cannot_overwrite(self):
        body = self.body(customer='过期草稿')
        self.archive.project_name = '他人最新名称'; self.db.commit()
        self.assertEqual(self.save(body).status_code, 409)
        self.db.refresh(self.archive)
        self.assertIsNone(self.archive.customer)

    def test_disabled_or_syncing_or_review_archive_is_protected(self):
        for field, value in [('is_enabled', 0), ('erp_sync_status', 'pending'), ('erp_sync_status', 'review')]:
            body = self.body(customer='不能覆盖')
            setattr(self.archive, field, value); self.db.commit()
            self.assertEqual(self.save(body).status_code, 409, (field, value))
            setattr(self.archive, field, 1 if field == 'is_enabled' else None); self.db.commit()

    def test_pending_business_approval_is_not_bypassed(self):
        self.actor(self.owner)
        self.submit(customer='待审批客户')
        self.actor(self.other, permissions=PERMISSIONS)
        self.assertEqual(self.save(self.body(customer='强制覆盖')).status_code, 409)
        self.db.refresh(self.archive)
        self.assertIsNone(self.archive.customer)

    def test_missing_owner_can_be_repaired_without_changing_personnel(self):
        self.archive.manager_id = None; self.db.commit()
        response = self.save(self.body(manager_id=self.owner.id))
        self.assertEqual(response.status_code, 200, response.text)
        self.db.refresh(self.archive)
        self.assertEqual(self.archive.manager_id, self.owner.id)
        self.assertEqual(self.owner.dept_id, self.dept.id)

    def test_new_owner_without_valid_department_head_is_rejected(self):
        response = self.save(self.body(manager_id=self.other.id))
        self.assertEqual(response.status_code, 422, response.text)
        self.db.refresh(self.archive)
        self.assertEqual(self.archive.manager_id, self.owner.id)

    def test_synced_identity_cannot_be_rewritten(self):
        self.archive.erp_synced = 1; self.db.commit()
        response = self.save(self.body(project_code='NEW-CODE'))
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['detail']['code'], 'ARCHIVE_CODE_LOCKED')

    def test_maintenance_preserves_sync_policy_and_pins_its_authorization(self):
        result = self.save(self.body(project_name='维护后的名称'))
        self.assertEqual(result.status_code, 200, result.text)
        task = self.db.query(ErpSyncTask).one()
        self.assertEqual(json.loads(task.history)[0]['authorization']['action'], 'project:archive:maintain')
        task.status = 'success'; self.archive.erp_sync_status = 'success'
        self.archive.erp_sync_policy = 'manual'; self.db.commit()
        result = self.save(self.body(project_name='手动档案名称'))
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.db.query(ErpSyncTask).count(), 1)

    def test_log_failure_rolls_back_business_values(self):
        body = self.body(customer='不得落库')
        with patch('app.services.project.record_operation_log', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.save(body)
        self.db.refresh(self.archive)
        self.assertIsNone(self.archive.customer)

    def test_actual_authorization_revocation_rejects_the_same_session(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.projects import router
        from app.core.database import get_db
        from app.core.security import user_access_token
        from app.models.rbac import SysRole, SysMenu, SysRoleMenu, SysUserRole
        from app.models.product_line import SysRoleProductLine
        role = SysRole(role_code='maintenance-fixture', role_name='维护测试', data_scope=4, status=1)
        self.db.add(role); self.db.flush()
        menus = [SysMenu(menu_name=code, permission_code=code, menu_type='B', status=1) for code in PERMISSIONS]
        self.db.add_all(menus); self.db.flush()
        self.db.add_all([SysRoleMenu(role_id=role.id, menu_id=menu.id) for menu in menus])
        self.db.add_all([SysUserRole(user_id=self.other.id, role_id=role.id),
            SysRoleProductLine(role_id=role.id, product_line_id=1)])
        self.db.commit()
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        headers = {'Authorization': f'Bearer {user_access_token(self.other, "oa")}'}
        body = self.body(customer='有权维护')
        with TestClient(app) as client:
            response = client.put(f'/api/projects/archives/{self.archive.id}/maintenance', json=body, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            body = self.body(customer='撤权后拒绝')
            self.db.query(SysRoleMenu).filter_by(menu_id=menus[2].id).delete(); self.db.commit()
            response = client.put(f'/api/projects/archives/{self.archive.id}/maintenance', json=body, headers=headers)
            self.assertEqual(response.status_code, 403)
            self.db.add(SysRoleMenu(role_id=role.id, menu_id=menus[2].id))
            self.db.query(SysRoleProductLine).delete(); self.db.commit()
            response = client.put(f'/api/projects/archives/{self.archive.id}/maintenance', json=body, headers=headers)
            self.assertEqual(response.status_code, 404)
            self.db.refresh(self.archive)
            self.assertEqual(self.archive.customer, '有权维护')


if __name__ == '__main__':
    unittest.main()
