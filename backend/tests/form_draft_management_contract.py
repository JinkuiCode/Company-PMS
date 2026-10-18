"""Scoped draft viewing and one confirmed deletion; disposable data only."""
import sys,json,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from form_draft_contract import Drafts
from app.models.operation_log import SysOperationLog

class Management(Drafts):
 def setUp(self):
  super().setUp()
  from app.api.form_draft_management import router
  self.client.app.include_router(router)
  self.admin='/api/archive-draft-management'
 def admin_actor(self,**kw):
  self.actor(self.head,permissions=['project:archive:view','project:archive:draft:manage'],**kw)
 def remove(self,row):
  return self.client.request('DELETE',f"{self.admin}/{row['id']}",json={'expected_version':row['version']})
 def test_manage_permission_required_no_admin_bypass_and_no_scope_leak(self):
  row=self.save();self.ctx['role_codes']=['admin']
  self.assertEqual(self.client.get(self.admin).status_code,403)
  self.admin_actor(lines=[])
  self.assertEqual(self.client.get(self.admin).json()['total'],0)
  self.assertEqual(self.client.get(f"{self.admin}/{row['id']}").status_code,404)
  self.admin_actor();self.ctx['data_scope']=2
  self.assertEqual(self.client.get(self.admin).json()['total'],0)
  self.assertEqual(self.remove(row).status_code,404)
 def test_departed_owner_still_in_historical_department_and_delete_is_audited(self):
  row=self.save({'manager_id':self.owner.id,'remarks':'PRIVATE-CONTENT'})
  self.owner.status=0;self.db.commit();self.admin_actor();self.ctx.update(data_scope=2,dept_id=self.dept.id)
  response=self.client.get(self.admin)
  self.assertEqual(response.status_code,200,response.text)
  self.assertEqual(response.json()['total'],1)
  response=self.remove(row);self.assertEqual(response.status_code,200,response.text)
  self.assertEqual(self.client.get(self.admin).json()['total'],0)
  self.assertEqual(self.client.get(f"{self.admin}/{row['id']}").status_code,404)
  self.db.expire_all();stored=self.db.get(self.Model,row['id'])
  self.assertEqual(stored.status,'deleted')
  self.assertEqual(json.loads(stored.payload_json)['remarks'],'PRIVATE-CONTENT')
  log=self.db.query(SysOperationLog).filter_by(action='draft_delete',operator_id=self.head.id).one()
  self.assertNotIn('PRIVATE-CONTENT',str(log.after_data))
  self.assertIn('删除',log.summary)
 def test_cas_and_log_failure_leave_draft_unchanged(self):
  row=self.save();row2=self.save({'project_name':'最新名称'},row['id'],row['version']);self.admin_actor()
  self.assertEqual(self.remove(row).status_code,409)
  with patch('app.services.form_draft_management.record_operation_log',side_effect=RuntimeError('audit down')):
   with self.assertRaisesRegex(RuntimeError,'audit down'):self.remove(row2)
  self.db.expire_all();stored=self.db.get(self.Model,row['id'])
  self.assertEqual((stored.status,stored.version),('active',row2['version']))
  self.assertEqual(self.db.query(SysOperationLog).filter_by(action='draft_delete').count(),0)
 def test_no_transfer_restore_recycle_or_used_drafts(self):
  row=self.save();self.admin_actor()
  for action in ('transfer','restore','clean'):
   self.assertEqual(self.client.post(f"{self.admin}/{row['id']}/{action}",json={'expected_version':1}).status_code,404)
  self.db.get(self.Model,row['id']).status='used';self.db.commit()
  self.assertEqual(self.client.get(self.admin).json()['total'],0)
  self.assertEqual(self.remove(row).status_code,404)
 def test_history_and_live_revoke(self):
  row=self.save();self.admin_actor()
  response=self.client.get(f"{self.admin}/{row['id']}/history")
  self.assertEqual(response.status_code,200,response.text)
  self.ctx['permissions']=[]
  self.assertEqual(self.client.get(f"{self.admin}/{row['id']}/history").status_code,403)
  self.assertEqual(self.remove(row).status_code,403)
 def test_readonly_detail_uses_backend_field_labels_and_projections(self):
  row=self.save({'manager_id':self.owner.id,'remarks':'应隐藏内容'})
  from app.models.field_policy import SysBusinessFieldPolicy
  self.db.add(SysBusinessFieldPolicy(module_code='project_archive',field_key='remarks',visible=0,editable=0,required=0,list_available=0))
  self.db.commit();self.admin_actor()
  response=self.client.get(f"{self.admin}/{row['id']}")
  self.assertEqual(response.status_code,200,response.text)
  fields=response.json().get('fields',[])
  self.assertEqual(response.json().get('product_line_id'),1,'query schemes keep stable product-line keys while displaying names')
  self.assertTrue(fields,'management detail requires the shared backend field labels')
  self.assertEqual(next(i['display'] for i in fields if i['key']=='product_line_id'),'产品线甲')
  self.assertEqual(next(i['display'] for i in fields if i['key']=='manager_id'),'项目负责人')
  self.assertEqual(next(i['label'] for i in fields if i['key']=='project_code'),'项目编号')
  self.assertNotIn('remarks',{i['key'] for i in fields})
  self.assertNotIn('应隐藏内容',response.text)
 def test_detail_order_matches_archive_create_form_not_registry_insertion(self):
  row=self.save({'quantity':1,'customer':'验收客户','manager_id':self.owner.id,'remarks':'应排在末尾'})
  self.admin_actor()
  result=self.client.get(f"{self.admin}/{row['id']}")
  self.assertEqual(result.status_code,200,result.text)
  keys=[field['key'] for field in result.json()['fields']]
  self.assertLess(keys.index('project_code'),keys.index('quantity'))
  self.assertLess(keys.index('project_name'),keys.index('customer'))
  self.assertLess(keys.index('product_line_id'),keys.index('quantity'))
  self.assertLess(keys.index('manager_id'),keys.index('remarks'))
  self.assertEqual(keys[-1],'creator_name')
 def test_owner_and_manager_scopes_both_required_and_disabled_line_history(self):
  row=self.save({'manager_id':self.other.id});self.admin_actor();self.ctx.update(data_scope=2,dept_id=self.dept.id)
  self.assertEqual(self.client.get(self.admin).json()['total'],0)
  self.assertEqual(self.remove(row).status_code,404)
  self.ctx['data_scope']=4
  from app.models.product_line import SysProductLine
  self.db.get(SysProductLine,1).is_enabled=0;self.db.commit()
  self.assertEqual(self.client.get(self.admin).json()['total'],1)
  self.assertEqual(self.remove(row).status_code,200)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Management(n) for n in Management.__dict__ if n.startswith('test_')))
 sys.exit(not result.wasSuccessful())
