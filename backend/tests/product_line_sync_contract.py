"""Accepted queue work is pinned to its organization; interactive retries are scoped."""
import json
import unittest
from unittest.mock import patch

import product_line_project_scope_contract as fixtures
from app.models.erp_task import ErpSyncTask
from app.services import erp_queue
from fastapi import HTTPException


class SyncScope(unittest.TestCase):
    setUp = fixtures.ProjectScope.setUp
    tearDown = fixtures.ProjectScope.tearDown

    def queued(self):
        task = erp_queue.enqueue(self.db, self.archives[0], self.users[0].id)
        self.db.commit()
        return task

    def grant_inspection(self):
        from app.models.rbac import SysRole, SysMenu, SysRoleMenu, SysUserRole
        from app.models.product_line import SysRoleProductLine
        role = SysRole(role_name='核查', role_code='verify', data_scope=4)
        menu = SysMenu(menu_name='重试', menu_type='B', permission_code='system:sync:retry')
        self.db.add_all([role, menu])
        self.db.flush()
        self.db.add_all([SysUserRole(user_id=self.users[0].id, role_id=role.id),
            SysRoleMenu(role_id=role.id, menu_id=menu.id),
            *[SysRoleProductLine(role_id=role.id, product_line_id=line.id) for line in self.lines]])
        self.db.commit()

    def test_inspection_checks_original_target_before_and_after_external_query(self):
        self.grant_inspection()
        task = self.queued()
        task.status = 'review'
        self.archives[0].erp_sync_status = 'review'
        self.db.commit()
        for during in (False, True):
            self.archives[0].business_product_line_id = self.lines[0 if during else 1].id
            self.db.commit()
            def response(*args, **kwargs):
                self.archives[0].business_product_line_id = self.lines[1].id
                self.db.commit()
                return dict(FNumber=task.project_code, FDataValue=task.project_code,
                            FDescription=task.project_name, FDocumentStatus='C')
            with patch('app.services.kingdee.KingdeeClient') as client:
                client.return_value.login.return_value = True
                client.return_value.query_assistant_data.side_effect = response
                with self.assertRaises(HTTPException) as caught:
                    erp_queue.inspect_result(self.db, task.id, self.users[0].id)
                self.assertEqual(caught.exception.status_code, 409)
                if not during:
                    client.assert_not_called()
            self.db.rollback()
            self.assertEqual(self.db.get(ErpSyncTask, task.id).status, 'review')

    def test_queue_records_original_line_and_organization(self):
        task = self.queued()
        target = json.loads(task.history)[0].get('target')
        self.assertEqual(target, dict(product_line_id=self.lines[0].id, organization_id=100,
                                     source_key='kingdee'))

    def test_changed_line_cannot_send_or_automatically_retry(self):
        task = self.queued()
        self.archives[0].business_product_line_id = self.lines[1].id
        self.db.commit()
        with patch('app.services.kingdee.sync_project_archive_to_erp') as send:
            erp_queue.run_once(self.db)
            erp_queue.run_once(self.db)
        send.assert_not_called()
        self.assertEqual(task.status, 'failed')

    def test_unassigned_and_legacy_unpinned_tasks_cannot_send(self):
        for unassigned in (False, True):
            task = self.queued()
            if unassigned:
                self.archives[0].business_product_line_id = None
            else:
                task.history = '[]'
            self.db.commit()
            with patch('app.services.kingdee.sync_project_archive_to_erp') as send:
                erp_queue.run_once(self.db)
            send.assert_not_called()
            self.assertEqual(task.status, 'failed')

    def test_retry_without_current_grant_does_not_enqueue(self):
        task = self.queued()
        task.status = 'failed'
        self.archives[0].erp_sync_status = 'failed'
        self.db.commit()
        with self.assertRaises(HTTPException) as caught:
            erp_queue.retry(self.db, task.id, self.users[0].id)
        self.assertIn(caught.exception.status_code, (403, 404))
        self.assertEqual(self.db.query(ErpSyncTask).count(), 1)

    def test_inspect_without_grant_does_not_contact_erp(self):
        task = self.queued()
        task.status = 'review'
        self.db.commit()
        with patch('app.services.kingdee.KingdeeClient') as client:
            with self.assertRaises(HTTPException) as caught:
                erp_queue.inspect_result(self.db, task.id, self.users[0].id)
        self.assertIn(caught.exception.status_code, (403, 404))
        client.assert_not_called()

    def test_accepted_background_work_does_not_require_old_operator_grants(self):
        task = self.queued()
        with patch('app.services.kingdee.sync_project_archive_to_erp', return_value={'success': True}) as send:
            erp_queue.run_once(self.db)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(task.status, 'success')


if __name__ == '__main__':
    unittest.main()
