"""Revision 02 is explicit, preserves history, installs no grants and rolls back."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import governance_upgrade_contract as fixtures
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import mssql

class ManagementUpgrade(unittest.TestCase):
 def setUp(self):
  self.assertTrue(Path('backend/app/services/form_draft_management_migration.py').exists(),'draft management migration missing')
  from app.services.form_draft_management_migration import upgrade_draft_management,verify_draft_management_structure
  self.upgrade=upgrade_draft_management;self.verify=verify_draft_management_structure
  self.engine=create_engine('sqlite://')
  fixtures.Base.metadata.create_all(self.engine)
  from app.models.form_draft import PmsFormDraft
  self.table=PmsFormDraft.__table__
  with self.engine.begin() as c:
   self.table.drop(c)
   c.exec_driver_sql("INSERT INTO pms_database_revision(id,revision) VALUES(1,'2026-10-15-governance-01')")
   from app.models.rbac import SysMenu
   c.execute(SysMenu.__table__.insert().values(menu_name='档案',menu_type='C',path='/project/archive',permission_code='project:archive:list'))
 def tearDown(self):
  if hasattr(self,'engine'):self.engine.dispose()
 def test_governance_chain_repeat_and_no_grants(self):
  self.upgrade(self.engine);self.upgrade(self.engine)
  from app.services.database_revision import check_database_ready
  check_database_ready(self.engine)
  with self.engine.connect() as c:
   self.assertEqual(c.exec_driver_sql('SELECT COUNT(*) FROM sys_role_menu').scalar(),0)
   self.assertEqual(c.exec_driver_sql("SELECT COUNT(*) FROM sys_menu WHERE permission_code='project:archive:draft:manage'").scalar(),1)
   self.assertEqual(c.exec_driver_sql('SELECT COUNT(*) FROM pms_project_archive').scalar(),0)
 def historical_row(self):
  from app.services.form_draft_migration import upgrade_form_drafts
  upgrade_form_drafts(self.engine)
  with self.engine.begin() as c:
   from app.models.user import SysUser
   c.execute(SysUser.__table__.insert().values(id=1,username='old',real_name='离职用户',password_hash='fixture',status=0))
   c.exec_driver_sql("INSERT INTO pms_form_draft(id,owner_id,resource,payload_json,version,status,created_at,updated_at) VALUES('old',1,'archive-create','{}',3,'deleted','2026-10-01','2026-10-02')")
 def test_original_v1_frozen_unchanged_and_rollback_on_failure(self):
  self.historical_row()
  with self.engine.connect() as c:before=tuple(c.exec_driver_sql('SELECT * FROM pms_form_draft').one())
  with patch('app.services.form_draft_management_migration.verify_draft_management_structure',side_effect=RuntimeError('injected')):
   with self.assertRaisesRegex(RuntimeError,'injected'):self.upgrade(self.engine)
  with self.engine.connect() as c:
   self.assertEqual(tuple(c.exec_driver_sql('SELECT * FROM pms_form_draft').one()),before)
   self.assertNotIn('creator_id',{i['name'] for i in inspect(c).get_columns('pms_form_draft')})
   self.assertEqual(c.exec_driver_sql('SELECT revision FROM pms_database_revision').scalar(),'2026-10-16-form-draft-01')
  self.upgrade(self.engine)
  with self.engine.connect() as c:
   result=c.exec_driver_sql('SELECT * FROM pms_form_draft').mappings().one()
   self.assertNotIn('creator_id',result);self.assertEqual(result['owner_id'],1)
   self.assertEqual(result['version'],3);self.assertEqual(result['status'],'deleted')
   self.assertEqual(result['payload_json'],'{}')
 def test_wrong_marker_and_conflicting_node_rollback(self):
  with self.engine.begin() as c:
   from app.models.rbac import SysMenu
   c.execute(SysMenu.__table__.insert().values(menu_name='坏节点',menu_type='C',permission_code='project:archive:draft:manage'))
  with self.assertRaises(RuntimeError):self.upgrade(self.engine)
  self.assertFalse(inspect(self.engine).has_table('pms_form_draft'))
  with self.engine.begin() as c:c.exec_driver_sql("UPDATE pms_database_revision SET revision='unknown'")
  with self.assertRaises(RuntimeError):self.upgrade(self.engine)
 def test_sql2017_owner_fk_and_no_new_content_columns(self):
  sql=str(CreateTable(self.table).compile(dialect=mssql.dialect()))
  self.assertNotIn('creator_id',sql)
  self.assertIn('FOREIGN KEY(owner_id) REFERENCES sys_user (id)',sql)
 def test_new_admin_templates_do_not_gain_management_implicitly(self):
  from sqlalchemy.orm import Session
  from app.services.role_templates import permission_ids_for_template
  from app.models.rbac import SysMenu
  self.upgrade(self.engine)
  with Session(self.engine) as db:
   node=db.query(SysMenu).filter_by(permission_code='project:archive:draft:manage').one()
   for role in ('admin','business_admin','operator'):self.assertNotIn(node.id,permission_ids_for_template(db,role))
 def test_backup_restore_v2_on_new_copies_source_unchanged(self):
  import tempfile,sqlite3
  from contextlib import closing
  self.assertTrue(Path('backend/app/services/form_draft_management_rehearsal.py').exists(),'management rehearsal missing')
  from app.services.form_draft_management_rehearsal import rehearse
  self.historical_row()
  with tempfile.TemporaryDirectory() as folder:
   source=Path(folder)/'source.db'
   with self.engine.connect() as connection,closing(sqlite3.connect(source)) as target:
    connection.connection.driver_connection.backup(target)
   result=rehearse(source,Path(folder)/'proof')
   self.assertTrue(result['source_unchanged']);self.assertTrue(result['restore_copy_verified'])
   self.assertEqual(result['revision'],'2026-10-16-form-draft-02')
   self.assertEqual(result['drafts_preserved'],1)
   with self.assertRaises(FileExistsError):rehearse(source,Path(folder)/'proof')
 def test_standalone_cli_upgrade_and_rehearsal_ready_without_runtime_init(self):
  import os,subprocess,tempfile,sqlite3
  from contextlib import closing
  from app.services.governance_rehearsal import fingerprint
  with tempfile.TemporaryDirectory() as folder:
   source=Path(folder)/'source.db'
   with self.engine.connect() as connection,closing(sqlite3.connect(source)) as target:
    connection.connection.driver_connection.backup(target)
   env={**os.environ,'PYTHONPATH':str(Path('backend').resolve())+os.pathsep+os.environ.get('PYTHONPATH',''),
        'DB_DIALECT':'sqlite','SQLITE_DB_PATH':str(source),'PMS_ENV':'development'}
   before=fingerprint(source)
   result=subprocess.run([sys.executable,'-B','backend/scripts/rehearse_draft_management.py','--source',str(source),'--output',str(Path(folder)/'proof')],
       env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   self.assertEqual(result.returncode,0,result.stdout);self.assertEqual(fingerprint(source),before)
   # The explicit CLI is the only real-upgrade path; here it targets disposable data.
   result=subprocess.run([sys.executable,'-B','backend/scripts/upgrade_database.py','--draft-management-only'],
       env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   self.assertEqual(result.returncode,0,result.stdout)
   with closing(sqlite3.connect(source)) as connection:
    self.assertEqual(connection.execute('SELECT revision FROM pms_database_revision').fetchone()[0],'2026-10-16-form-draft-02')

if __name__=='__main__':unittest.main()
