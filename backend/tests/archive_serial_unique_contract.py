"""Global serial reservations through real application services, disposable DB only."""
import json
import unittest
from uuid import uuid4
from unittest.mock import patch
from fastapi import HTTPException
from form_draft_contract import Drafts
from app.models.project import PmsProjectArchive
from app.models.operation_log import SysOperationLog


class Serials(Drafts):
    def post_serial(self, code, serial, *, draft_id=None, version=None):
        return self.client.post(self.base,json={'id':draft_id or str(uuid4()),'expected_version':version,
            'payload':{'project_code':code,'project_name':'本次输入','product_line_id':1,'archive_category':2,'serial_no':serial}})

    def assert_serial_conflict(self,response):
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(response.json()['detail']['field_key'],'serial_no')
        self.assertEqual(response.json()['detail']['code'],'ARCHIVE_UNIQUE_CONFLICT')
        self.assertNotIn('APPROVAL-001',response.text)

    def test_formal_disabled_and_other_drafts_reserve_serial_without_leaks(self):
        self.archive.is_enabled=0;self.db.commit()
        self.assert_serial_conflict(self.post_serial('NEW',' sn-001 '))
        a=self.save({'project_code':'ONE','serial_no':'Private-SN'})
        self.actor(self.other)
        response=self.post_serial('TWO',' private-sn ')
        self.assert_serial_conflict(response)
        self.assertNotIn(a['id'],response.text)

    def test_self_resave_rename_and_delete_release_only_committed_reservation(self):
        a=self.save({'project_code':'ONE','serial_no':'OLD'})
        a=self.save({'project_code':'ONE','serial_no':' old '},a['id'],a['version'])
        before=self.db.query(SysOperationLog).count()
        self.assert_serial_conflict(self.post_serial('ONE','SN-001',draft_id=a['id'],version=a['version']))
        self.assertEqual(self.db.get(self.Model,a['id']).version,a['version'])
        self.assertEqual(self.db.query(SysOperationLog).count(),before)
        a=self.save({'project_code':'ONE','serial_no':'NEW'},a['id'],a['version'])
        self.assertEqual(self.post_serial('TWO','OLD').status_code,200)
        response=self.client.request('DELETE',f"{self.base}/{a['id']}",json={'expected_version':a['version']})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.post_serial('THREE','NEW').status_code,200)

    def test_pending_reserves_new_and_formal_retains_old_until_approval(self):
        pending=self.submit(serial_no='PENDING-SN')
        self.assert_serial_conflict(self.post_serial('NEW','pending-sn'))
        self.assert_serial_conflict(self.post_serial('NEW','SN-001'))
        self.actor(self.head)
        response=self.client.post(f"/api/projects/archive-changes/requests/{pending['id']}/decide",json={'decision':'approve','expected_version':pending['version'],'opinion':'同意'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.post_serial('OLD-FREE','SN-001').status_code,200)
        self.assert_serial_conflict(self.post_serial('NEW','pending-sn'))

    def test_reject_and_withdraw_release_only_target_keep_old_and_idempotence(self):
        for action in ('reject','withdraw'):
            with self.subTest(action=action):
                self.actor(self.owner)
                pending=self.submit(serial_no=f'PENDING-{action}')
                self.assert_serial_conflict(self.post_serial(f'CONFLICT-{action}',f'pending-{action}'))
                if action=='reject':
                    self.actor(self.head);suffix='decide';body={'decision':'reject','expected_version':pending['version'],'opinion':'退回'}
                else:suffix='withdraw';body={'expected_version':pending['version']}
                url=f"/api/projects/archive-changes/requests/{pending['id']}/{suffix}"
                for _ in range(2):
                    response=self.client.post(url,json=body);self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(self.post_serial(f'FREE-{action}',f'pending-{action}').status_code,200)
                self.assert_serial_conflict(self.post_serial(f'OLD-{action}','SN-001'))

    def test_submit_cannot_reserve_a_draft_serial_and_preserves_input(self):
        self.save({'project_code':'RESERVED','serial_no':'DRAFT-SN'})
        response=self.client.post(f'/api/projects/archive-changes/{self.archive.id}/submit',json=self.payload(serial_no=' draft-sn '))
        self.assert_serial_conflict(response)
        self.assertEqual(self.db.query(self.Change).count(),0)
        self.db.refresh(self.archive);self.assertEqual(self.archive.serial_no,'SN-001')

    def test_damaged_active_json_fails_closed_not_ignored(self):
        a=self.save({'project_code':'ONE','serial_no':'SAFE'})
        row=self.db.get(self.Model,a['id']);row.payload_json='[]';self.db.commit()
        response=self.post_serial('TWO','OTHER')
        self.assertEqual(response.status_code,503,response.text)
        self.assertNotIn('SAFE',response.text)

    def test_approval_failure_rolls_back_formal_and_pending_reservation(self):
        pending=self.submit(serial_no='RESERVED-FAILURE')
        self.actor(self.head)
        from app.services.archive_change import decide_archive_change
        from app.schemas.archive_change import ArchiveChangeDecision
        with patch('app.services.archive_change.record_operation_log',side_effect=RuntimeError('synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                decide_archive_change(self.db,pending['id'],ArchiveChangeDecision(decision='approve',expected_version=pending['version'],opinion='合成'),self.head.id,scope_context=self.ctx)
        self.db.expire_all()
        self.assertEqual(self.db.get(self.Change,pending['id']).status,2)
        self.assertEqual(self.db.get(PmsProjectArchive,self.archive.id).serial_no,'SN-001')
        self.assert_serial_conflict(self.post_serial('AFTER-FAILURE','RESERVED-FAILURE'))

    def test_conversion_keeps_claim_and_lost_response_replays_original_archive(self):
        a=self.save({'project_code':'CONVERT','serial_no':'TO-FORMAL','manager_id':self.owner.id})
        url=f"{self.base}/{a['id']}/submit"
        for _ in range(2):
            response=self.client.post(url,json={'expected_version':a['version']})
            self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.db.query(PmsProjectArchive).filter_by(project_code='CONVERT').count(),1)
        self.assert_serial_conflict(self.post_serial('OTHER','TO-FORMAL'))

    def test_switch_into_main_rechecks_historical_formal_serial(self):
        # Simulate pre-deployment historical overlap without changing any real data.
        self.archive.archive_category=2;self.db.commit()
        row=self.Model(id=str(uuid4()),owner_id=self.owner.id,resource='archive-create',status='active',payload_json=json.dumps({'project_code':'HISTORY','serial_no':'SN-001','product_line_id':1,'archive_category':2}))
        self.db.add(row);self.db.commit();self.actor(self.head)
        response=self.client.put(f'/api/projects/archives/{self.archive.id}',json={'archive_category':1,'expected_version':self.snapshot()['change_version']})
        self.assert_serial_conflict(response)

    def test_failed_early_validation_does_not_retain_identity_lock(self):
        from app.services.archive_code_unique import identity_lock_held
        response=self.client.post(self.base,json={'id':str(uuid4()),'payload':{'project_code':'INVALID','project_name':'非法草稿','product_line_id':1}})
        self.assertEqual(response.status_code,422,response.text)
        self.assertFalse(identity_lock_held(self.db.connection()))
        response=self.client.post('/api/projects/archives',json={'project_code':'INVALID-CREATE','project_name':'非法枚举','product_line_id':1,'manager_id':self.owner.id,'archive_category':999999})
        self.assertEqual(response.status_code,422,response.text)
        self.assertFalse(identity_lock_held(self.db.connection()))

    def test_exact_first_save_and_conversion_replay_release_namespace_lock(self):
        from app.services.archive_code_unique import identity_lock_held
        from app.services.form_drafts import save_draft
        from app.schemas.form_draft import DraftSave
        draft_id=str(uuid4())
        data=DraftSave(id=draft_id,payload={'project_code':'IDEMPOTENT','project_name':'合成','product_line_id':1,'archive_category':2,'manager_id':self.owner.id,'serial_no':'IDEMPOTENT-SN'})
        first=save_draft(self.db,self.ctx,data)
        self.assertEqual(save_draft(self.db,self.ctx,data)['version'],first['version'])
        self.assertFalse(identity_lock_held(self.db.connection()))
        url=f"{self.base}/{draft_id}/submit"
        for _ in range(2):
            response=self.client.post(url,json={'expected_version':first['version']});self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(identity_lock_held(self.db.connection()))

    def test_formal_create_and_another_pending_request_cannot_take_reservations(self):
        self.save({'project_code':'PRIVATE-DRAFT','serial_no':'DRAFT-ONLY'})
        def create(code,serial):
            return self.client.post('/api/projects/archives',json={'project_code':code,'project_name':'合成','product_line_id':1,'archive_category':2,'manager_id':self.owner.id,'serial_no':serial})
        self.assert_serial_conflict(create('NO-DRAFT','draft-only'))
        pending=self.submit(serial_no='PENDING-ONLY')
        self.assert_serial_conflict(create('NO-PENDING','pending-only'))
        created=create('SECOND','OTHER-SERIAL');self.assertEqual(created.status_code,200,created.text)
        row=self.db.get(PmsProjectArchive,created.json()['id'])
        from app.services.archive_change import archive_business_version
        response=self.client.post(f'/api/projects/archive-changes/{row.id}/submit',json={'expected_version':archive_business_version(row),'reason':'合成','submission_id':str(uuid4()),'updates':{'serial_no':'PENDING-ONLY'}})
        self.assert_serial_conflict(response)
        self.assertEqual(self.db.query(self.Change).count(),1)

    def test_unedited_historical_identity_format_is_not_rewritten_by_other_fields(self):
        from sqlalchemy import update
        self.db.execute(update(PmsProjectArchive).where(PmsProjectArchive.id==self.archive.id).values(serial_no=' SN-001 ',project_code=' APPROVAL-001 '));self.db.commit();self.actor(self.head)
        response=self.client.put(f'/api/projects/archives/{self.archive.id}',json={'customer':'正常维护','expected_version':self.snapshot()['change_version']})
        self.assertEqual(response.status_code,200,response.text)
        self.db.refresh(self.archive)
        self.assertEqual(self.archive.serial_no,' SN-001 ')
        self.assertEqual(self.archive.project_code,' APPROVAL-001 ')

    def test_constraint_error_recheck_releases_lock_and_identifies_serial(self):
        from sqlalchemy.exc import IntegrityError
        from app.services.archive_code_unique import identity_lock_held
        failure=IntegrityError('synthetic',{},Exception('ux_pms_project_archive_serial_no_key'))
        with patch('app.services.erp_queue.enqueue',side_effect=failure):
            response=self.client.post('/api/projects/archives',json={'project_code':'FAIL-SERIAL','project_name':'合成','product_line_id':1,'archive_category':2,'manager_id':self.owner.id,'serial_no':'FAIL-SERIAL'})
        self.assert_serial_conflict(response)
        self.assertFalse(identity_lock_held(self.db.connection()))
        self.assertEqual(self.db.query(PmsProjectArchive).count(),1)
        self.actor(self.head)
        with patch('app.services.project.record_operation_log',side_effect=failure):
            response=self.client.put(f'/api/projects/archives/{self.archive.id}',json={'serial_no':'FAIL-UPDATE','expected_version':self.snapshot()['change_version']})
        self.assert_serial_conflict(response)
        self.assertFalse(identity_lock_held(self.db.connection()))
        self.db.refresh(self.archive);self.assertEqual(self.archive.serial_no,'SN-001')


if __name__=='__main__':
    suite=unittest.TestSuite(Serials(name) for name in Serials.__dict__ if name.startswith('test_'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
