"""Run the exact SQL probe fixture through real services with customer required."""
import ast,sys,unittest
from pathlib import Path
from datetime import datetime
sys.path[:0]=[str(Path(__file__).resolve().parents[3]/'backend/tests'),str(Path(__file__).resolve().parents[3]/'backend')]
from form_draft_contract import Drafts
from app.models.dict import SysDict,SysDictItem
from app.models.field_policy import SysBusinessFieldPolicy
from app.models.product_line import SysProductLine
from app.models.project import PmsProjectArchive
from app.models.erp_task import ErpSyncTask
class ConversionFixture(Drafts):
 def complete_probe_payload(self):
  tree=ast.parse((Path(__file__).parent/'isolated_probe.py').read_text())
  call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='save' and any(k.arg=='machine_model' for k in n.keywords))
  payload={k.arg:ast.literal_eval(k.value) for k in call.keywords if k.arg not in ('_id','_version','manager_id')}
  return dict(payload,project_code='PROBE-COMPLETE',project_name='probe fixture',product_line_id=1,manager_id=self.owner.id)
 def setUp(self):
  super().setUp()
  self.db.get(SysProductLine,1).organization_id=200292
  self.db.add(SysBusinessFieldPolicy(module_code='project_archive',field_key='customer',visible=1,editable=1,required=1,list_available=1,required_effective_at=datetime(2026,10,1)))
  for code,value in [('archive_machine_model','5'),('archive_quantity_unit','7')]:
   d=self.db.query(SysDict).filter_by(dict_code=code).one();self.db.add(SysDictItem(dict_id=d.id,item_value=value,item_label='fixture',status=1))
  self.db.commit()
 def test_exact_probe_fixture_converts_and_replays_with_required_customer(self):
  a=self.save(self.complete_probe_payload());url=f"{self.base}/{a['id']}/submit"
  result=self.client.post(url,json={'expected_version':a['version']})
  self.assertEqual(result.status_code,200,result.text)
  replay=self.client.post(url,json={'expected_version':a['version']});self.assertEqual(replay.status_code,200,replay.text)
  self.assertEqual(replay.json()['id'],result.json()['id'])
  self.assertEqual(self.db.query(PmsProjectArchive).count(),2)
  self.assertEqual(self.db.query(ErpSyncTask).count(),1)
 def test_required_customer_is_still_enforced_and_failed_conversion_keeps_draft(self):
  fields=self.complete_probe_payload();fields.pop('customer',None)
  a=self.save(fields);response=self.client.post(f"{self.base}/{a['id']}/submit",json={'expected_version':a['version']})
  self.assertEqual(response.status_code,422,response.text)
  self.assertEqual({i['field_key'] for i in response.json()['detail']['fields']},{'customer'})
  self.assertEqual(self.client.get(f"{self.base}/{a['id']}").json()['status'],'active')
  self.assertEqual(self.db.query(PmsProjectArchive).count(),1)
  self.assertEqual(self.db.query(ErpSyncTask).count(),0)
if __name__=='__main__':
 suite=unittest.TestSuite(ConversionFixture(n) for n in ConversionFixture.__dict__ if n.startswith('test_'))
 raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
