"""Bounded owner-only maintenance of trusted initial archives, synthetic DB only."""
import unittest,json
from unittest.mock import patch
from archive_maintenance_contract import ArchiveMaintenance,PERMISSIONS
from app.models.operation_log import SysOperationLog
from app.models.erp_task import ErpSyncTask
from app.services.archive_change import archive_business_values
from app.services.operation_log import serialize_model

class LegacyManagerAddress(unittest.TestCase):
    actor=ArchiveMaintenance.actor
    snapshot=ArchiveMaintenance.snapshot
    tearDown=ArchiveMaintenance.tearDown
    body=ArchiveMaintenance.body
    save=ArchiveMaintenance.save
    def setUp(self):
        ArchiveMaintenance.setUp(self)
        self.other_dept.leader_id=self.head.id
        self.archive.data_origin='kingdee_initial';self.archive.governance_legacy=True
        self.archive.address_detail='  历史详细地址（原文字）  '
        self.db.commit()
    def preview(self,body):
        return self.client.post(f'/api/projects/archives/{self.archive.id}/maintenance/preview',json={k:v for k,v in body.items() if k!='reason'})
    def test_preview_and_submit_only_change_manager_and_keep_address_bytes(self):
        body=self.body(manager_id=self.other.id);before=serialize_model(self.archive)
        preview=self.preview(body);self.assertEqual(preview.status_code,200,preview.text)
        self.db.refresh(self.archive);self.assertEqual(serialize_model(self.archive),before)
        self.assertEqual(self.db.query(SysOperationLog).count(),0)
        response=self.save(body);self.assertEqual(response.status_code,200,response.text)
        self.db.refresh(self.archive);after=serialize_model(self.archive)
        changed={key for key in before if before[key]!=after[key]}
        self.assertTrue(changed <= {'manager_id','updated_by','updated_at'},changed)
        self.assertEqual(after['manager_id'],self.other.id)
        for key in ('address_province','address_city','address_detail','data_origin','governance_legacy'):
            self.assertEqual(after[key],before[key])
        log=self.db.query(SysOperationLog).one();self.assertEqual(log.action,'maintain')
        self.assertIn(body['reason'],log.summary);self.assertEqual(json.loads(log.diff_data)['manager_id'],{'before':self.owner.id,'after':self.other.id})
        self.assertEqual(self.db.query(ErpSyncTask).count(),0)
        self.assertEqual(self.save(body).status_code,409)
    def test_no_exception_for_origin_or_marker_or_no_change(self):
        for origin,legacy in [('kingdee_initial',False),('pms',True)]:
            self.archive.data_origin=origin;self.archive.governance_legacy=legacy;self.db.commit()
            body=self.body(manager_id=self.other.id)
            self.assertEqual(self.preview(body).status_code,422,(origin,legacy))
            self.assertEqual(self.save(body).status_code,422,(origin,legacy))
        self.archive.data_origin='kingdee_initial';self.archive.governance_legacy=True;self.db.commit()
        self.assertEqual(self.save(self.body(manager_id=self.owner.id)).status_code,422)
    def test_any_additional_business_key_even_unchanged_keeps_strict_address(self):
        current=json.loads(json.dumps(archive_business_values(self.archive),default=str))
        for key,value in current.items():
            if key=='manager_id':continue
            with self.subTest(key=key):
                body=self.body(**{'manager_id':self.other.id,key:value})
                self.assertEqual(self.preview(body).status_code,422,(key,self.preview(body).text))
                self.assertEqual(self.save(body).status_code,422,key)
        self.db.refresh(self.archive);self.assertEqual(self.archive.manager_id,self.owner.id)
        self.assertEqual(self.db.query(SysOperationLog).count(),0)
    def test_normal_edit_and_address_change_remain_strict(self):
        self.actor(self.head,permissions=PERMISSIONS)
        body=self.body(manager_id=self.other.id)
        response=self.client.put(f'/api/projects/archives/{self.archive.id}',json={**body['updates'],'expected_version':body['expected_version']})
        self.assertEqual(response.status_code,422,response.text)
        body=self.body(manager_id=self.other.id,address_detail='新的地址')
        self.assertEqual(self.save(body).status_code,422)
    def test_permissions_scope_version_status_and_owner_rules_still_apply(self):
        body=self.body(manager_id=self.other.id)
        for permission in PERMISSIONS:
            self.actor(self.other,permissions=[p for p in PERMISSIONS if p!=permission])
            self.assertEqual(self.save(body).status_code,403,permission)
        self.actor(self.other,permissions=PERMISSIONS,lines=[]);self.assertEqual(self.save(body).status_code,404)
        self.actor(self.other,permissions=PERMISSIONS);self.assertEqual(self.save({**body,'expected_version':'0'*64}).status_code,409)
        for field,value in [('is_enabled',0),('erp_sync_status','pending'),('erp_sync_status','review')]:
            setattr(self.archive,field,value);self.db.commit()
            self.assertEqual(self.save(self.body(manager_id=self.other.id)).status_code,409,(field,value))
            setattr(self.archive,field,1 if field=='is_enabled' else None);self.db.commit()
        self.other.status=0;self.db.commit()
        self.actor(self.head,permissions=PERMISSIONS)
        self.assertEqual(self.save(self.body(manager_id=self.other.id)).status_code,422)
    def test_late_failure_rolls_back_manager_address_and_audit(self):
        body=self.body(manager_id=self.other.id);before=serialize_model(self.archive)
        with patch('app.services.project.record_operation_log',side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):self.save(body)
        self.db.refresh(self.archive);self.assertEqual(serialize_model(self.archive),before)
        self.assertEqual(self.db.query(SysOperationLog).count(),0)
        self.assertEqual(self.db.query(ErpSyncTask).count(),0)
    def test_complete_or_all_empty_address_keeps_existing_success_behavior(self):
        for values in [(None,None,None),('32','3202','有效详细地址')]:
            for key,value in zip(('address_province','address_city','address_detail'),values):setattr(self.archive,key,value)
            self.db.commit();body=self.body(manager_id=self.other.id)
            response=self.preview(body);self.assertEqual(response.status_code,200,response.text)
    def test_http_cannot_supply_internal_compatibility_context(self):
        body=self.body(manager_id=self.other.id)
        response=self.save({**body,'address_compatibility':True})
        self.assertEqual(response.status_code,422,response.text)

    def test_pending_request_and_other_field_policies_are_not_bypassed(self):
        from app.models.archive_change import ArchiveChange
        from app.models.field_policy import SysBusinessFieldPolicy
        body=self.body(manager_id=self.other.id)
        pending=ArchiveChange(archive_id=self.archive.id,active_archive_id=self.archive.id,submission_id='synthetic',request_hash='hash',author_id=self.owner.id,approver_id=self.head.id,department_id=self.dept.id,base_version=body['expected_version'],updates_json='{"customer":"待审核"}',differences_json='[]',reason='合成',status=2)
        self.db.add(pending);self.db.commit()
        self.assertEqual(self.save(body).status_code,409)
        self.db.delete(pending);self.db.commit()
        from datetime import timedelta
        from app.services.field_policy import get_effective_field_policies
        policy=SysBusinessFieldPolicy(module_code='project_archive',field_key='customer',visible=True,editable=True,required=True,list_available=True,required_effective_at=self.archive.created_at-timedelta(days=1))
        self.db.add(policy);self.db.commit()
        effective=next(item for item in get_effective_field_policies(self.db,'project_archive')['items'] if item['field_key']=='customer')
        self.assertTrue(effective['required']);self.assertIsNotNone(effective['required_effective_at'])
        response=self.save(body);self.assertEqual(response.status_code,422,response.text)
        self.assertIn('customer',{item['field_key'] for item in response.json()['detail']['fields']})
        self.db.refresh(self.archive);self.assertEqual(self.archive.manager_id,self.owner.id)

    def test_approval_submission_and_new_archives_have_no_address_exception(self):
        from uuid import uuid4
        self.actor(self.owner)
        response=self.client.post(f'/api/projects/archive-changes/{self.archive.id}/submit',json={'updates':{'manager_id':self.other.id},'expected_version':self.snapshot()['change_version'],'reason':'合成','submission_id':str(uuid4())})
        self.assertEqual(response.status_code,422,response.text)
        self.assertTrue({'address_province','address_city'} <= {item['field_key'] for item in response.json()['detail']['fields']})
        response=self.client.post('/api/projects/archives',json={'project_code':'NEW-ADDRESS','project_name':'合成新建','product_line_id':1,'archive_category':2,'manager_id':self.owner.id,'address_detail':'只有详细地址'})
        self.assertEqual(response.status_code,422,response.text)
        self.assertTrue({'address_province','address_city'} <= {item['field_key'] for item in response.json()['detail']['fields']})
        self.assertEqual(self.db.query(self.Change).count(),0)
        self.assertEqual(self.db.query(ErpSyncTask).count(),0)

    def test_internal_context_is_bound_to_original_identity_address_and_exact_keys(self):
        from app.services.project import _legacy_manager_address_context,apply_archive_updates
        from app.schemas.project import ArchiveUpdate
        from fastapi import HTTPException
        context=_legacy_manager_address_context(self.archive,{'manager_id':self.other.id})
        for updates in ({'manager_id':self.other.id,'project_name':self.archive.project_name},{'manager_id':self.owner.id}):
            with self.subTest(updates=updates),self.assertRaises(HTTPException) as error:
                apply_archive_updates(self.db,self.archive.id,ArchiveUpdate(**updates),self.other.id,archive=self.archive,scope_context=self.ctx,dry_run=True,_maintenance_address_context=context)
            self.assertEqual(error.exception.status_code,422)
        self.archive.address_detail='已变化的历史地址'
        with self.assertRaises(HTTPException) as error:
            apply_archive_updates(self.db,self.archive.id,ArchiveUpdate(manager_id=self.other.id),self.other.id,archive=self.archive,scope_context=self.ctx,dry_run=True,_maintenance_address_context=context)
        self.assertEqual(error.exception.status_code,422)
        self.db.refresh(self.archive);self.assertEqual(self.archive.address_detail,'  历史详细地址（原文字）  ')

if __name__=='__main__':
    suite=unittest.TestSuite(LegacyManagerAddress(n) for n in LegacyManagerAddress.__dict__ if n.startswith('test_'))
    result=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(not result.wasSuccessful())
