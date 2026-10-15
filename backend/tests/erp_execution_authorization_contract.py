"""Queue execution reauthorizes synthetic users before any external request."""
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import erp_queue_contract as fixture
from app.services import erp_queue
from app.models.rbac import SysRole, SysMenu, SysRoleMenu
from app.models.product_line import SysRoleProductLine
from app.models.operation_log import SysOperationLog


class ExecutionAuthorization(unittest.TestCase):
    tearDown = fixture.QueueContract.tearDown

    def setUp(self):
        fixture.QueueContract.setUp(self)
        self.role = self.db.query(SysRole).one()
        self.menus = {}
        for action in ('add', 'edit', 'sync', 'view', 'maintain'):
            code = f'project:archive:{action}'
            menu = self.db.query(SysMenu).filter_by(permission_code=code).first()
            if menu is None:
                menu = SysMenu(menu_name=action, menu_type='B', permission_code=code, status=1)
                self.db.add(menu); self.db.flush()
                self.db.add(SysRoleMenu(role_id=self.role.id, menu_id=menu.id))
            self.menus[action] = menu
        self.db.commit()

    def queued(self, **options):
        task = erp_queue.enqueue(self.db, self.archive, self.user.id, **options)
        self.db.commit()
        return task

    def revoked(self, task):
        with patch('app.services.kingdee.sync_project_archive_to_erp', return_value={'success': True}) as external:
            self.assertTrue(erp_queue.run_once(self.db))
        external.assert_not_called()
        self.db.refresh(task); self.db.refresh(self.archive)
        self.assertEqual(task.status, 'failed')
        self.assertEqual(task.attempts, 0)
        self.assertEqual(self.archive.erp_sync_status, 'failed')
        self.assertIn('未发送', task.message)
        self.assertTrue(self.db.query(SysOperationLog).filter_by(status='failed').first())

    def test_current_authorization_is_passed_to_the_sync_claim(self):
        task = self.queued()
        with patch('app.services.kingdee.sync_project_archive_to_erp', return_value={'success': True}) as external:
            erp_queue.run_once(self.db)
        scope = external.call_args.kwargs['scope_context']
        self.assertEqual(scope['user_id'], self.user.id)
        self.assertEqual(scope['product_line_ids'], [self.line.id])
        self.assertEqual(task.status, 'success')

    def test_product_line_revoked_after_enqueue_stops_execution(self):
        task = self.queued()
        self.db.query(SysRoleProductLine).delete(); self.db.commit()
        self.revoked(task)

    def test_action_revoked_is_not_bypassed_by_admin_or_all_data(self):
        task = self.queued()
        self.role.role_code = 'admin'
        menu = SysMenu(menu_name='全部数据', menu_type='B', permission_code='business:data:all', status=1)
        self.db.add(menu); self.db.flush()
        self.db.add(SysRoleMenu(role_id=self.role.id, menu_id=menu.id))
        self.db.query(SysRoleMenu).filter_by(menu_id=self.menus['edit'].id).delete(); self.db.commit()
        self.revoked(task)

    def test_disabled_user_stops_execution(self):
        task = self.queued()
        self.user.status = 0; self.db.commit()
        self.revoked(task)

    def test_deleted_user_stops_execution(self):
        from app.models.rbac import SysUserRole
        task = self.queued()
        self.db.query(SysUserRole).filter_by(user_id=self.user.id).delete()
        self.db.delete(self.user); self.db.commit()
        self.revoked(task)

    def test_disabled_role_stops_execution(self):
        task = self.queued()
        self.role.status = 0; self.db.commit()
        self.revoked(task)

    def test_missing_actor_is_not_a_system_identity(self):
        task = self.queued()
        task.operator_id = None; self.db.commit()
        self.revoked(task)

    def test_legacy_history_without_action_source_fails_closed(self):
        task = self.queued()
        events = json.loads(task.history)
        events[0].pop('authorization', None)
        task.history = json.dumps(events); self.db.commit()
        self.revoked(task)

    def test_action_source_is_specific_and_cannot_be_replaced_with_empty_permissions(self):
        task = self.queued(required_permission='project:archive:add')
        events = json.loads(task.history)
        self.assertEqual(events[0]['authorization']['action'], 'project:archive:add')
        events[0]['authorization']['permissions'] = []
        task.history = json.dumps(events); self.db.commit()
        self.revoked(task)

    def test_manual_sync_requires_sync_action_not_only_edit(self):
        task = self.queued(explicit=True)
        self.db.query(SysRoleMenu).filter_by(menu_id=self.menus['sync'].id).delete(); self.db.commit()
        self.revoked(task)

    def test_creation_source_does_not_require_edit_action(self):
        task = self.queued(required_permission='project:archive:add')
        self.db.query(SysRoleMenu).filter_by(menu_id=self.menus['edit'].id).delete(); self.db.commit()
        with patch('app.services.kingdee.sync_project_archive_to_erp', return_value={'success': True}) as external:
            erp_queue.run_once(self.db)
        external.assert_called_once()
        self.assertEqual(task.status, 'success')

    def test_maintenance_source_requires_maintenance_and_edit_and_view(self):
        task = self.queued(required_permission='project:archive:maintain')
        self.db.query(SysRoleMenu).filter_by(menu_id=self.menus['view'].id).delete(); self.db.commit()
        self.revoked(task)

    def test_revocation_at_the_sync_claim_has_the_same_failure_message_and_audit(self):
        from app.services import erp_execution_authorization as authorization
        original = authorization.authorize_task_execution
        task = self.queued()
        calls = []
        def check(db, current_task, archive):
            calls.append(current_task.id)
            if len(calls) == 3:
                self.db.query(SysRoleMenu).filter_by(menu_id=self.menus['edit'].id).delete()
                self.db.commit()
            return original(db, current_task, archive)
        with patch.object(authorization, 'authorize_task_execution', side_effect=check), \
                patch('app.services.kingdee.KingdeeClient') as client:
            erp_queue.run_once(self.db)
        client.assert_not_called()
        self.db.refresh(task)
        self.assertEqual(len(calls), 3)
        self.assertEqual(task.status, 'failed')
        self.assertIn('原操作人或授权已变化', task.message)
        self.assertTrue(self.db.query(SysOperationLog).filter_by(status='failed').first())

    def test_old_authorization_failure_cannot_overwrite_a_new_task_state(self):
        from app.services import erp_execution_authorization as authorization
        task = self.queued()
        newer = []
        def changed(db, current_task, archive):
            newer.append(erp_queue.enqueue(db, archive, self.user.id))
            db.commit()
            raise authorization.authorization_changed()
        with patch.object(authorization, 'authorize_task_execution', side_effect=changed), \
                patch('app.services.kingdee.sync_project_archive_to_erp') as external:
            erp_queue.run_once(self.db)
        external.assert_not_called()
        self.db.refresh(task); self.db.refresh(self.archive)
        self.assertEqual(task.status, 'failed')
        self.assertEqual(newer[0].status, 'queued')
        self.assertEqual(self.archive.erp_sync_status, 'queued')


if __name__ == '__main__':
    unittest.main()
