"""Actual services and API on a fresh disposable SQLite database."""
import sys,unittest,json
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import archive_change_contract as fixture
from app.models.project import PmsProjectArchive
from app.models.erp_task import ErpSyncTask
from app.models.operation_log import SysOperationLog

class Drafts(fixture.ArchiveChangeContract):
 # Inherit fixtures only, not their tests (see suite below).
 def setUp(self):
  self.assertTrue(Path('backend/app/api/form_drafts.py').exists(),'persistent draft API is missing')
  from app.models.form_draft import PmsFormDraft
  fixture.ArchiveChangeContract.setUp(self)
  from app.api.form_drafts import router
  self.client.app.include_router(router)
  self.Model=PmsFormDraft
  self.base='/api/form-drafts/archive-create'
 def save(self,payload=None,id=None,version=None):
  id=id or str(uuid4())
  body={'id':id,'expected_version':version,'payload':{'project_code':'DRAFT-SAMPLE','project_name':'待填写档案','product_line_id':1,'archive_category':2,**(payload or {})}}
  response=self.client.post(self.base,json=body)
  self.assertEqual(response.status_code,200,response.text)
  return response.json()
 def test_incomplete_cross_session_private_multiple_and_no_business_side_effect(self):
  a=self.save({'project_name':'未完成','quantity':2})
  self.save({'project_code':'DRAFT-SECOND'})
  self.db.expire_all()
  r=self.client.get(f"{self.base}/{a['id']}")
  self.assertEqual(r.json()['payload']['project_name'],'未完成')
  self.assertEqual(len(self.client.get(self.base).json()['items']),2)
  self.assertEqual(self.db.query(PmsProjectArchive).count(),1)
  self.assertEqual(self.db.query(ErpSyncTask).count(),0)
  self.actor(self.other,permissions=['project:archive:view','project:archive:add','business:data:all'])
  self.assertEqual(self.client.get(f"{self.base}/{a['id']}").status_code,404)
  self.assertEqual(self.client.get(self.base).json()['items'],[])
 def test_revoke_permission_scope_and_unassigned_creation_eligibility(self):
  a=self.save({'product_line_id':1})
  self.actor(self.owner,lines=[])
  self.assertEqual(self.client.get(f"{self.base}/{a['id']}").status_code,403)
  self.assertEqual(self.client.post(self.base,json={'id':str(uuid4()),'payload':{}}).status_code,403)
  self.actor(self.owner,permissions=['project:archive:view'])
  self.assertEqual(self.client.get(self.base).status_code,403)
 def test_payload_safety_types_quantity_and_no_erp_directory(self):
  for payload in ({'password':'x'},{'erp_synced':1},{'product_category':1},{'quantity':-1},{'quantity':1.5},{'quantity':True},{'project_name':'x'*129},{'manager_id':'bad'}):
   r=self.client.post(self.base,json={'id':str(uuid4()),'payload':{'project_code':'DRAFT-SAMPLE','project_name':'待填写档案',**payload}})
   self.assertEqual(r.status_code,422,r.text)
  with patch('app.services.product_line_source.get_organization',side_effect=RuntimeError('offline')):
   self.save({'product_line_id':1,'project_name':'不依赖ERP'})
 def test_conflict_preserves_latest_idempotent_first_save_delete_audit(self):
  a=self.save({'project_name':'first'})
  repeated=self.save({'project_name':'first'},a['id'],None)
  self.assertEqual(a['version'],repeated['version'])
  b=self.save({'project_name':'latest'},a['id'],a['version'])
  stale=self.client.post(self.base,json={'id':a['id'],'expected_version':a['version'],'payload':{'project_code':'DRAFT-SAMPLE','project_name':'stale','product_line_id':1,'archive_category':2}})
  self.assertEqual(stale.status_code,409)
  self.assertEqual(self.client.get(f"{self.base}/{a['id']}").json()['payload']['project_name'],'latest')
  r=self.client.request('DELETE',f"{self.base}/{a['id']}",json={'expected_version':b['version']})
  self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(self.client.get(self.base).json()['items'],[])
  self.assertEqual(self.db.query(SysOperationLog).filter_by(entity_type='pms_form_draft').count(),3)
 def test_disabled_values_restore_with_names_and_warning_but_cannot_create(self):
  from app.models.product_line import SysProductLine
  from app.models.dict import SysDict,SysDictItem
  a=self.save({'equipment_series':1,'product_line_id':1})
  self.db.add(SysProductLine(id=2,source_key='kingdee',organization_id=200,organization_code='002',organization_name='组织乙',display_name='产品线乙',name_key='line-two'))
  self.db.get(SysProductLine,1).is_enabled=0
  definition=self.db.query(SysDict).filter_by(dict_code='equipment_series').one()
  item=self.db.query(SysDictItem).filter_by(dict_id=definition.id,item_value='1').one();item.status=0
  self.db.commit();self.actor(self.owner,lines=[1,2])
  response=self.client.get(f"{self.base}/{a['id']}")
  self.assertEqual(response.status_code,200,response.text)
  self.assertTrue(response.json()['warnings'])
  self.assertTrue(response.json()['value_labels']['equipment_series'])
  self.assertEqual(self.client.post(f"{self.base}/{a['id']}/submit",json={'expected_version':a['version']}).status_code,422)
 def test_hidden_field_projected_out_and_hidden_write_rejected(self):
  from app.models.field_policy import SysBusinessFieldPolicy
  a=self.save({'remarks':'PRIVATE','project_name':'可见'})
  self.db.add(SysBusinessFieldPolicy(module_code='project_archive',field_key='remarks',visible=0,editable=1,required=0,list_available=0))
  self.db.commit()
  response=self.client.get(f"{self.base}/{a['id']}")
  self.assertNotIn('remarks',response.json()['payload'])
  self.assertNotIn('PRIVATE',response.text)
  response=self.client.post(self.base,json={'id':a['id'],'expected_version':a['version'],'payload':{'remarks':'new'}})
  self.assertEqual(response.status_code,422,response.text)
 def test_current_personnel_scope_rechecked_on_restore(self):
  a=self.save({'manager_id':self.other.id})
  self.ctx['data_scope']=1
  response=self.client.get(f"{self.base}/{a['id']}")
  self.assertEqual(response.status_code,404,response.text)
  self.assertEqual(self.client.get(self.base).json()['items'],[])
 def test_draft_audit_uses_chinese_protocol_values_without_private_payload(self):
  self.save({'project_name':'不应进入全局审计内容'})
  row=self.db.query(SysOperationLog).filter_by(entity_type='pms_form_draft').one()
  items=json.loads(row.diff_items_data)
  item=next(i for i in items if i['field_key']=='status')
  self.assertEqual(item['after_display'],'待填写')
  self.assertNotIn('不应进入全局审计内容',row.after_data)
  from app.services.field_catalog import build_field_catalog
  status=next(i for i in build_field_catalog() if i['module']=='form_draft' and i['field_code']=='status')
  self.assertEqual(status['source_type'],'system_fixed')
 def test_partial_validation_uses_shared_field_error_contract(self):
  response=self.client.post(self.base,json={'id':str(uuid4()),'payload':{'project_code':'DRAFT-SAMPLE','project_name':'x'*129}})
  self.assertEqual(response.status_code,422,response.text)
  self.assertIsInstance(response.json()['detail'],dict)
  self.assertEqual(response.json()['detail']['code'],'FIELD_POLICY_VALIDATION_FAILED')
  self.assertEqual(response.json()['detail']['fields'][0]['field_key'],'project_name')
 def test_draft_requires_identity_and_line_and_rejects_blank_identity(self):
  for payload,missing in [({}, {'project_code','project_name'}),({'project_code':'ONE'}, {'project_name'}),({'project_name':'项目'}, {'project_code'}),({'project_code':'  ','project_name':'项目'}, {'project_code'}),({'project_code':'ONE','project_name':'  '}, {'project_name'}),({'project_code':None,'project_name':'项目'}, {'project_code'})]:
   with self.subTest(payload=payload):
    response=self.client.post(self.base,json={'id':str(uuid4()),'payload':{'product_line_id':1,'archive_category':2,**payload}})
    self.assertEqual(response.status_code,422,response.text)
    fields={i['field_key'] for i in response.json()['detail']['fields']}
    self.assertEqual(fields,missing)
  self.assertEqual(self.db.query(self.Model).count(),0)
  self.assertEqual(self.db.query(SysOperationLog).filter_by(entity_type='pms_form_draft').count(),0)
  row=self.save({'project_code':'IDENTITY-ONLY','project_name':'只填写两项','product_line_id':1,'archive_category':2})
  self.assertEqual(row['payload'],{'project_code':'IDENTITY-ONLY','project_name':'只填写两项','product_line_id':1,'archive_category':2})
  response=self.client.post(f"{self.base}/{row['id']}/submit",json={'expected_version':row['version']})
  self.assertEqual(response.status_code,422,response.text)
  self.assertEqual(self.client.get(f"{self.base}/{row['id']}").json()['status'],'active')
  self.assertEqual(self.db.query(PmsProjectArchive).count(),1)
 def test_product_line_required_and_local_candidates_never_call_erp(self):
  for value in (None,''):
   response=self.client.post(self.base,json={'id':str(uuid4()),'payload':{'project_code':'LINE-REQ','project_name':'产品线必输','product_line_id':value}})
   self.assertEqual(response.status_code,422,response.text)
   self.assertIn('product_line_id',{i['field_key'] for i in response.json()['detail']['fields']})
  with patch('app.services.product_line_source.get_organization',side_effect=AssertionError('Draft candidates must not access ERP')):
   response=self.client.get(self.base+'/product-lines')
   self.assertEqual(response.status_code,200,response.text)
   self.assertTrue(response.json()['options'])
   self.assertTrue(all(i['value'] in self.ctx.get('product_line_ids',[1]) or 'business:data:all' in self.ctx.get('permissions',[]) for i in response.json()['options']))
 def test_resave_preserves_historical_hidden_and_readonly_fields_without_accepting_edits(self):
  from app.models.field_policy import SysBusinessFieldPolicy
  for visible in (0,1):
   row=self.save({'project_code':f'HISTORY-{visible}','remarks':'历史备注需保留'})
   policy=SysBusinessFieldPolicy(module_code='project_archive',field_key='remarks',visible=visible,editable=0,required=0,list_available=0)
   self.db.add(policy);self.db.commit()
   refreshed=self.client.get(f"{self.base}/{row['id']}").json()
   payload={k:v for k,v in refreshed['payload'].items() if k!='remarks'}
   payload['project_name']='继续填写的新名称'
   response=self.client.post(self.base,json={'id':row['id'],'expected_version':row['version'],'payload':payload})
   self.assertEqual(response.status_code,200,response.text)
   self.db.expire_all()
   self.assertEqual(json.loads(self.db.get(self.Model,row['id']).payload_json).get('remarks'),'历史备注需保留')
   response=self.client.post(self.base,json={'id':row['id'],'expected_version':response.json()['version'],'payload':{**payload,'remarks':'客户端篡改'}})
   self.assertEqual(response.status_code,422,response.text)
   self.db.delete(policy);self.db.commit()
 def test_draft_line_candidates_respect_scope_disabled_values_and_revocation(self):
  from app.models.product_line import SysProductLine
  self.db.add(SysProductLine(id=2,source_key='kingdee',organization_id=200,organization_code='002',organization_name='组织乙',display_name='产品线乙',name_key='line-two'))
  self.db.commit();self.actor(self.owner,lines=[1])
  response=self.client.get(self.base+'/product-lines')
  self.assertEqual([i['value'] for i in response.json()['options']],[1])
  response=self.client.post(self.base,json={'id':str(uuid4()),'payload':{'project_code':'SCOPE','project_name':'范围','product_line_id':2,'archive_category':2}})
  self.assertEqual(response.status_code,404)
  self.db.get(SysProductLine,1).is_enabled=0;self.db.commit();self.actor(self.owner,lines=[1,2])
  response=self.client.get(self.base+'/product-lines')
  self.assertEqual([i['value'] for i in response.json()['options']],[2])
  self.assertIn('1',response.json()['label_map'])
  self.actor(self.owner,permissions=['project:archive:view'],lines=[1,2])
  self.assertEqual(self.client.get(self.base+'/product-lines').status_code,403)
 def complete_payload(self):
  from app.models.dict import SysDict,SysDictItem
  for code,value in [('archive_machine_model','1'),('archive_quantity_unit','7')]:
   d=self.db.query(SysDict).filter_by(dict_code=code).one()
   self.db.add(SysDictItem(dict_id=d.id,item_value=value,item_label='测试值',status=1))
  self.db.commit()
  return {'project_code':'DRAFT-NEW','project_name':'草稿转档','product_line_id':1,'manager_id':self.owner.id,'archive_category':2,'machine_model':1,'quantity':1,'quantity_unit':7,'contract_signed_date':'2026-10-01','contract_ship_date':'2026-12-01'}
 def test_conversion_failure_success_and_lost_response_replay(self):
  a=self.save({'project_name':'未完成'})
  url=f"{self.base}/{a['id']}/submit"
  bad=self.client.post(url,json={'expected_version':a['version']})
  self.assertEqual(bad.status_code,422,bad.text)
  self.assertEqual(self.client.get(f"{self.base}/{a['id']}").json()['status'],'active')
  a=self.save(self.complete_payload(),a['id'],a['version'])
  with patch('app.services.form_drafts._audit',side_effect=RuntimeError('audit failed')):
   with self.assertRaisesRegex(RuntimeError,'audit failed'):self.client.post(url,json={'expected_version':a['version']})
  self.assertEqual(self.db.query(PmsProjectArchive).count(),1)
  self.assertEqual(self.db.query(ErpSyncTask).count(),0)
  result=self.client.post(url,json={'expected_version':a['version']})
  self.assertEqual(result.status_code,200,result.text)
  replay=self.client.post(url,json={'expected_version':a['version']})
  self.assertEqual(replay.json()['id'],result.json()['id'])
  self.assertEqual(self.db.query(PmsProjectArchive).count(),2)
  self.assertEqual(self.db.query(ErpSyncTask).count(),1)
  self.assertEqual(self.client.get(self.base).json()['items'],[])
  self.assertEqual(self.client.get(f"{self.base}/{a['id']}").json()['archive_id'],result.json()['id'])
if __name__=='__main__':
 suite=unittest.TestSuite(Drafts(name) for name in Drafts.__dict__ if name.startswith('test_'))
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 sys.exit(not result.wasSuccessful())
