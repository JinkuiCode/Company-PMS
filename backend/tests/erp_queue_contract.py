"""Persistent ERP queue behavior, using an isolated SQLite database only."""
import sys
import unittest
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base
import app.models.init_db  # register all tables
from app.models.project import PmsProjectArchive
from app.models.erp_task import ErpSyncTask
from app.services import erp_queue
from fastapi import HTTPException


class QueueContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.archive = PmsProjectArchive(project_code='TEST', project_name='名称', is_enabled=1)
        self.db.add(self.archive)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def enqueue(self):
        task = erp_queue.enqueue(self.db, self.archive, None)
        self.db.commit()
        return task

    def test_enqueue_rollback_and_latest(self):
        erp_queue.enqueue(self.db, self.archive, None)
        self.db.rollback()
        self.assertEqual(self.db.query(ErpSyncTask).count(), 0)
        first = self.enqueue()
        second = self.enqueue()
        self.db.refresh(first)
        self.assertEqual(first.status, 'superseded')
        self.assertEqual(second.status, 'queued')

    def test_success_runs_once(self):
        task = self.enqueue()
        def success(db, archive_id, **kwargs):
            self.archive.erp_sync_status = 'success'
            db.commit()
            return {'success': True, 'message': '金蝶已审核'}
        with patch('app.services.kingdee.sync_project_archive_to_erp', side_effect=success) as send:
            erp_queue.run_once(self.db)
            erp_queue.run_once(self.db)
        self.assertEqual(send.call_count, 1)
        self.db.refresh(task)
        self.assertEqual(task.status, 'success')

    def test_two_workers_do_not_send_the_same_task(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = create_engine(f'sqlite:///{folder}/queue.db')
            Base.metadata.create_all(engine)
            with Session(engine) as db:
                archive = PmsProjectArchive(project_code='CONCURRENT', project_name='并发测试', is_enabled=1)
                db.add(archive)
                db.flush()
                erp_queue.enqueue(db, archive, None)
                db.commit()
            entered, release = threading.Event(), threading.Event()
            failures = []
            def send(db, archive_id, **kwargs):
                entered.set()
                self.assertTrue(release.wait(5))
                return {'success': True, 'message': '一次写入'}
            def first_worker():
                try:
                    with Session(engine) as db:
                        erp_queue.run_once(db)
                except BaseException as exc:
                    failures.append(exc)
            with patch('app.services.kingdee.sync_project_archive_to_erp', side_effect=send) as external:
                thread = threading.Thread(target=first_worker)
                thread.start()
                try:
                    self.assertTrue(entered.wait(5))
                    with Session(engine) as db:
                        self.assertFalse(erp_queue.run_once(db))
                finally:
                    release.set()
                    thread.join(5)
                self.assertFalse(thread.is_alive())
                self.assertEqual(failures, [])
                self.assertEqual(external.call_count, 1)
            engine.dispose()

    def test_ambiguous_never_automatically_resends(self):
        task = self.enqueue()
        def ambiguous(db, archive_id, **kwargs):
            self.archive.erp_sync_status = 'pending'
            db.commit()
            return {'success': False, 'message': '结果不确定'}
        with patch('app.services.kingdee.sync_project_archive_to_erp', side_effect=ambiguous) as send:
            erp_queue.run_once(self.db)
            erp_queue.run_once(self.db)
        self.assertEqual(send.call_count, 1)
        self.db.refresh(task)
        self.assertEqual(task.status, 'review')

    def test_only_explicit_retryable_failure_retries(self):
        task = self.enqueue()
        with patch('app.services.kingdee.sync_project_archive_to_erp', return_value={'success': False, 'message': '网络异常', 'retryable': True}):
            erp_queue.run_once(self.db)
        self.db.refresh(task)
        self.assertEqual(task.status, 'queued')
        self.assertGreater(task.next_attempt_at, datetime.now())

    def test_interrupted_task_requires_review(self):
        task = self.enqueue()
        task.status = 'running'
        task.started_at = datetime.now() - timedelta(hours=1)
        self.db.commit()
        with patch('app.services.kingdee.sync_project_archive_to_erp') as send:
            erp_queue.run_once(self.db)
        self.db.refresh(task)
        self.assertEqual(task.status, 'review')
        send.assert_not_called()

    def test_disabled_archive_finishes_without_external_write(self):
        task = self.enqueue()
        self.archive.is_enabled = 0
        self.db.commit()
        with patch('app.services.kingdee.sync_project_archive_to_erp') as send:
            erp_queue.run_once(self.db)
        send.assert_not_called()
        self.db.refresh(self.archive)
        self.assertEqual(task.status, 'failed')
        self.assertEqual(self.archive.erp_sync_status, 'failed')

    def test_retry_stops_after_three_attempts(self):
        task = self.enqueue()
        with patch('app.services.kingdee.sync_project_archive_to_erp', return_value={
            'success': False, 'retryable': True, 'message': '连接失败，未写入'}) as send:
            for attempt in range(3):
                task.next_attempt_at = datetime.now() - timedelta(seconds=1)
                self.db.commit()
                erp_queue.run_once(self.db)
            erp_queue.run_once(self.db)
        self.assertEqual(send.call_count, 3)
        self.assertEqual(task.status, 'failed')

    def test_failed_readback_does_not_unlock_review(self):
        task = self.enqueue()
        task.status = 'review'
        self.archive.erp_sync_status = 'review'
        self.db.commit()
        with patch('app.services.kingdee.KingdeeClient') as client:
            client.return_value.query_assistant_data.side_effect = RuntimeError('duplicate or timeout')
            with self.assertRaises(HTTPException):
                erp_queue.inspect_result(self.db, task.id, None)
        self.assertEqual(task.status, 'review')
        self.assertEqual(self.archive.erp_sync_status, 'review')

    def test_readback_existing_draft_locks_external_identity(self):
        task = self.enqueue()
        task.status = 'review'
        self.archive.erp_sync_status = 'review'
        self.db.commit()
        with patch('app.services.kingdee.KingdeeClient') as client:
            client.return_value.query_assistant_data.return_value = {
                'FEntryID': '42', 'FNumber': 'TEST', 'FDataValue': 'TEST',
                'FDescription': '名称', 'FDocumentStatus': 'A'}
            erp_queue.inspect_result(self.db, task.id, None)
        self.assertEqual(self.archive.erp_synced, 1)
        self.assertEqual(task.status, 'review')

    def test_stale_old_task_does_not_block_latest(self):
        old = self.enqueue()
        old.status = 'running'
        old.started_at = datetime.now() - timedelta(hours=1)
        self.db.commit()
        latest = self.enqueue()
        with patch('app.services.kingdee.sync_project_archive_to_erp', return_value={'success': True, 'message': '完成'}):
            erp_queue.run_once(self.db)
        self.db.refresh(self.archive)
        self.assertEqual(self.archive.erp_sync_status, 'success')
        self.assertEqual(old.status, 'superseded')
        self.assertEqual(latest.status, 'success')

    def test_active_worker_cannot_be_recovered_or_inspected(self):
        from app.services.erp_execution_lock import archive_execution_lock
        task = self.enqueue()
        task.status = 'running'
        task.started_at = datetime.now() - timedelta(hours=1)
        self.db.commit()
        with archive_execution_lock(self.db, self.archive.id) as acquired:
            self.assertTrue(acquired)
            erp_queue.run_once(self.db)
            self.assertEqual(task.status, 'running')
            task.status = 'review'
            self.db.commit()
            with patch('app.services.kingdee.KingdeeClient') as client:
                with self.assertRaises(HTTPException) as result:
                    erp_queue.inspect_result(self.db, task.id, None, external_request_finished=True)
                self.assertEqual(result.exception.status_code, 409)
                client.assert_not_called()

    def test_retry_after_explicit_external_completion_confirmation(self):
        task = self.enqueue()
        task.status = 'review'
        self.archive.erp_sync_status = 'review'
        self.db.commit()
        with patch('app.services.kingdee.KingdeeClient') as client:
            client.return_value.query_assistant_data.return_value = None
            erp_queue.inspect_result(self.db, task.id, None)
            self.assertEqual(task.status, 'review')
            erp_queue.inspect_result(self.db, task.id, None, external_request_finished=True)
        self.assertEqual(task.status, 'failed')
        self.assertEqual(self.db.get(ErpSyncTask, erp_queue.retry(self.db, task.id, None)['id']).status, 'queued')

    def test_file_execution_lock_is_shared_across_connections(self):
        from app.services.erp_execution_lock import archive_execution_lock
        with tempfile.TemporaryDirectory() as folder:
            first = create_engine(f'sqlite:///{folder}/shared.db')
            second = create_engine(f'sqlite:///{folder}/shared.db')
            with Session(first) as db1, Session(second) as db2:
                with archive_execution_lock(db1, 1) as owned:
                    self.assertTrue(owned)
                    with archive_execution_lock(db2, 1) as concurrent:
                        self.assertFalse(concurrent)
                with archive_execution_lock(db2, 1) as released:
                    self.assertTrue(released)
            first.dispose()
            second.dispose()

    def test_business_failure_no_retry_and_admin_retry_audited(self):
        task = self.enqueue()
        with patch('app.services.kingdee.sync_project_archive_to_erp', return_value={'success': False, 'message': '没有金蝶审核权限'}):
            erp_queue.run_once(self.db)
        self.db.refresh(task)
        self.assertEqual(task.status, 'failed')
        new = erp_queue.retry(self.db, task.id, None)
        self.assertNotEqual(new['id'], task.id)
        self.assertEqual(self.db.get(ErpSyncTask, new['id']).status, 'queued')
        from app.models.operation_log import SysOperationLog
        self.assertEqual(self.db.query(SysOperationLog).filter_by(action='retry').count(), 1)

    def test_review_cannot_retry_until_readback(self):
        task = self.enqueue()
        task.status = 'review'
        self.archive.erp_sync_status = 'review'
        self.db.commit()
        with self.assertRaises(HTTPException):
            erp_queue.retry(self.db, task.id, None)
        self.db.rollback()
        with patch('app.services.kingdee.KingdeeClient') as client:
            client.return_value.query_assistant_data.return_value = {
                'FNumber': 'TEST', 'FDataValue': 'TEST', 'FDescription': '名称', 'FDocumentStatus': 'C'}
            result = erp_queue.inspect_result(self.db, task.id, None)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(self.archive.erp_synced, 1)

    def test_filters_pagination_and_scope(self):
        self.enqueue()
        self.assertEqual(erp_queue.list_tasks(self.db, keyword='TEST')['total'], 1)
        self.assertEqual(erp_queue.list_tasks(self.db, keyword='missing')['total'], 0)
        self.assertEqual(erp_queue.list_tasks(self.db, page=2, page_size=1)['items'], [])
        self.assertEqual(erp_queue.list_tasks(self.db, scope_context={'data_scope': 1, 'user_id': 999})['total'], 0)

    def test_code_locked_for_initial_and_synced(self):
        from app.services.project import update_archive
        from app.schemas.project import ArchiveUpdate
        for values in ({'erp_synced': 1}, {'erp_synced': 0, 'data_origin': 'kingdee_initial'}):
            for key, value in values.items():
                setattr(self.archive, key, value)
            self.db.commit()
            with self.assertRaises(HTTPException) as ctx:
                update_archive(self.db, self.archive.id, ArchiveUpdate(project_code='CHANGED'), 1)
            self.assertEqual(ctx.exception.detail['code'], 'ARCHIVE_CODE_LOCKED')

    def test_mssql_table_compiles_and_menu_revocation_survives(self):
        from sqlalchemy.schema import CreateTable
        from sqlalchemy.dialects import mssql
        self.assertIn('NVARCHAR(max)', str(CreateTable(ErpSyncTask.__table__).compile(dialect=mssql.dialect())))
        from app.models.rbac import SysRole, SysRoleMenu
        from app.services.erp_queue_migration import initialize_sync_management
        self.db.add(SysRole(role_name='管理员', role_code='admin', data_scope=4, status=1))
        self.db.commit()
        initialize_sync_management(self.db)
        self.assertEqual(self.db.query(SysRoleMenu).count(), 3)
        self.db.query(SysRoleMenu).delete()
        self.db.commit()
        initialize_sync_management(self.db)
        self.assertEqual(self.db.query(SysRoleMenu).count(), 0)

    def test_save_and_queue_same_transaction(self):
        from app.services.project import create_archive, update_archive
        from app.schemas.project import ArchiveCreate, ArchiveUpdate
        from app.services.enum_registry import initialize_enum_definitions
        initialize_enum_definitions(self.db)
        self.db.commit()
        result = create_archive(self.db, ArchiveCreate(project_code='NEW', project_name='新项目'), 1)
        self.assertEqual(self.db.query(ErpSyncTask).filter_by(archive_id=result['id']).count(), 1)
        update_archive(self.db, result['id'], ArchiveUpdate(project_name='新名称'), 1)
        tasks = self.db.query(ErpSyncTask).filter_by(archive_id=result['id']).order_by(ErpSyncTask.id).all()
        self.assertEqual([task.status for task in tasks], ['superseded', 'queued'])
        with patch('app.services.erp_queue.enqueue', side_effect=RuntimeError('queue failed')):
            with self.assertRaises(RuntimeError):
                update_archive(self.db, result['id'], ArchiveUpdate(project_name='不能提交'), 1)
        self.assertEqual(self.db.get(PmsProjectArchive, result['id']).project_name, '新名称')

    def test_old_completion_cannot_overwrite_new_queue_status(self):
        task = self.enqueue()
        def completed_then_saved(db, archive_id, **kwargs):
            self.archive.erp_sync_status = 'success'
            db.commit()
            erp_queue.enqueue(db, self.archive, None)
            db.commit()
            return {'success': True, 'message': '已审核'}
        with patch('app.services.kingdee.sync_project_archive_to_erp', side_effect=completed_then_saved):
            erp_queue.run_once(self.db)
        self.db.refresh(self.archive)
        self.assertEqual(self.archive.erp_sync_status, 'queued')
        self.db.refresh(task)
        self.assertEqual(task.status, 'success')

    def test_api_permission_separation_and_scope(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.sync_tasks import router
        from app.core.database import get_db
        from app.services.authorization import get_current_user_context
        app = FastAPI()
        app.include_router(router)
        ctx = {'user_id': 1, 'data_scope': 4, 'permissions': ['project:archive:view']}
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user_context] = lambda: ctx
        task = self.enqueue()
        client = TestClient(app)
        self.assertEqual(client.get('/api/sync-tasks').status_code, 403)
        self.assertEqual(client.get(f'/api/sync-tasks/archive/{self.archive.id}').status_code, 200)
        self.assertEqual(client.post('/api/sync-tasks/retry', json={'task_ids': [task.id]}).status_code, 403)
        ctx['data_scope'] = 1
        self.assertEqual(client.get(f'/api/sync-tasks/archive/{self.archive.id}').status_code, 404)
        ctx.update(data_scope=4, permissions=['system:sync:view'])
        self.assertEqual(client.get('/api/sync-tasks').status_code, 200)
        self.assertEqual(client.post(f'/api/sync-tasks/{task.id}/inspect').status_code, 403)
        ctx['permissions'].append('system:sync:retry')
        self.assertEqual(client.post(f'/api/sync-tasks/{task.id}/inspect').status_code, 409)

if __name__ == '__main__':
    unittest.main()
