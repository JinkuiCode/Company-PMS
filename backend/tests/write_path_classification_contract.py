"""Targeted isolated checks for routes requiring manual log-path classification.

Direct handler checks do not substitute for runtime RBAC acceptance.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fastapi import HTTPException
from sqlalchemy import event
import offline_archive_import_contract as import_fixture
import feedback_service_contract as feedback_fixture
from app.api import erp
from app.models.operation_log import SysOperationLog


class WritePathClassificationContract(unittest.TestCase):
    def test_every_non_auth_namespace_write_route_rejects_unauthenticated_requests(self):
        import re
        from fastapi.testclient import TestClient
        from main import app
        from app.core.database import Base, engine
        # The isolated runner pins this engine to a new temporary SQLite file.
        Base.metadata.create_all(engine)
        client=TestClient(app,raise_server_exceptions=False)
        checked=0
        for route in app.routes:
            path=getattr(route,'path','')
            if not path.startswith('/api/') or path.startswith(('/api/auth/','/api/sso/')):continue
            actual=re.sub(r'\{[^}]+\}',lambda m:'00000000-0000-4000-8000-000000000001' if 'draft_id' in m.group() else '1',path)
            for method in sorted(getattr(route,'methods',set()) & {'POST','PUT','PATCH','DELETE'}):
                with self.subTest(method=method,path=path):
                    response=client.request(method,actual,json={})
                    # Existing HTTPBearer rejects an absent header before the
                    # application's invalid-token (401) branch is entered.
                    self.assertEqual(response.status_code,403)
                    self.assertEqual(response.json(),{'detail':'Not authenticated'})
                    checked+=1
        self.assertEqual(checked,69,'new write endpoints require re-auditing the inventory')
        client.close()

    def test_disabled_independent_sync_never_calls_erp(self):
        with patch.object(erp.kingdee,'test_erp_connection',side_effect=AssertionError('external ERP forbidden')):
            for call,data in [(erp.sync_project_archive,erp.SyncRequest(archive_id=1)),(erp.batch_sync_project_archives,erp.BatchSyncRequest(archive_ids=[1]))]:
                with self.subTest(handler=call.__name__), self.assertRaises(HTTPException) as caught:
                    call(data,request=None,db=None,scope_ctx={'user_id':1})
                self.assertEqual(caught.exception.status_code,409)

    def test_import_preview_executes_no_database_mutation(self):
        fixture=import_fixture.ImportContract();fixture.setUp();statements=[]
        def capture(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
        try:
            event.listen(fixture.e,'before_cursor_execute',capture)
            from app.services.offline_archive_import import preview_import
            result=preview_import(fixture.db,fixture.payload,fixture.scope)
            self.assertEqual(result['total'],2)
            self.assertTrue(statements)
            forbidden=('INSERT','UPDATE','DELETE','CREATE','ALTER','DROP','REPLACE')
            self.assertFalse([s for s in statements if s.lstrip().upper().startswith(forbidden)])
            self.assertFalse(fixture.db.new or fixture.db.dirty or fixture.db.deleted)
        finally:
            event.remove(fixture.e,'before_cursor_execute',capture);fixture.tearDown()

    def test_attachment_success_records_private_safe_business_log(self):
        import tempfile
        from app.services import feedback_attachments
        fixture=feedback_fixture.FeedbackServiceContract();fixture.setUp()
        try:
            row=fixture.create();before=fixture.db.query(SysOperationLog).count()
            with tempfile.TemporaryDirectory() as directory,patch.object(feedback_attachments,'storage_root',return_value=Path(directory)):
                attached=feedback_attachments.attach(fixture.db,fixture.owner,row['id'],1,'fixture.pdf',b'%PDF-1.7\nfixture')
                logs=fixture.db.query(SysOperationLog).filter_by(entity_type='pms_feedback_attachment',entity_id=str(attached['id'])).all()
                self.assertEqual(len(logs),1)
                self.assertEqual(logs[0].action,'create')
                self.assertEqual(fixture.db.query(SysOperationLog).count(),before+1)
                self.assertNotIn('storage_name',str(logs[0].after_data))
        finally:fixture.tearDown()

if __name__=='__main__':unittest.main()
