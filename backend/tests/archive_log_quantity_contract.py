"""Approved presentation and positive-quantity rules on disposable databases."""
import sys,json,unittest
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import operation_log_reference_display_contract as logs
import archive_change_contract as archives
import offline_archive_import_contract as imports
from fastapi import HTTPException
from app.services.field_policy import validate_business_field_write,MODULE_PROJECT_ARCHIVE
from app.models.erp_task import ErpSyncTask
from app.models.operation_log import SysOperationLog

class LogPresentation(unittest.TestCase):
 setUp=logs.ReferenceLogDisplay.setUp
 tearDown=logs.ReferenceLogDisplay.tearDown
 log=logs.ReferenceLogDisplay.log
 views=logs.ReferenceLogDisplay.views
 def test_legacy_names_are_plain_with_separate_source_and_raw_storage_unchanged(self):
  row=self.log(after={'manager_id':17,'business_product_line_id':1})
  original=(row.after_data,row.diff_items_data,row.diff_data)
  for items in self.views(row):
   fields={i['field_key']:i for i in items}
   self.assertEqual(fields['manager_id']['after_display'],'杨志刚（owner）')
   self.assertEqual(fields['business_product_line_id']['after_display'],'8吋Bench')
   for item in items:self.assertEqual(item['after_name_source'],'current')
  self.assertEqual((row.after_data,row.diff_items_data,row.diff_data),original)
 def test_snapshot_is_authoritative_and_has_no_current_source(self):
  row=self.log(after={'manager_id':17},legacy=False)
  self.user.real_name='后来改名';self.db.commit()
  for items in self.views(row):
   self.assertEqual(items[0]['after_display'],'杨志刚（owner）')
   self.assertNotEqual(items[0].get('after_name_source'),'current')
 def test_log_order_follows_new_form_in_both_views_and_system_fields_last(self):
  keys=['archive_category','project_code','project_name','customer','business_product_line_id','quantity','quantity_unit','manager_id','machine_model','equipment_series','serial_no','contract_ship_date','project_contact','remarks','erp_sync_status']
  row=self.log(after={k:(17 if k=='manager_id' else 1 if k=='business_product_line_id' else 'sample') for k in reversed(keys)})
  from app.services.document_history import _project_items
  audit=self.views(row)[0]
  allowed=set(keys)|{'product_line_id'}
  document=_project_items(self.db,row,allowed)
  for items in (audit,document):self.assertEqual([i['field_key'] for i in items],keys)

class QuantityWrite(unittest.TestCase):
 setUp=archives.ArchiveChangeContract.setUp
 tearDown=archives.ArchiveChangeContract.tearDown
 actor=archives.ArchiveChangeContract.actor
 snapshot=archives.ArchiveChangeContract.snapshot
 payload=archives.ArchiveChangeContract.payload
 submit=archives.ArchiveChangeContract.submit
 def test_write_rule_rejects_nonpositive_fraction_and_overflow(self):
  for value in (0,-1,Decimal('1.5'),Decimal('1000000000000')):
   with self.subTest(value=value):
    with self.assertRaises(HTTPException) as caught:
     validate_business_field_write(self.db,MODULE_PROJECT_ARCHIVE,current_values={'quantity':1},updates={'quantity':value},entity_created_at=self.archive.created_at,is_create=False,entity_governance_legacy=True)
    self.assertIn('quantity',str(caught.exception.detail))
 def test_actual_owner_submission_rejects_invalid_quantity(self):
  for value in (0,-1,'1.25'):
   with self.subTest(value=value):
    response=self.client.post(f'/api/projects/archive-changes/{self.archive.id}/submit',json=self.payload(quantity=value))
    self.assertEqual(response.status_code,422,response.text)
  self.assertEqual(self.db.query(self.Change).count(),0)
 def test_create_rejects_invalid_quantity_and_accepts_positive_integer(self):
  from app.models.dict import SysDict,SysDictItem
  from app.models.project import PmsProjectArchive
  for code,value in [('archive_machine_model','1'),('archive_quantity_unit','7')]:
   definition=self.db.query(SysDict).filter_by(dict_code=code).one()
   self.db.add(SysDictItem(dict_id=definition.id,item_value=value,item_label='测试值',status=1))
  self.db.commit()
  body={'project_code':'QUANTITY-NEW','project_name':'数量新建','product_line_id':1,'manager_id':self.owner.id,'archive_category':2,'machine_model':1,'quantity_unit':7,'contract_signed_date':'2026-10-01','contract_ship_date':'2026-12-01'}
  for value in (0,-1,'1.5'):
   response=self.client.post('/api/projects/archives',json={**body,'quantity':value})
   self.assertEqual(response.status_code,422,response.text)
   self.assertIn('quantity',response.text)
  response=self.client.post('/api/projects/archives',json={**body,'quantity':'2.00000000'})
  self.assertEqual(response.status_code,200,response.text)
  self.assertEqual(self.db.get(PmsProjectArchive,response.json()['id']).quantity,2)
 def test_maintenance_preview_rejects_fraction(self):
  self.actor(self.owner,permissions=['project:archive:view','project:archive:edit','project:archive:maintain'])
  response=self.client.post(f'/api/projects/archives/{self.archive.id}/maintenance/preview',json={'updates':{'quantity':'0.5'},'expected_version':self.snapshot()['change_version']})
  self.assertEqual(response.status_code,422,response.text)
  self.assertIn('quantity',response.text)
 def test_unchanged_legacy_negative_can_edit_customer_then_correct_with_audit_without_erp(self):
  from app.schemas.project import ArchiveUpdate
  from app.services.project import apply_archive_updates
  self.archive.quantity=Decimal('-1');self.db.commit()
  apply_archive_updates(self.db,self.archive.id,ArchiveUpdate(customer='合法维护',quantity='-1'),self.head.id,scope_context=self.ctx)
  self.assertEqual(self.archive.quantity,Decimal('-1'))
  apply_archive_updates(self.db,self.archive.id,ArchiveUpdate(quantity=1),self.head.id,scope_context=self.ctx)
  self.assertEqual(self.archive.quantity,1)
  log=self.db.query(SysOperationLog).order_by(SysOperationLog.id.desc()).first()
  self.assertEqual(json.loads(log.diff_data)['quantity'],{'before':-1.0,'after':1.0})
  self.assertEqual(self.db.query(ErpSyncTask).count(),0)
 def test_positive_decimal_integer_accepted_by_shared_rule(self):
  for value in (1,Decimal('2.00000000'),Decimal('999999999999')):
   validate_business_field_write(self.db,MODULE_PROJECT_ARCHIVE,current_values={'quantity':1},updates={'quantity':value},entity_created_at=self.archive.created_at,is_create=False,entity_governance_legacy=True)

class QuantityImport(unittest.TestCase):
 setUp=imports.ImportContract.setUp
 tearDown=imports.ImportContract.tearDown
 def test_import_preflight_rejects_negative_zero_and_fraction_with_row(self):
  from app.services.offline_archive_import import preview_import
  for value in ('-1','0','2.5'):
   self.payload['rows'][0]['values']['quantity']=value
   result=preview_import(self.db,self.payload,self.scope)
   self.assertTrue(result['errors'],result)
   self.assertTrue(any(e.get('source_id')=='S1-R2' and e.get('field')=='quantity' for e in result['errors']))
 def test_invalid_quantity_import_does_not_write_partial_rows(self):
  from app.services.offline_archive_import import apply_import
  from app.models.project import PmsProjectArchive
  self.payload['rows'][0]['values']['quantity']='-1'
  with self.assertRaises(HTTPException):apply_import(self.db,self.payload,self.uid,self.scope)
  self.assertEqual(self.db.query(PmsProjectArchive).count(),0)
if __name__=='__main__':unittest.main()
