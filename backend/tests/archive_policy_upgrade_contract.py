"""A1 bounded data-only migration, disposable databases only."""
import os,sys,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
from sqlalchemy import create_engine,select,inspect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['DB_DIALECT']='sqlite'
os.environ['SQLITE_DB_PATH']=str(Path(tempfile.mkdtemp())/'unused.db')
import app.models.init_db
from app.core.database import Base
from app.models.database_revision import PmsDatabaseRevision
from app.models.field_policy import SysBusinessFieldPolicy as Policy
from app.models.dict import SysDict,SysDictItem
from app.models.rbac import SysMenu
from sqlalchemy.orm import Session

class PolicyUpgrade(unittest.TestCase):
 def setUp(self):
  self.assertTrue(Path('backend/app/services/archive_policy_revision_migration.py').exists(),'bounded policy migration is missing')
  import app.services.archive_policy_revision_migration as migration
  self.migration=migration;self.engine=create_engine('sqlite://')
  Base.metadata.create_all(self.engine)
  with self.engine.begin() as c:
   c.execute(PmsDatabaseRevision.__table__.insert().values(id=1,revision=migration.PREVIOUS))
   c.execute(SysMenu.__table__.insert().values(id=22,menu_name='档案',menu_type='C',path='/project/archive',permission_code='project:archive:list'))
   c.execute(SysMenu.__table__.insert().values(parent_id=22,menu_name='草稿管理',menu_type='B',permission_code='project:archive:draft:manage'))
   c.execute(SysDict.__table__.insert().values(id=1,dict_code='archive_quantity_unit',dict_name='单位',table_name='pms_project_archive',field_name='quantity_unit',status=1,next_value=12))
   c.execute(SysDictItem.__table__.insert().values(id=8,dict_id=1,item_value='7',item_label='台',sort=28,status=1))
   c.execute(SysDictItem.__table__.insert().values(id=9,dict_id=1,item_value='8',item_label='套',sort=2,status=0))
   from app.services.archive_governance_migration import install_archive_governance
   db=Session(bind=c);install_archive_governance(db);db.close()
   from app.models.operation_log import SysOperationLog
   c.execute(SysOperationLog.__table__.insert().values(module='项目档案',action='create',entity_type='pms_project_archive',entity_id='1',status='success',summary='合成历史日志',after_data='{"quantity_unit":7}',diff_items_data='[{"field_key":"quantity_unit","after_display":"台"}]'))
   for key in ('contract_signed_date','contract_ship_date','customer','sales_company'):
    c.execute(Policy.__table__.insert().values(module_code='project_archive',field_key=key,visible=True,editable=True,required=True,list_available=True,required_effective_at=datetime(2020,1,1)))
 def tearDown(self):
  if hasattr(self,'engine'):self.engine.dispose()
 def snapshot(self):
  with self.engine.connect() as c:return {t.name:[dict(r) for r in c.execute(select(t)).mappings()] for t in Base.metadata.sorted_tables}
 def test_upgrade_preserves_identity_other_config_cutoffs_and_logs_and_repeat(self):
  before=self.snapshot();result=self.migration.upgrade_archive_policy(self.engine);after=self.snapshot()
  self.assertEqual(result['unit']['before']['item_label'],'台');self.assertEqual(result['unit']['after']['item_label'],'pcs')
  self.assertEqual(result['unit']['before']['id'],result['unit']['after']['id'])
  for table,rows in before.items():
   if table not in ('pms_database_revision','sys_dict_item','sys_business_field_policy'):self.assertEqual(after[table],rows,table)
  for row in before['sys_business_field_policy']:
   actual=next(r for r in after['sys_business_field_policy'] if r['id']==row['id'])
   if row['field_key'] not in self.migration.REQUIRED_VALUES:self.assertEqual(actual,row)
   else:
    self.assertEqual(actual['required'],self.migration.REQUIRED_VALUES[row['field_key']])
    self.assertEqual(actual['required_effective_at'],row['required_effective_at'])
    self.assertEqual({k:v for k,v in actual.items() if k!='required'},{k:v for k,v in row.items() if k!='required'})
  for row in before['sys_dict_item']:
   actual=next(r for r in after['sys_dict_item'] if r['id']==row['id'])
   self.assertEqual({k:v for k,v in actual.items() if k!='item_label'},{k:v for k,v in row.items() if k!='item_label'})
  self.migration.upgrade_archive_policy(self.engine);self.assertEqual(after,self.snapshot())
  from app.services.database_revision import check_database_ready
  check_database_ready(self.engine)
 def test_injected_failure_rolls_back_everything(self):
  before=self.snapshot()
  with patch.object(self.migration,'verify_archive_policy',side_effect=RuntimeError('after-write')):
   with self.assertRaisesRegex(RuntimeError,'after-write'):self.migration.upgrade_archive_policy(self.engine)
  self.assertEqual(before,self.snapshot())
 def test_wrong_marker_disabled_unknown_identity_duplicate_pcs_fail_closed(self):
  for sql in ["UPDATE pms_database_revision SET revision='upgrading'","UPDATE sys_dict_item SET status=0 WHERE id=8","UPDATE sys_dict_item SET item_label='别的单位' WHERE id=8","UPDATE sys_dict SET status=0 WHERE id=1","UPDATE sys_dict_item SET item_label='PCS' WHERE id=9"]:
   with self.subTest(sql=sql):
    with self.engine.begin() as c:c.exec_driver_sql(sql)
    before=self.snapshot()
    with self.assertRaises(RuntimeError):self.migration.upgrade_archive_policy(self.engine)
    self.assertEqual(before,self.snapshot())
    # Fresh synthetic fixture per case, no cleanup of existing data.
    self.engine.dispose();self.setUp()
 def test_already_pcs_keeps_identity_and_target_drift_is_rejected(self):
  with self.engine.begin() as c:c.exec_driver_sql("UPDATE sys_dict_item SET item_label='pcs' WHERE id=8")
  self.migration.upgrade_archive_policy(self.engine)
  with self.engine.begin() as c:c.exec_driver_sql("UPDATE sys_business_field_policy SET required=1 WHERE field_key='quantity'")
  before=self.snapshot()
  with self.assertRaises(RuntimeError):self.migration.upgrade_archive_policy(self.engine)
  self.assertEqual(before,self.snapshot())
 def test_cli_old_modes_reject_before_write_and_new_bounded_mode(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('upgrade_a1',Path('backend/scripts/upgrade_database.py'));cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
  for mode in ('draft_management_only','feedback_only'):
   with patch.object(cli,'validate_runtime_config'),patch.object(cli,'engine',self.engine):
    before=self.snapshot()
    with self.assertRaises(RuntimeError):cli.upgrade_database(**{mode:True})
    self.assertEqual(before,self.snapshot())
  with patch.object(cli,'validate_runtime_config'),patch.object(cli,'engine',self.engine):cli.upgrade_database(archive_policy_only=True)
  with self.engine.connect() as c:self.assertEqual(c.execute(select(PmsDatabaseRevision.revision)).scalar(),self.migration.REVISION)
 def test_full_explicit_finalizer_same_rules_without_version_forgery(self):
  before=self.snapshot();self.migration.finalize_archive_policy_setup(self.engine)
  with self.engine.connect() as c:
   self.migration.verify_archive_policy(c)
   self.assertEqual(c.execute(select(PmsDatabaseRevision.revision)).scalar(),self.migration.PREVIOUS)
  self.assertEqual(before['sys_role_menu'],self.snapshot()['sys_role_menu'])
 def test_mssql_revision_lock_query_is_parameterized(self):
  from sqlalchemy.dialects import mssql
  sql=str(self.migration.revision_query().compile(dialect=mssql.dialect()))
  self.assertIn('UPDLOCK, HOLDLOCK',sql);self.assertIn(':id_1',sql)

 def test_legitimately_disabled_optional_unit_does_not_block_runtime(self):
  self.migration.upgrade_archive_policy(self.engine)
  with self.engine.begin() as c:c.exec_driver_sql("UPDATE sys_dict_item SET status=0 WHERE id=8")
  from app.services.database_revision import check_database_ready
  check_database_ready(self.engine)
  with self.assertRaises(RuntimeError):self.migration.upgrade_archive_policy(self.engine)

 def test_fake_mssql_full_branch_keeps_parameterization_and_transaction(self):
  from contextlib import contextmanager
  from sqlalchemy.dialects import mssql
  from types import SimpleNamespace
  statements=[]
  class Connection:
   dialect=SimpleNamespace(name='mssql')
   def __init__(self,raw):self.raw=raw
   def execute(self,statement,*args,**kwargs):
    compiled=statement.compile(dialect=mssql.dialect())
    statements.append((str(compiled),compiled.params))
    return self.raw.execute(statement,*args,**kwargs)
  engine=self.engine
  class Engine:
   @contextmanager
   def begin(self):
    with engine.begin() as raw:yield Connection(raw)
  old_draft=self.migration.verify_draft_management_structure;old_archive=self.migration.verify_archive_governance
  with patch.object(self.migration,'verify_draft_management_structure',side_effect=lambda c:old_draft(c.raw)),patch.object(self.migration,'verify_archive_governance',side_effect=lambda c:old_archive(c.raw)):
   self.migration.upgrade_archive_policy(Engine())
  self.assertIn('UPDLOCK, HOLDLOCK',statements[0][0])
  updates=[(sql,params) for sql,params in statements if sql.startswith('UPDATE')]
  self.assertTrue(updates)
  for sql,params in updates:
   self.assertNotIn('pcs',sql);self.assertNotIn(self.migration.REVISION,sql);self.assertTrue(params)
  self.assertEqual(self.snapshot()['pms_database_revision'][0]['revision'],self.migration.REVISION)

 def test_reverse_material_and_backup_copy_restore_old_policy_without_touching_source(self):
  import sqlite3
  from contextlib import closing
  before=self.snapshot()
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'old-backup.db'
   with self.engine.connect() as c,closing(sqlite3.connect(path)) as target:c.connection.driver_connection.backup(target)
   result=self.migration.upgrade_archive_policy(self.engine)
   self.assertEqual({r['id']:r for r in result['policies']['before']},{r['id']:r for r in before['sys_business_field_policy'] if r['field_key'] in self.migration.REQUIRED_VALUES})
   restored=create_engine('sqlite:///'+str(path))
   try:
    with restored.connect() as c:
     self.assertEqual(c.execute(select(PmsDatabaseRevision.revision)).scalar(),self.migration.PREVIOUS)
     self.assertEqual(c.execute(select(SysDictItem.item_label).where(SysDictItem.id==8)).scalar(),'台')
     self.assertEqual([dict(r) for r in c.execute(select(Policy.__table__)).mappings()],before['sys_business_field_policy'])
   finally:restored.dispose()

 def test_legitimate_conditional_required_configuration_does_not_lock_runtime(self):
  self.migration.upgrade_archive_policy(self.engine)
  from app.services.field_policy import update_field_policies
  from app.schemas.field_policy import FieldPolicyBatchUpdate
  from app.services.database_revision import check_database_ready
  with Session(self.engine) as db:
   row=db.query(Policy).filter_by(field_key='equipment_series').one()
   update_field_policies(db,'project_archive',FieldPolicyBatchUpdate(items=[dict(field_key='equipment_series',visible=True,editable=True,required=True,list_available=True,expected_updated_at=row.updated_at)]))
  check_database_ready(self.engine)

 def test_full_mode_rejects_existing_previous_before_any_initializer_or_marker_write(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('upgrade_a1_guard',Path('backend/scripts/upgrade_database.py'));cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
  before=self.snapshot()
  with patch.object(cli,'validate_runtime_config'),patch.object(cli,'engine',self.engine),patch.object(cli,'init_db',side_effect=RuntimeError('unbounded initializer invoked')) as initialize:
   with self.assertRaisesRegex(RuntimeError,'archive-policy-only'):cli.upgrade_database()
   initialize.assert_not_called()
  self.assertEqual(before,self.snapshot())

if __name__=='__main__':unittest.main()
