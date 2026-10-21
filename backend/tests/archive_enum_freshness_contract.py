"""Archive-only enum rejection stays structured on disposable fixture databases."""
import unittest
from uuid import uuid4
from archive_form_linkage_contract import ArchiveFormRules
from app.models.dict import SysDict, SysDictItem
from app.models.project import PmsProjectArchive
from app.models.operation_log import SysOperationLog
from app.models.erp_task import ErpSyncTask

class ArchiveEnumFreshness(ArchiveFormRules):
 def disabled(self,value):
  definition=self.db.query(SysDict).filter_by(dict_code='archive_machine_model').one()
  item=self.db.query(SysDictItem).filter_by(dict_id=definition.id,item_value=str(value)).one()
  item.status=0;self.db.commit()
 def assert_enum_error(self,response):
  self.assertEqual(response.status_code,422,response.text)
  detail=response.json()['detail']
  self.assertIsInstance(detail,dict)
  self.assertEqual(detail['code'],'ARCHIVE_ENUM_UNAVAILABLE')
  self.assertEqual(detail['field_key'],'machine_model')
  self.assertIn('机型',detail['message']);self.assertIn('禁用',detail['message'])
 def payload_new(self):
  return {'project_code':'NEW-ENUM','project_name':'保留输入','product_line_id':1,'manager_id':self.owner.id,'archive_category':2,'machine_model':6,'quantity':1,'quantity_unit':7,'contract_signed_date':'2026-10-01','contract_ship_date':'2026-12-01'}
 def test_create_rejects_disabled_enum_before_archive_queue_or_audit(self):
  self.disabled(6);before=self.db.query(SysOperationLog).count()
  self.assert_enum_error(self.client.post('/api/projects/archives',json=self.payload_new()))
  self.assertEqual(self.db.query(PmsProjectArchive).count(),1)
  self.assertEqual(self.db.query(ErpSyncTask).count(),0);self.assertEqual(self.db.query(SysOperationLog).count(),before)
 def test_draft_rejection_keeps_existing_payload_version_and_audit(self):
  row=self.save({'machine_model':6});self.disabled(6)
  changed={**row['payload'],'machine_model':7};row=self.save(changed,row['id'],row['version'])
  before=self.db.query(SysOperationLog).count()
  response=self.client.post(self.base,json={'id':row['id'],'expected_version':row['version'],'payload':{**row['payload'],'machine_model':6}})
  self.assert_enum_error(response)
  current=self.client.get(f"{self.base}/{row['id']}").json()
  self.assertEqual(current['version'],row['version']);self.assertEqual(current['payload']['machine_model'],7)
  self.assertEqual(self.db.query(SysOperationLog).count(),before)
 def test_update_and_approval_preview_reject_disabled_changed_value(self):
  self.disabled(6);version=self.snapshot()['change_version']
  self.actor(self.head,lines=[1,2,3,4])
  self.assert_enum_error(self.client.put(f'/api/projects/archives/{self.archive.id}',json={'machine_model':6,'expected_version':version}))
  self.actor(self.owner,lines=[1,2,3,4])
  self.assert_enum_error(self.client.post(f'/api/projects/archive-changes/{self.archive.id}/preview',json={'updates':{'machine_model':6},'expected_version':version}))
  self.db.refresh(self.archive);self.assertEqual(self.archive.machine_model,1)
 def test_historical_unchanged_disabled_is_preserved_but_conversion_is_new(self):
  self.disabled(1);self.actor(self.head,lines=[1,2,3,4])
  r=self.client.put(f'/api/projects/archives/{self.archive.id}',json={'machine_model':1,'customer':'只改客户','expected_version':self.snapshot()['change_version']})
  self.assertEqual(r.status_code,200,r.text)
  self.db.refresh(self.archive);self.assertEqual(self.archive.machine_model,1)
  self.actor(self.owner,lines=[1,2,3,4]);row=self.save({'machine_model':6});self.disabled(6)
  row=self.save(row['payload'],row['id'],row['version'])
  self.assert_enum_error(self.client.post(f"{self.base}/{row['id']}/submit",json={'expected_version':row['version']}))
  self.assertEqual(self.client.get(f"{self.base}/{row['id']}").json()['status'],'active')

if __name__=='__main__':
 suite=unittest.TestSuite(ArchiveEnumFreshness(name) for name in ArchiveEnumFreshness.__dict__ if name.startswith('test_'))
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 raise SystemExit(not result.wasSuccessful())
