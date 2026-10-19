"""Approved archive input rules on disposable SQLite, never the ERP directory."""
import json
import unittest
from uuid import uuid4
from form_draft_contract import Drafts
from app.models.dict import SysDict, SysDictItem
from app.models.product_line import SysProductLine
from app.services.field_policy import validate_business_field_write, MODULE_PROJECT_ARCHIVE
from fastapi import HTTPException

class ArchiveFormRules(Drafts):
 def setUp(self):
  super().setUp()
  line=self.db.get(SysProductLine,1);line.organization_id=200292;line.display_name='重命名后仍为8吋Bench'
  for id,org in [(2,499413),(3,4146325),(4,200293)]:
   self.db.add(SysProductLine(id=id,source_key='kingdee',organization_id=org,organization_code=str(org),organization_name='组织',display_name=f'产品线{id}',name_key=f'line-{id}'))
  for code,values in [('archive_machine_model',range(1,17)),('equipment_series',range(1,19)),('archive_quantity_unit',range(1,10))]:
   definition=self.db.query(SysDict).filter_by(dict_code=code).one()
   for value in values:
    if not self.db.query(SysDictItem).filter_by(dict_id=definition.id,item_value=str(value)).first():
     self.db.add(SysDictItem(dict_id=definition.id,item_value=str(value),item_label='台' if code=='archive_quantity_unit' and value==7 else f'选项{value}',sort=value,status=1))
  self.db.commit();self.actor(self.owner,lines=[1,2,3,4])
 def test_category_required_before_draft_write_and_resave(self):
  payload={'project_code':'CATEGORY','project_name':'类别必输','product_line_id':1}
  for category in [None,'']:
   response=self.client.post(self.base,json={'id':str(uuid4()),'payload':{**payload,'archive_category':category}})
   self.assertEqual(response.status_code,422,response.text)
   self.assertIn('archive_category',{f['field_key'] for f in response.json()['detail']['fields']})
  self.assertEqual(self.db.query(self.Model).count(),0)
  row=self.save({'archive_category':2})
  response=self.client.post(self.base,json={'id':row['id'],'expected_version':row['version'],'payload':payload})
  self.assertEqual(response.status_code,422,response.text)
  self.assertEqual(self.client.get(f"{self.base}/{row['id']}").json()['version'],row['version'])
 def test_metadata_uses_authorized_organization_identity_not_names(self):
  self.actor(self.owner,lines=[1,3])
  body=self.client.get('/api/projects/archives/fields').json()['linkage']
  self.assertEqual(body['line_profiles'],{'1':'bench8','3':'single'})
  self.assertEqual(body['profiles']['bench8']['machine_model'],[5,6,7,8,10,11,12])
  self.actor(self.owner,lines=[])
  self.assertEqual(self.client.get('/api/projects/archives/fields').json()['linkage']['line_profiles'],{})
  self.actor(self.owner,permissions=['project:archive:view','business:data:all'],lines=[])
  self.assertEqual(set(self.client.get('/api/projects/archives/fields').json()['linkage']['line_profiles']),{'1','2','3'})
 def test_draft_filter_matches_backend_and_unmapped_values_remain_available(self):
  for line,model,series in [(1,5,6),(2,2,12),(3,1,14),(1,14,1),(2,16,18),(4,1,6)]:
   self.save({'project_code':f'VALID-{line}-{model}','archive_category':2,'product_line_id':line,'machine_model':model,'equipment_series':series})
  for field,value in [('machine_model',2),('equipment_series',14)]:
   response=self.client.post(self.base,json={'id':str(uuid4()),'payload':{'project_code':'INVALID','project_name':'不兼容','product_line_id':1,'archive_category':2,field:value}})
   self.assertEqual(response.status_code,422,response.text)
   self.assertIn(field,{f['field_key'] for f in response.json()['detail']['fields']})
 def test_historical_unrelated_edits_allowed_but_changed_parent_rechecks_children(self):
  from app.services.archive_field_linkage import linkage_errors
  old={'product_line_id':1,'machine_model':2,'equipment_series':14}
  self.assertEqual(linkage_errors(self.db,old,{'project_name':'无关修改'}),[])
  self.assertEqual(linkage_errors(self.db,old,{'machine_model':2}),[])
  self.assertEqual(linkage_errors(self.db,old,{'product_line_id':2,'equipment_series':12}),[])
  errors=linkage_errors(self.db,{'product_line_id':3,'machine_model':1,'equipment_series':14},{'product_line_id':1})
  self.assertEqual({e['field_key'] for e in errors},{'machine_model','equipment_series'})
  kwargs=dict(current_values=old,entity_created_at=self.archive.created_at,is_create=False,entity_governance_legacy=True)
  validate_business_field_write(self.db,MODULE_PROJECT_ARCHIVE,updates={'project_name':'维护'},**kwargs)
  with self.assertRaises(HTTPException) as ctx:
   validate_business_field_write(self.db,MODULE_PROJECT_ARCHIVE,updates={'machine_model':1},**kwargs)
  self.assertEqual(ctx.exception.status_code,422)
  # offline_initial is also the normal edit path's historical compatibility flag;
  # it must never exempt a related-field edit from the relationship rule.
  with self.assertRaises(HTTPException):
   validate_business_field_write(self.db,MODULE_PROJECT_ARCHIVE,updates={'machine_model':1},historical_import=True,**kwargs)
  self.archive.data_origin='offline_initial';self.archive.archive_category=2
  self.archive.machine_model=5;self.archive.equipment_series=6;self.db.commit()
  self.actor(self.head,lines=[1,2,3,4])
  response=self.client.put(f'/api/projects/archives/{self.archive.id}',json={'machine_model':2,'expected_version':self.snapshot()['change_version']})
  self.assertEqual(response.status_code,422,response.text)
  self.assertIn('machine_model',{i['field_key'] for i in response.json()['detail']['fields']})
  self.db.refresh(self.archive);self.assertEqual(self.archive.machine_model,5)
 def test_new_formal_archive_rejects_linkage_and_defaults_operator(self):
  payload={'project_code':'NEW-FORMAL','project_name':'正式','product_line_id':1,'archive_category':2,'machine_model':2,'quantity':1,'quantity_unit':7,'contract_signed_date':'2026-10-01','contract_ship_date':'2026-12-01'}
  response=self.client.post('/api/projects/archives',json=payload)
  self.assertEqual(response.status_code,422,response.text)
  self.assertIn('machine_model',{i['field_key'] for i in response.json()['detail']['fields']})
  payload['machine_model']=5
  response=self.client.post('/api/projects/archives',json=payload)
  self.assertEqual(response.status_code,200,response.text)
  from app.models.project import PmsProjectArchive
  self.assertEqual(self.db.query(PmsProjectArchive).filter_by(project_code='NEW-FORMAL').one().manager_id,self.owner.id)
 def test_unit_priority_preserves_remaining_order_status_and_storage(self):
  from app.services.dict import get_dict_by_code
  definition=self.db.query(SysDict).filter_by(dict_code='archive_quantity_unit').one()
  rows=self.db.query(SysDictItem).filter_by(dict_id=definition.id).order_by(SysDictItem.sort,SysDictItem.id).all()
  before=[(r.id,r.item_value,r.sort,r.status) for r in rows]
  original=[r.item_value for r in rows]
  options=get_dict_by_code(self.db,'archive_quantity_unit')['items']
  self.assertEqual([i['value'] for i in options],['7']+[v for v in original if v!='7'])
  self.assertEqual(before,[(r.id,r.item_value,r.sort,r.status) for r in rows])
  next(r for r in rows if r.item_value=='7').status=0;self.db.commit()
  self.assertNotIn('7',[i['value'] for i in get_dict_by_code(self.db,'archive_quantity_unit')['items']])

if __name__=='__main__':
 names=[name for name in ArchiveFormRules.__dict__ if name.startswith('test_')]
 result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(ArchiveFormRules(name) for name in names))
 raise SystemExit(not result.wasSuccessful())
