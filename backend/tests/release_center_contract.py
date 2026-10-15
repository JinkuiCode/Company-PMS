"""Release publication and personal notices, isolated data and transport only."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import archive_change_contract as fixture
from fastapi import HTTPException
from app.services import releases
from app.models.release import PmsRelease, PmsReleaseNotice, PmsReleaseMail
from app.services.database_revision import CURRENT_DATABASE_REVISION


class Releases(unittest.TestCase):
    actor = fixture.ArchiveChangeContract.actor
    tearDown = fixture.ArchiveChangeContract.tearDown

    def setUp(self):
        fixture.ArchiveChangeContract.setUp(self)
        from app.models.rbac import SysRole, SysMenu, SysUserRole, SysRoleMenu
        from app.models.database_revision import PmsDatabaseRevision
        role = SysRole(role_name='发布测试', role_code='fixture-publisher')
        node = SysMenu(menu_name='发布', menu_type='B', permission_code='system:release:publish')
        self.db.add_all([role, node]); self.db.flush()
        self.db.add_all([SysUserRole(user_id=self.owner.id, role_id=role.id), SysRoleMenu(role_id=role.id, menu_id=node.id),
            PmsDatabaseRevision(id=1, revision=CURRENT_DATABASE_REVISION)])
        self.db.commit()
        self.context = {'user_id': self.owner.id, 'permissions': ['system:release:publish']}
        self.manifest = {'version': 'v1.0.0', 'title': '统一治理', 'summary': '记录修改并了解更新',
            'build_id': 'fixture-build', 'commit': 'a'*40, 'database_revision': CURRENT_DATABASE_REVISION,
            'built_at': '2026-10-15T00:00:00Z', 'changes': [{'kind': '新增', 'title': '单据日志', 'description': '查看字段变化', 'guide': 'archive'}]}
        self.receipt = {'manifest_sha256': releases.manifest_digest(self.manifest), 'accepted': True,
            'validated_at': '2026-10-15T01:00:00Z'}
        self.runtime_patch = patch.object(releases, 'load_runtime_manifest', side_effect=lambda: self.manifest)
        self.runtime_patch.start(); self.addCleanup(self.runtime_patch.stop)

    def publish(self):
        return releases.publish_release(self.db, self.context, self.manifest, self.receipt)

    def test_publication_is_idempotent_and_each_enabled_user_has_one_notice_and_mail(self):
        result = self.publish(); self.publish()
        self.assertEqual(self.db.query(PmsRelease).count(), 1)
        from app.models.user import SysUser
        count = self.db.query(SysUser).filter_by(status=1).count()
        self.assertEqual(self.db.query(PmsReleaseNotice).count(), count)
        self.assertEqual(self.db.query(PmsReleaseMail).count(), count)
        self.assertEqual(result.version, 'v1.0.0')

    def test_publication_needs_explicit_permission_and_matching_successful_acceptance(self):
        self.context['permissions'] = []
        with self.assertRaises(HTTPException): self.publish()
        self.context['permissions'] = ['system:release:publish']
        self.receipt['manifest_sha256'] = 'b'*64
        with self.assertRaises(HTTPException): self.publish()
        self.assertEqual(self.db.query(PmsRelease).count(), 0)

    def test_notice_read_is_personal_explicit_and_idempotent(self):
        self.publish()
        mine = releases.list_notices(self.db, {'user_id': self.owner.id})
        other = self.db.query(PmsReleaseNotice).filter_by(user_id=self.other.id).one()
        self.assertIsNone(mine['items'][0]['read_at'])
        with self.assertRaises(HTTPException): releases.mark_read(self.db, {'user_id': self.owner.id}, other.id)
        notice_id = mine['items'][0]['id']
        releases.mark_read(self.db, {'user_id': self.owner.id}, notice_id)
        first = self.db.get(PmsReleaseNotice, notice_id).read_at
        releases.mark_read(self.db, {'user_id': self.owner.id}, notice_id)
        self.assertEqual(self.db.get(PmsReleaseNotice, notice_id).read_at, first)
        self.assertIsNone(other.read_at)

    def test_initial_and_following_versions_obey_semver_sequence(self):
        self.manifest['version'] = 'v2.0.0'; self.receipt['manifest_sha256'] = releases.manifest_digest(self.manifest)
        with self.assertRaises(HTTPException): self.publish()
        self.manifest['version'] = 'v1.0.0'; self.receipt['manifest_sha256'] = releases.manifest_digest(self.manifest); self.publish()
        self.manifest['version'] = 'v1.0.1'; self.manifest['build_id'] = 'fixture-fix'
        self.receipt['manifest_sha256'] = releases.manifest_digest(self.manifest)
        self.publish()
        self.assertEqual(self.db.query(PmsRelease).count(), 2)

    def test_failed_transaction_leaves_no_partial_audience(self):
        with patch.object(releases, 'record_operation_log', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError): self.publish()
        self.db.rollback()
        self.assertEqual(self.db.query(PmsRelease).count(), 0)
        self.assertEqual(self.db.query(PmsReleaseNotice).count(), 0)

    def test_live_revoke_is_enforced_even_with_stale_context(self):
        from app.models.rbac import SysRoleMenu
        self.db.query(SysRoleMenu).delete(); self.db.commit()
        with self.assertRaises(HTTPException): self.publish()

    def test_changed_content_cannot_overwrite_published_version(self):
        self.publish()
        self.manifest['summary'] = 'different content'
        self.receipt['manifest_sha256'] = releases.manifest_digest(self.manifest)
        with self.assertRaises(HTTPException): self.publish()
        self.assertEqual(self.db.query(PmsRelease).one().summary, '记录修改并了解更新')

    def test_self_consistent_receipt_for_another_deployment_is_rejected(self):
        with patch.object(releases, 'load_runtime_manifest', return_value={**self.manifest, 'build_id': 'another-build'}):
            with self.assertRaises(HTTPException): self.publish()
        self.assertEqual(self.db.query(PmsRelease).count(), 0)

    def test_user_with_notice_history_has_clear_delete_restriction(self):
        from app.services.rbac import delete_user
        from app.models.user import SysUser
        self.publish()
        with self.assertRaises(HTTPException) as caught:
            delete_user(self.db, self.other.id, self.owner.id)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn('停用', str(caught.exception.detail))
        self.assertIsNotNone(self.db.get(SysUser, self.other.id))

    def test_simultaneous_same_release_returns_the_same_publication(self):
        import sqlite3, tempfile, threading
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import Session
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'concurrent.db'
            with self.engine.connect() as connection, sqlite3.connect(path) as target:
                connection.connection.driver_connection.backup(target)
            engine = create_engine('sqlite:///' + str(path), connect_args={'timeout': 15, 'check_same_thread': False})
            gate = threading.Barrier(2); ids = []; errors = []
            def before_flush(db, *args):
                if any(isinstance(row, PmsRelease) for row in db.new): gate.wait(10)
            def worker():
                try:
                    with Session(engine) as db: ids.append(releases.publish_release(db, self.context, self.manifest, self.receipt).id)
                except Exception as error: errors.append(error)
            event.listen(Session, 'before_flush', before_flush)
            try:
                threads = [threading.Thread(target=worker) for _ in range(2)]
                for thread in threads: thread.start()
                for thread in threads: thread.join(20)
                self.assertFalse(any(thread.is_alive() for thread in threads))
                self.assertEqual(errors, []); self.assertEqual(len(ids), 2); self.assertEqual(ids[0], ids[1])
                with Session(engine) as db:
                    self.assertEqual(db.query(PmsRelease).count(), 1)
                    self.assertEqual(db.query(PmsReleaseNotice).count(), 3)
            finally:
                event.remove(Session, 'before_flush', before_flush); engine.dispose()

    def test_actual_api_uses_session_identity_and_live_manage_grants(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.releases import router
        from app.core.database import get_db
        from app.core.security import user_access_token
        from app.models.rbac import SysMenu, SysRoleMenu, SysUserRole
        from app.services import runtime_release
        release = self.publish()
        app = FastAPI(); app.include_router(router); app.dependency_overrides[get_db] = lambda: self.db
        headers = {'Authorization': 'Bearer ' + user_access_token(self.owner, 'oa')}
        other_headers = {'Authorization': 'Bearer ' + user_access_token(self.other, 'oa')}
        with patch.object(runtime_release, 'load_runtime_manifest', return_value=self.manifest), TestClient(app) as client:
            notices = client.get('/api/releases/notices', headers=headers)
            self.assertEqual(notices.status_code, 200, notices.text)
            self.assertEqual(notices.json()['total'], 1)
            other_id = self.db.query(PmsReleaseNotice).filter_by(user_id=self.other.id).one().id
            self.assertEqual(client.post(f'/api/releases/notices/{other_id}/read', headers=headers).status_code, 404)
            self.assertEqual(client.post('/api/releases/publish', headers=other_headers, json=self.receipt).status_code, 403)
            path = f'/api/releases/{release.id}/deliveries'
            self.assertEqual(client.get(path, headers=headers).status_code, 403)
            self.assertNotIn('technical', client.get('/api/releases/runtime', headers=headers).json())
            role_id = self.db.query(SysUserRole).filter_by(user_id=self.owner.id).one().role_id
            node = SysMenu(menu_name='管理投递', menu_type='B', permission_code='system:release:manage')
            self.db.add(node); self.db.flush(); grant = SysRoleMenu(role_id=role_id, menu_id=node.id)
            self.db.add(grant); self.db.commit()
            self.assertEqual(client.get(path, headers=headers).status_code, 200)
            self.assertIn('technical', client.get('/api/releases/runtime', headers=headers).json())
            self.db.delete(grant); self.db.commit()
            self.assertEqual(client.get(path, headers=headers).status_code, 403)
            self.assertNotIn('technical', client.get('/api/releases/runtime', headers=headers).json())


if __name__ == '__main__': unittest.main()
