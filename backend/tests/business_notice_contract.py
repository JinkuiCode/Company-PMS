"""Approval notices use disposable fixtures, live RBAC and no external mail."""
import unittest
from unittest.mock import patch
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
import archive_change_contract as fixture
from app.models.business_notice import BusinessNotice, BusinessNoticeMail
from app.services import business_notices as notices
from app.models.rbac import SysRole, SysMenu, SysUserRole, SysRoleMenu
from app.models.product_line import SysRoleProductLine
from app.models.operation_log import SysOperationLog

class Notices(unittest.TestCase):
    actor = fixture.ArchiveChangeContract.actor
    snapshot = fixture.ArchiveChangeContract.snapshot
    payload = fixture.ArchiveChangeContract.payload
    submit = fixture.ArchiveChangeContract.submit
    tearDown = fixture.ArchiveChangeContract.tearDown

    def setUp(self):
        fixture.ArchiveChangeContract.setUp(self)
        from app.api.business_notices import router
        self.client.app.include_router(router)
        self.roles = {}
        for user in (self.owner, self.head, self.other):
            role = SysRole(role_name='通知夹具', role_code=f'notice-{user.id}', data_scope=4)
            self.db.add(role); self.db.flush(); self.roles[user.id] = role
            self.db.add(SysUserRole(user_id=user.id, role_id=role.id))
            self.db.add(SysRoleProductLine(role_id=role.id, product_line_id=1))
            for code in ('project:archive:view', 'project:archive:edit'):
                node = self.db.query(SysMenu).filter_by(permission_code=code).first()
                if not node:
                    node = SysMenu(menu_name=code, menu_type='B', permission_code=code)
                    self.db.add(node); self.db.flush()
                self.db.add(SysRoleMenu(role_id=role.id, menu_id=node.id))
        self.db.commit()

    def mine(self, user=None, **kwargs):
        return notices.list_notices(self.db, {'user_id': (user or self.head).id}, **kwargs)

    def decide(self, result, decision='approve'):
        self.actor(self.head)
        response = self.client.post(f"/api/projects/archive-changes/requests/{result['id']}/decide",
            json={'decision':decision, 'expected_version':result['version'], 'opinion':'业务意见，不进入邮件'})
        self.assertEqual(response.status_code,200,response.text)
        return response

    def test_submission_replay_is_one_personal_event_and_mail(self):
        data = self.payload(project_name='待批')
        url = f'/api/projects/archive-changes/{self.archive.id}/submit'
        first = self.client.post(url,json=data); second=self.client.post(url,json=data)
        self.assertEqual(first.status_code,200); self.assertEqual(second.json()['id'],first.json()['id'])
        row=self.db.query(BusinessNotice).one()
        self.assertEqual((row.user_id,row.event,row.request_version),(self.head.id,'submitted',1))
        self.assertEqual(self.db.query(BusinessNoticeMail).one().notice_id,row.id)
        self.assertEqual(self.mine()['unread'],1)
        self.assertEqual(self.mine(self.owner)['total'],0)

    def test_result_and_repeated_decision_only_notify_original_author_once(self):
        result=self.submit(project_name='新名称'); self.decide(result); self.decide(result)
        self.assertEqual(self.db.query(BusinessNotice).count(),2)
        self.assertEqual(self.db.query(BusinessNoticeMail).count(),2)
        item=self.mine(self.owner)['items'][0]
        self.assertEqual((item['event'],item['status']),( 'approved',3))
        self.assertNotIn('differences',item)
        self.assertEqual(self.mine()['items'][0]['status'],3)

    def test_rejection_result_and_withdrawal_have_distinct_events(self):
        result=self.submit(customer='待退回');self.decide(result,'reject')
        self.assertEqual(self.mine(self.owner)['items'][0]['event'],'rejected')
        self.actor(self.owner);second=self.submit(customer='待撤回')
        response=self.client.post(f"/api/projects/archive-changes/requests/{second['id']}/withdraw",json={'expected_version':1})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.db.query(BusinessNotice).count(),3)
        self.assertEqual(self.mine()['items'][0]['status'],5)

    def test_queue_failure_rolls_back_entire_submission(self):
        original=notices.queue_archive_notice
        def fail(*args,**kwargs):
            original(*args,**kwargs);raise RuntimeError('notice insert failed')
        with patch.object(notices,'queue_archive_notice',side_effect=fail):
            with self.assertRaisesRegex(RuntimeError,'notice insert failed'):self.submit(customer='不可保存')
        self.assertEqual(self.db.query(self.Change).count(),0)
        self.assertEqual(self.db.query(BusinessNotice).count(),0)
        self.assertEqual(self.db.query(BusinessNoticeMail).count(),0)
        self.assertEqual(self.db.query(SysOperationLog).filter_by(action='submit').count(),0)

    def test_queue_failure_rolls_back_approval_and_erp_queue(self):
        result=self.submit(project_name='不可生效')
        with patch.object(notices,'queue_archive_notice',side_effect=RuntimeError('mail queue failed')):
            with self.assertRaisesRegex(RuntimeError,'mail queue failed'):self.decide(result)
        self.db.refresh(self.archive)
        self.assertEqual(self.archive.project_name,'正式名称')
        self.assertEqual(self.db.get(self.Change,result['id']).status,2)
        self.assertEqual(self.db.query(fixture.ErpSyncTask).count(),0)
        self.assertEqual(self.db.query(BusinessNotice).count(),1)

    def test_direct_save_does_not_create_notices(self):
        fixture.ArchiveChangeContract.test_department_head_direct_save_and_other_actor_forbidden(self)
        self.assertEqual(self.db.query(BusinessNotice).count(),0)

    def test_maintenance_does_not_create_notices(self):
        self.actor(self.other,permissions=['project:archive:view','project:archive:edit','project:archive:maintain'])
        response=self.client.put(f'/api/projects/archives/{self.archive.id}/maintenance',json={
            'updates':{'customer':'维护修正'},'expected_version':self.snapshot()['change_version'],'reason':'核对历史资料'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.db.query(BusinessNotice).count(),0)
        self.assertEqual(self.db.query(BusinessNoticeMail).count(),0)

    def test_personal_routes_validate_bounds_and_live_access(self):
        self.submit(customer='待审批');self.actor(self.head)
        response=self.client.get('/api/business-notices');self.assertEqual(response.status_code,200,response.text)
        row=response.json()['items'][0]
        self.assertEqual(self.client.get('/api/business-notices',params={'page_size':501}).status_code,422)
        self.assertEqual(self.client.get(f"/api/business-notices/{row['id']}").status_code,200)
        self.assertEqual(self.client.get(f"/api/projects/archive-changes/requests/{row['change_id']}").status_code,200)
        self.assertEqual(self.client.post(f"/api/business-notices/{row['id']}/read").status_code,200)
        self.roles[self.head.id].status=0;self.db.commit()
        self.assertEqual(self.client.get('/api/business-notices').status_code,403)

    def test_concurrent_decisions_commit_one_result_notice(self):
        import tempfile,sqlite3,threading
        from pathlib import Path
        from concurrent.futures import ThreadPoolExecutor
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.schemas.archive_change import ArchiveChangeDecision
        from app.services.archive_change import decide_archive_change
        result=self.submit(customer='并发通过');self.actor(self.head);scope=dict(self.ctx)
        self.db.commit()
        with tempfile.TemporaryDirectory() as folder:
            filename=Path(folder)/'decide.db'
            with sqlite3.connect(filename) as target:self.db.connection().connection.driver_connection.backup(target)
            engine=create_engine(f'sqlite:///{filename}',connect_args={'check_same_thread':False,'timeout':10})
            barrier=threading.Barrier(2)
            def decide():
                with Session(engine) as db:
                    barrier.wait(timeout=5)
                    return decide_archive_change(db,result['id'],ArchiveChangeDecision(decision='approve',expected_version=1,opinion='核对'),scope['user_id'],scope_context=scope)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(decide) for _ in range(2)]
                for future in futures:self.assertEqual(future.result(timeout=15)['status'],3)
            with Session(engine) as db:
                self.assertEqual(db.query(BusinessNotice).count(),2)
                self.assertEqual(db.query(BusinessNoticeMail).count(),2)
            engine.dispose()

    def test_read_is_explicit_personal_and_logged_once(self):
        self.submit(customer='待批');row=self.db.query(BusinessNotice).one()
        with self.assertRaises(HTTPException):notices.mark_read(self.db,{'user_id':self.other.id},row.id)
        self.assertIsNone(row.read_at)
        notices.mark_read(self.db,{'user_id':self.head.id},row.id)
        first=row.read_at
        notices.mark_read(self.db,{'user_id':self.head.id},row.id)
        self.assertEqual(row.read_at,first)
        self.assertEqual(self.mine()['unread'],0)
        self.assertEqual(self.mine(unread_only=True)['total'],0)
        self.assertEqual(self.db.query(SysOperationLog).filter_by(entity_type='pms_business_notice',action='read').count(),1)

    def test_live_permission_revocation_overrides_stale_caller_context(self):
        self.submit(customer='待批')
        node=self.db.query(SysMenu).filter_by(permission_code='project:archive:view').one()
        self.db.query(SysRoleMenu).filter_by(role_id=self.roles[self.head.id].id,menu_id=node.id).delete();self.db.commit()
        with self.assertRaises(HTTPException):self.mine()
        self.head.status=0;self.db.commit()
        with self.assertRaises(HTTPException):self.mine()

    def test_product_line_and_personnel_scope_filter_counts_details_and_reads(self):
        self.submit(customer='待批');nid=self.db.query(BusinessNotice).one().id
        self.db.query(SysRoleProductLine).filter_by(role_id=self.roles[self.head.id].id).delete();self.db.commit()
        self.assertEqual(self.mine()['total'],0)
        with self.assertRaises(HTTPException):notices.get_notice(self.db,{'user_id':self.head.id},nid)
        with self.assertRaises(HTTPException):notices.mark_read(self.db,{'user_id':self.head.id},nid)
        self.db.add(SysRoleProductLine(role_id=self.roles[self.head.id].id,product_line_id=1))
        self.roles[self.head.id].data_scope=1;self.db.commit()
        self.assertEqual(self.mine()['total'],0)

    def test_head_change_hides_original_todo_and_never_forwards(self):
        result=self.submit(customer='待批');self.dept.leader_id=self.other.id;self.db.commit()
        self.assertEqual(self.mine()['total'],0);self.assertEqual(self.mine(self.other)['total'],0)
        self.actor(self.head)
        self.assertEqual(self.client.get(f"/api/projects/archive-changes/requests/{result['id']}").status_code,404)
        self.actor(self.owner)
        self.assertEqual(self.client.get(f"/api/projects/archive-changes/requests/{result['id']}").status_code,200)

    def test_exact_request_rejects_unrelated_user_and_revoked_view(self):
        result=self.submit(customer='待批');self.actor(self.other)
        url=f"/api/projects/archive-changes/requests/{result['id']}"
        self.assertEqual(self.client.get(url).status_code,404)
        self.actor(self.head);self.assertEqual(self.client.get(url).status_code,200)
        self.roles[self.head.id].status=0;self.db.commit()
        self.assertEqual(self.client.get(url).status_code,403)

    def test_database_unique_event_prevents_duplicate_even_outside_api(self):
        self.submit(customer='待批');row=self.db.query(BusinessNotice).one()
        self.db.add(BusinessNotice(change_id=row.change_id,event=row.event,request_version=row.request_version,user_id=row.user_id))
        with self.assertRaises(IntegrityError):self.db.flush()
        self.db.rollback();self.assertEqual(self.db.query(BusinessNotice).count(),1)

if __name__=='__main__':unittest.main()
