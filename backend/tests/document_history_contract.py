"""Document history exposes authorized business events without global audit access."""
import sys
import unittest
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import archive_change_contract as fixture
from fastapi import APIRouter
from app.models.operation_log import SysOperationLog
from app.models.field_policy import SysBusinessFieldPolicy
from app.services.operation_log import record_operation_log


class DocumentHistory(unittest.TestCase):
    actor = fixture.ArchiveChangeContract.actor
    snapshot = fixture.ArchiveChangeContract.snapshot
    payload = fixture.ArchiveChangeContract.payload
    submit = fixture.ArchiveChangeContract.submit
    tearDown = fixture.ArchiveChangeContract.tearDown

    def setUp(self):
        fixture.ArchiveChangeContract.setUp(self)
        from main import app
        routes = [route for route in app.routes if getattr(route, 'path', '').startswith('/api/document-history/')]
        self.client.app.include_router(APIRouter(routes=routes))

    def log(self, **values):
        parameters = dict(module='项目档案', action='update', entity_type='pms_project_archive',
            entity_id=self.archive.id, operator_id=self.other.id, summary='客户变化：不应从摘要泄露私有值',
            before_data={'customer': '旧私有客户'}, after_data={'customer': '新私有客户'})
        parameters.update(values)
        result = record_operation_log(self.db, **parameters)
        self.db.commit()
        return result

    def history(self, **params):
        return self.client.get(f'/api/document-history/archive/{self.archive.id}', params=params)

    def test_other_actors_are_visible_without_global_audit_permission(self):
        self.log()
        response = self.history()
        self.assertEqual(response.status_code, 200, response.text)
        row = response.json()['items'][0]
        self.assertEqual(row['actor'], self.other.real_name)
        self.assertEqual(row['action_label'], '编辑')
        self.assertEqual(row['diff_items'][0]['field_label'], '客户')
        for forbidden in ('before_data', 'after_data', 'diff_data', 'error_msg', 'ip_address', 'request_path'):
            self.assertNotIn(forbidden, row)

    def test_hidden_values_do_not_escape_through_snapshot_or_summary(self):
        self.log()
        self.db.add(SysBusinessFieldPolicy(module_code='project_archive', field_key='customer',
            visible=False, editable=False, required=False, list_available=False))
        self.db.commit()
        response = self.history()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('私有客户', response.text)
        self.assertNotIn('不应从摘要', response.text)
        self.assertEqual(response.json()['items'][0]['diff_items'], [])

    def test_revoke_scope_or_action_hides_history(self):
        self.log()
        self.actor(self.owner, lines=[])
        self.assertEqual(self.history().status_code, 404)
        self.actor(self.owner, permissions=['project:archive:edit'])
        self.assertEqual(self.history().status_code, 403)

    def test_approval_events_are_related_to_the_archive_and_filtered(self):
        self.submit(customer='申请中的私有客户')
        response = self.history()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('submit', [row['action'] for row in response.json()['items']])
        self.db.add(SysBusinessFieldPolicy(module_code='project_archive', field_key='customer',
            visible=False, editable=False, required=False, list_available=False))
        self.db.commit()
        self.assertNotIn('申请中的私有客户', self.history().text)
        self.assertNotIn('updates_json', self.history().text)

    def test_new_display_snapshot_keeps_reference_name_when_master_is_renamed(self):
        self.log(before_data={'manager_id': self.owner.id}, after_data={'manager_id': self.other.id})
        old = self.other.real_name
        self.other.real_name = '重命名后的姓名'; self.db.commit()
        response = self.history()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(old, response.json()['items'][0]['diff_items'][0]['after_display'])
        self.assertNotIn('重命名后的姓名', response.text)

    def test_root_deletion_removes_business_access_but_keeps_audit(self):
        log = self.log()
        self.db.delete(self.archive); self.db.commit()
        self.assertEqual(self.history().status_code, 404)
        self.assertIsNotNone(self.db.get(SysOperationLog, log.id))

    def test_pagination_and_actions_are_scoped_to_the_document(self):
        self.log(action='create', before_data=None)
        self.log(action='maintain')
        response = self.history(page_size=1)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['total'], 2)
        self.assertEqual(response.json()['items'][0]['action'], 'maintain')
        response = self.history(action='create')
        self.assertEqual(response.json()['total'], 1)
        self.assertEqual(response.json()['items'][0]['action'], 'create')

    def test_noop_business_update_does_not_create_a_false_event(self):
        self.log(before_data={'customer': '未改变'}, after_data={'customer': '未改变'})
        self.assertEqual(self.db.query(SysOperationLog).count(), 0)

    def test_free_text_credentials_are_removed_from_audit_storage(self):
        log = self.log(summary='password=secret-value Authorization: Bearer sample-token',
                       error_msg='app_secret=secret-value')
        self.assertNotIn('secret-value', log.summary)
        self.assertNotIn('sample-token', log.summary)
        self.assertNotIn('secret-value', log.error_msg)

    def test_audit_uses_event_snapshot_and_masks_legacy_raw_text(self):
        from app.services.operation_log import get_operation_logs
        log = self.log(before_data={'manager_id': self.owner.id}, after_data={'manager_id': self.other.id})
        old = self.other.real_name
        self.other.real_name = '后来改名'; self.db.commit()
        log.summary = 'token=old-secret'
        log.before_data = '{"password":"old-secret"}'
        self.db.commit()
        result = get_operation_logs(self.db)['items'][0]
        self.assertIn(old, result['diff_items'][0]['after_display'])
        self.assertNotIn('old-secret', json.dumps(result))

    def test_legacy_event_identifies_fallback_as_current_not_historical_name(self):
        log = self.log(before_data={'manager_id': self.owner.id}, after_data={'manager_id': self.other.id})
        log.diff_items_data = None
        self.other.real_name = '不可当作旧姓名'; self.db.commit()
        response = self.history()
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()['items'][0]['diff_items'][0]
        self.assertEqual(item['after_display'], '不可当作旧姓名（other）')
        self.assertIsNone(log.diff_items_data)

    def test_deleted_child_event_remains_on_surviving_project(self):
        from app.models.project import PmsTask
        from app.services.project import delete_task
        from app.services.document_history import get_document_history
        task = PmsTask(project_id=self.linked.id, task_name='删除任务样本')
        self.db.add(task); self.db.commit()
        self.actor(self.owner, permissions=['project:list:view', 'project:list:delete'])
        delete_task(self.db, task.id, self.owner.id, scope_context=self.ctx)
        result = get_document_history(self.db, 'project', self.linked.id, self.ctx)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['action'], 'delete')
        self.assertTrue(any(item['before_display'] == '删除任务样本' for item in result['items'][0]['diff_items']))

    def test_project_cascade_deletion_retains_child_snapshots_only_in_admin_audit(self):
        from app.models.project import PmsTask, PmsProgressLog
        from app.services.project import delete_project
        task = PmsTask(project_id=self.linked.id, task_name='保留子记录')
        self.db.add(task); self.db.flush()
        self.db.add(PmsProgressLog(task_id=task.id, old_progress=0, new_progress=50, operator_id=self.owner.id))
        self.db.commit()
        self.actor(self.owner, permissions=['project:list:view', 'project:list:delete'])
        delete_project(self.db, self.linked.id, self.owner.id, scope_context=self.ctx)
        log = self.db.query(SysOperationLog).filter_by(entity_type='pms_project', action='delete').one()
        snapshot = json.loads(log.before_data)
        self.assertEqual(snapshot['tasks'][0]['task_name'], '保留子记录')
        self.assertEqual(snapshot['progress_logs'][0]['new_progress'], 50)
        response = self.client.get(f'/api/document-history/project/{self.linked.id}')
        self.assertEqual(response.status_code, 404)

    def test_sso_name_change_and_autocreate_roll_back_if_audit_fails(self):
        from unittest.mock import patch
        from app.services import sso
        from app.models.rbac import SysRole
        from app.models.user import SysUser
        old = self.owner.real_name
        with patch.object(sso, 'record_operation_log', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError): sso.find_or_create_user(self.db, self.owner.username, '新姓名', '')
        self.db.expire_all()
        self.assertEqual(self.db.get(SysUser, self.owner.id).real_name, old)
        self.db.add(SysRole(role_code='operator', role_name='操作员')); self.db.commit()
        with patch.object(sso.settings, 'SSO_AUTO_CREATE_USER', True), patch.object(sso, 'record_operation_log', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError): sso.find_or_create_user(self.db, 'sso-atomic-fixture', '新用户', self.dept.dept_name)
        self.assertIsNone(self.db.query(SysUser).filter_by(username='sso-atomic-fixture').first())


if __name__ == '__main__':
    unittest.main()
