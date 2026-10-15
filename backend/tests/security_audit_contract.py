"""Failure audit is independent, payload-free and bounded against flooding."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import archive_change_contract as fixture
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request
from app.models.operation_log import SysOperationLog
from app.services import security_audit


class SecurityAudit(unittest.TestCase):
    actor = fixture.ArchiveChangeContract.actor
    tearDown = fixture.ArchiveChangeContract.tearDown

    def setUp(self):
        fixture.ArchiveChangeContract.setUp(self)
        security_audit.reset_limiter_for_tests()
        self.factory = sessionmaker(bind=self.db.get_bind())
        self.request = Request({'type': 'http', 'method': 'PUT', 'path': '/api/projects/archives/1',
            'headers': [], 'client': ('127.0.0.1', 1), 'server': ('fixture', 80), 'scheme': 'http',
            'query_string': b'token=never-store-this'})
        self.request.state.audit_actor_id = self.owner.id

    def test_failed_business_transaction_still_has_independent_audit(self):
        original = self.archive.project_name
        self.archive.project_name = 'must roll back'
        self.db.rollback()
        security_audit.record_request_failure(self.request, 403, session_factory=self.factory)
        self.assertEqual(self.db.get(type(self.archive), self.archive.id).project_name, original)
        row = self.db.query(SysOperationLog).one()
        self.assertEqual(row.action, 'denied')
        self.assertEqual(row.operator_id, self.owner.id)
        self.assertIsNone(row.before_data)
        self.assertNotIn('never-store-this', row.request_path)

    def test_duplicate_denials_are_rate_limited_and_limiter_is_bounded(self):
        for _ in range(20):
            security_audit.record_request_failure(self.request, 403, session_factory=self.factory)
        self.assertEqual(self.db.query(SysOperationLog).count(), 1)
        self.assertLessEqual(security_audit.limiter_size(), security_audit.MAX_BUCKETS)

    def test_read_validation_failures_are_not_business_write_events(self):
        self.request.scope['method'] = 'GET'
        security_audit.record_request_failure(self.request, 422, session_factory=self.factory)
        self.assertEqual(self.db.query(SysOperationLog).count(), 0)

    def test_varying_probe_paths_cannot_bypass_source_budget(self):
        from types import SimpleNamespace
        for index in range(100):
            probe = Request({**self.request.scope, 'path': f'/api/resource-{index}/1',
                'route': SimpleNamespace(path=f'/api/resource-{index}/{{id}}'), 'state': {'audit_actor_id': self.owner.id}})
            security_audit.record_request_failure(probe, 404, session_factory=self.factory)
        self.assertEqual(self.db.query(SysOperationLog).count(), security_audit.MAX_EVENTS_PER_SOURCE)

    def test_unknown_paths_share_a_fixed_key_and_never_persist_path_contents(self):
        for index in range(20):
            probe = Request({**self.request.scope, 'path': f'/api/unmatched/private-value-{index}', 'state': {}})
            security_audit.record_request_failure(probe, 404, session_factory=self.factory)
        rows = self.db.query(SysOperationLog).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].request_path, '[未匹配路由]')

    def test_concealed_out_of_scope_get_is_audited_without_entity_contents(self):
        self.request.scope['method'] = 'GET'
        security_audit.record_request_failure(self.request, 404, session_factory=self.factory)
        row = self.db.query(SysOperationLog).one()
        self.assertEqual(row.entity_type, 'security_request')
        self.assertNotIn('project_name', row.after_data)

    def test_no_false_success_if_audit_storage_is_unavailable(self):
        with patch.object(security_audit, 'record_operation_log', side_effect=RuntimeError('storage unavailable')):
            self.assertFalse(security_audit.record_request_failure(self.request, 409, session_factory=self.factory))
        self.assertEqual(self.db.query(SysOperationLog).count(), 0)

    def test_real_exception_handler_audits_after_business_dependency_rollback(self):
        from fastapi import FastAPI, Depends, HTTPException, Request
        from fastapi.testclient import TestClient
        from sqlalchemy.orm import Session
        from starlette.exceptions import HTTPException as StarletteHTTPException
        from app.core.database import get_db
        from app.core.security import user_access_token
        from app.services.authorization import get_current_user_context
        from main import audited_http_error
        original = self.archive.customer
        app = FastAPI(exception_handlers={StarletteHTTPException: audited_http_error})
        def session():
            try: yield self.db
            finally: self.db.rollback()
        app.dependency_overrides[get_db] = session
        @app.put('/api/security-fixture')
        def rejected(request: Request, db: Session=Depends(get_db), context=Depends(get_current_user_context)):
            self.archive.customer = 'rolled back'
            db.flush()
            raise HTTPException(403, '隔离拒绝')
        with patch('app.core.database.SessionLocal', self.factory), TestClient(app) as client:
            response = client.put('/api/security-fixture', headers={'Authorization': 'Bearer '+user_access_token(self.owner, 'oa')})
        self.assertEqual(response.status_code, 403)
        self.db.refresh(self.archive)
        self.assertEqual(self.archive.customer, original)
        row = self.db.query(SysOperationLog).one()
        self.assertEqual(row.operator_id, self.owner.id)
        self.assertEqual(row.request_path, '/api/security-fixture')


if __name__ == '__main__': unittest.main()
