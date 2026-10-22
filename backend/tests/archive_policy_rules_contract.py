"""A1 behavior on a fresh synthetic SQLite DB; no existing DB or ERP access."""
import unittest
from datetime import datetime, timedelta
from uuid import uuid4
from archive_form_linkage_contract import ArchiveFormRules
from app.models.field_policy import SysBusinessFieldPolicy
from app.models.dict import SysDict, SysDictItem
from app.models.project import PmsProjectArchive

class PolicyRules(ArchiveFormRules):
 def required(self,key):
  row=self.db.query(SysBusinessFieldPolicy).filter_by(module_code='project_archive',field_key=key).first()
  if row is None:row=SysBusinessFieldPolicy(module_code='project_archive',field_key=key);self.db.add(row)
  row.visible=True;row.editable=True;row.required=True;row.list_available=True;row.required_effective_at=datetime.now()-timedelta(days=500)
  self.db.commit()
 def unit_pcs(self):
  definition=self.db.query(SysDict).filter_by(dict_code='archive_quantity_unit').one()
  row=self.db.query(SysDictItem).filter_by(dict_id=definition.id,item_value='7').one();row.item_label='pcs';self.db.commit();return row
 def formal(self,code,category=2,**extra):
  return self.client.post('/api/projects/archives',json=dict(project_code=code,project_name=code,product_line_id=1,archive_category=category,manager_id=self.owner.id,**extra))
 def test_each_non_main_accepts_optional_values_and_all_contract_dates_empty(self):
  for key in ('customer','contract_signed_date','contract_ship_date'):self.required(key)
  for category in (2,3,4,5,6,7,8):
   # Existing enum fixture contains these category values.
   r=self.formal('NONMAIN-'+str(category),category,customer=None,quantity=None,quantity_unit=None,machine_model=None,contract_signed_date=None,contract_ship_date=None)
   self.assertEqual(r.status_code,200,r.text)
  r=self.formal('MAIN',1,customer='客户',machine_model=5,quantity=1,quantity_unit=7,equipment_series=6,serial_no='MAIN-SN',contract_signed_date=None,contract_ship_date=None)
  self.assertEqual(r.status_code,200,r.text)
 def test_metadata_separates_form_projection_from_global_field_permissions(self):
  self.unit_pcs()
  fields={i['field_key']:i for i in self.client.get('/api/projects/archives/fields').json()['items']}
  for key in ('customer_full_name','legacy_archive_status','legacy_code_date','legacy_updated_date','delivery_note','remarks'):
   self.assertTrue(fields[key].get('form_hidden'));self.assertTrue(fields[key]['visible']);self.assertTrue(fields[key]['list_available'])
  for key in ('equipment_series','serial_no'):
   self.assertEqual(fields[key]['form_visible_when'],{'field':'archive_category','values':[1]})
  self.assertEqual(fields['quantity']['default_value'],1);self.assertEqual(fields['quantity_unit']['default_value'],7)
  self.assertFalse(fields['contract_signed_date']['required']);self.assertFalse(fields['contract_ship_date']['required'])
 def test_new_omission_defaults_only_and_explicit_empty_remains_empty(self):
  self.unit_pcs()
  r=self.formal('DEFAULT');self.assertEqual(r.status_code,200,r.text)
  row=self.db.get(PmsProjectArchive,r.json()['id']);self.assertEqual(row.quantity,1);self.assertEqual(row.quantity_unit,7)
  r=self.formal('EXPLICIT-EMPTY',quantity=None,quantity_unit=None);self.assertEqual(r.status_code,200,r.text)
  row=self.db.get(PmsProjectArchive,r.json()['id']);self.assertIsNone(row.quantity);self.assertIsNone(row.quantity_unit)
  row=self.save({'project_code':'OLD-DRAFT','manager_id':self.owner.id})
  r=self.client.post(f"{self.base}/{row['id']}/submit",json={'expected_version':row['version']});self.assertEqual(r.status_code,200,r.text)
  archive=self.db.get(PmsProjectArchive,r.json()['id']);self.assertIsNone(archive.quantity);self.assertIsNone(archive.quantity_unit)
 def test_non_main_required_override_not_restore_old_unconditional_basic_requirements(self):
  for key in ('quantity','quantity_unit','machine_model','customer'):self.required(key)
  r=self.formal('ONLY-FIVE',customer=None,quantity=None,quantity_unit=None,machine_model=None)
  self.assertEqual(r.status_code,200,r.text)
  r=self.formal('MAIN-MISSING',1,customer=None,quantity=1,quantity_unit=7,machine_model=5,equipment_series=6,serial_no='OTHER-SN')
  self.assertEqual(r.status_code,422,r.text)
  self.assertIn('customer',{i['field_key'] for i in r.json()['detail']['fields']})
 def test_hidden_draft_fields_survive_projection_resave_without_nulling(self):
  row=self.save({'project_code':'HIDDEN-HISTORY','archive_category':1,'equipment_series':6,'serial_no':'OLD-SERIAL','remarks':'旧备注'})
  r=self.client.post(self.base,json={'id':row['id'],'expected_version':row['version'],'payload':{'project_code':'HIDDEN-HISTORY','project_name':'保持原值','archive_category':2,'product_line_id':1}})
  self.assertEqual(r.status_code,200,r.text)
  payload=r.json()['payload'];self.assertEqual(payload.get('remarks'),'旧备注');self.assertEqual(payload.get('serial_no'),'OLD-SERIAL');self.assertEqual(payload.get('equipment_series'),6)

 def test_customer_remains_visible_when_optional_and_disabled_unit_has_no_default(self):
  self.unit_pcs()
  self.required('customer')
  fields={i['field_key']:i for i in self.client.get('/api/projects/archives/fields').json()['items']}
  self.assertIsNone(fields['customer'].get('form_visible_when'))
  unit=self.unit_pcs();unit.status=0;self.db.commit()
  fields={i['field_key']:i for i in self.client.get('/api/projects/archives/fields').json()['items']}
  self.assertIsNone(fields['quantity_unit'].get('default_value'))

 def test_explicit_hidden_clear_overrides_retained_history_when_category_changes(self):
  row=self.save({'project_code':'CLEAR-HISTORY','archive_category':1,'equipment_series':6,'serial_no':'OLD-SERIAL'})
  r=self.client.post(self.base,json={'id':row['id'],'expected_version':row['version'],'payload':{'project_code':'CLEAR-HISTORY','project_name':'明确清空','archive_category':2,'product_line_id':1,'equipment_series':None,'serial_no':None}})
  self.assertEqual(r.status_code,200,r.text)
  self.assertIsNone(r.json()['payload']['equipment_series']);self.assertIsNone(r.json()['payload']['serial_no'])

if __name__=='__main__':
 names=[name for name in PolicyRules.__dict__ if name.startswith('test_')]
 result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(PolicyRules(name) for name in names))
 raise SystemExit(not result.wasSuccessful())
