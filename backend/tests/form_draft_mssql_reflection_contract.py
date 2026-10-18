"""SQL Server draft check reflection contract; no database connections."""
import os,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(PMS_CONFIG_FILE=os.devnull,PMS_ENV='development',DB_DIALECT='sqlite',SQLITE_DB_PATH=':memory:')
from app.services import form_draft_migration as module

class Inspector:
 default_schema_name='dbo'
 def __init__(self):self.table=module.frozen_v1_table();self.dialect='mssql';self.index_bad=False
 def has_table(self,name):return True
 def get_columns(self,name):return [{'name':c.name,'type':c.type,'nullable':c.nullable} for c in self.table.columns]
 def get_pk_constraint(self,name):return {'constrained_columns':['id']}
 def get_indexes(self,name):return [{'name':'idx_form_draft_owner','unique':self.index_bad,'column_names':['owner_id','resource','status','updated_at']}]
 def get_foreign_keys(self,name):return [{'constrained_columns':['owner_id'],'referred_table':'sys_user','referred_columns':['id']}]
 def get_check_constraints(self,name):
  if self.dialect=='mssql':raise NotImplementedError('real SQLAlchemy MSSQL dialect has no check reflection')
  return [{'name':'ck_form_draft_version','sqltext':'version > 0'},{'name':'ck_form_draft_status','sqltext':"status IN ('active','used','deleted')"}]

class Connection:
 def __init__(self):
  self.dialect=SimpleNamespace(name='mssql');self.calls=[]
  self.rows=[{'name':'ck_form_draft_version','definition':'([version]>(0))','is_disabled':False,'is_not_trusted':False},
             {'name':'ck_form_draft_status','definition':"([status]=N'active' OR [status]=N'used' OR [status]=N'deleted')",'is_disabled':False,'is_not_trusted':False}]
 def execute(self,sql,parameters):
  value=str(sql);self.calls.append((value,parameters))
  assert value.lstrip().upper().startswith('SELECT') and 'sys.check_constraints' in value
  assert parameters=={'schema_name':'dbo','table_name':'pms_form_draft'}
  return SimpleNamespace(mappings=lambda:SimpleNamespace(all=lambda:self.rows))

class Compatibility(unittest.TestCase):
 def setUp(self):self.inspector=Inspector();self.connection=Connection();self.mock=patch.object(module,'inspect',return_value=self.inspector);self.mock.start();self.addCleanup(self.mock.stop)
 def test_sqlserver_checks_are_read_without_unsupported_reflection(self):
  module.verify_form_draft_structure(self.connection)
  self.assertEqual(len(self.connection.calls),1)
 def test_disabled_check_fails_closed(self):
  self.connection.rows[0]['is_disabled']=True
  with self.assertRaisesRegex(RuntimeError,'检查约束'):module.verify_form_draft_structure(self.connection)
 def test_untrusted_check_fails_closed(self):
  self.connection.rows[1]['is_not_trusted']=True
  with self.assertRaisesRegex(RuntimeError,'检查约束'):module.verify_form_draft_structure(self.connection)
 def test_missing_constraint_fails_closed(self):
  self.connection.rows.pop()
  with self.assertRaisesRegex(RuntimeError,'检查约束'):module.verify_form_draft_structure(self.connection)
 def test_relaxed_version_expression_fails_closed(self):
  self.connection.rows[0]['definition']='version >= 0'
  with self.assertRaisesRegex(RuntimeError,'检查约束'):module.verify_form_draft_structure(self.connection)
 def test_extra_status_value_fails_closed(self):
  self.connection.rows[1]['definition']="status IN ('active','used','deleted','other')"
  with self.assertRaisesRegex(RuntimeError,'检查约束'):module.verify_form_draft_structure(self.connection)
 def test_sqlite_stays_on_existing_reflection(self):
  self.connection.dialect.name='sqlite';self.inspector.dialect='sqlite'
  module.verify_form_draft_structure(self.connection);self.assertEqual(self.connection.calls,[])
 def test_other_structure_guards_remain(self):
  self.inspector.index_bad=True
  with self.assertRaisesRegex(RuntimeError,'索引'):module.verify_form_draft_structure(self.connection)

if __name__=='__main__':unittest.main(verbosity=2)
