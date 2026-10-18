"""Disposable schema only. No configured database is opened."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import governance_upgrade_contract as fixtures
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.schema import CreateTable,CreateIndex
from sqlalchemy.dialects import mssql

class DraftUpgrade(unittest.TestCase):
 def setUp(self):
  self.assertTrue(Path('backend/app/services/form_draft_migration.py').exists(),'persistent draft migration is missing')
  from app.services.form_draft_migration import upgrade_form_drafts,verify_form_draft_structure
  from app.models.form_draft import PmsFormDraft
  self.upgrade=upgrade_form_drafts;self.verify=verify_form_draft_structure;self.table=PmsFormDraft.__table__
  self.engine=create_engine('sqlite://')
  fixtures.Base.metadata.create_all(self.engine)
  with self.engine.begin() as c:
   self.table.drop(c)
   c.exec_driver_sql("INSERT INTO pms_database_revision(id,revision) VALUES(1,'2026-10-15-governance-01')")
 def tearDown(self):
  if hasattr(self,'engine'):self.engine.dispose()
 def test_upgrade_repeat_and_ready_without_grants_or_business_writes(self):
  self.upgrade(self.engine);self.upgrade(self.engine)
  from app.services.database_revision import check_database_ready,DatabaseUpgradeRequired
  with self.engine.connect() as c:self.verify(c)
  with self.assertRaises(DatabaseUpgradeRequired):check_database_ready(self.engine)
  with self.engine.connect() as c:
   self.assertEqual(c.execute(text('SELECT COUNT(*) FROM sys_role_menu')).scalar(),0)
   self.assertEqual(c.execute(text('SELECT COUNT(*) FROM pms_project_archive')).scalar(),0)
 def test_failure_rollback_and_reject_partial_or_fake_marker(self):
  with patch('app.services.form_draft_migration.verify_form_draft_structure',side_effect=RuntimeError('injected')):
   with self.assertRaisesRegex(RuntimeError,'injected'):self.upgrade(self.engine)
  self.assertFalse(inspect(self.engine).has_table(self.table.name))
  with self.engine.begin() as c:c.exec_driver_sql("UPDATE pms_database_revision SET revision='2026-10-16-form-draft-01'")
  with self.assertRaises(RuntimeError):self.upgrade(self.engine)
 def test_reject_wrong_revision(self):
  with self.engine.begin() as c:c.exec_driver_sql("UPDATE pms_database_revision SET revision='unknown'")
  with self.assertRaises(RuntimeError):self.upgrade(self.engine)
 def test_named_but_weakened_checks_and_missing_owner_fk_rejected(self):
  self.upgrade(self.engine)
  with self.engine.begin() as c:
   ddl=c.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='pms_form_draft'")).scalar()
   c.exec_driver_sql('DROP TABLE pms_form_draft')
   c.exec_driver_sql(ddl.replace('version > 0','version > -99999').replace("status IN ('active','used','deleted')","status IS NOT NULL"))
   for index in self.table.indexes:index.create(c)
  with self.assertRaises(RuntimeError):
   with self.engine.connect() as c:self.verify(c)
 def test_backup_restore_rehearsal_isolated_source_unchanged(self):
  import tempfile,sqlite3
  from contextlib import closing
  self.assertTrue(Path('backend/app/services/form_draft_rehearsal.py').exists(),'draft rehearsal is missing')
  from app.services.form_draft_rehearsal import rehearse
  with tempfile.TemporaryDirectory() as folder:
   source=Path(folder)/'synthetic-source.db'
   with self.engine.connect() as c, closing(sqlite3.connect(source)) as target:
    c.connection.driver_connection.backup(target)
   result=rehearse(source,Path(folder)/'rehearsal')
   self.assertTrue(result['source_unchanged'])
   self.assertTrue(result['restore_copy_verified'])
   self.assertEqual(result['revision'],'2026-10-16-form-draft-01')
   with self.assertRaises(FileExistsError):rehearse(source,Path(folder)/'rehearsal')
 def test_fingerprint_closes_read_connection(self):
  import sqlite3
  import app.services.governance_rehearsal as shared
  connection=sqlite3.connect(':memory:')
  with patch.object(shared,'_readonly',return_value=connection):shared.fingerprint('synthetic')
  try:
   with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
  finally:connection.close()
 def test_standalone_rehearsal_cli_loads_foreign_key_models(self):
  import os, subprocess, tempfile, sqlite3
  from contextlib import closing
  from app.services.governance_rehearsal import fingerprint
  with tempfile.TemporaryDirectory() as folder:
   source=Path(folder)/'standalone-source.db'
   with self.engine.connect() as connection, closing(sqlite3.connect(source)) as target:
    connection.connection.driver_connection.backup(target)
   before=fingerprint(source)
   result=subprocess.run([sys.executable,'-B','backend/scripts/rehearse_form_drafts.py','--source',str(source),'--output',str(Path(folder)/'rehearsal')],
                         cwd=Path(__file__).resolve().parents[2],env={**os.environ,'SQLITE_DB_PATH':str(Path(folder)/'unused.db')},
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   self.assertEqual(result.returncode,0,result.stdout)
   self.assertEqual(fingerprint(source),before)
   self.assertEqual(fingerprint(Path(folder)/'rehearsal/restored.db'),before)
   ready=subprocess.run([sys.executable,'-B','-c','from app.core.database import engine; from app.services.form_draft_migration import verify_form_draft_structure; c=engine.connect(); verify_form_draft_structure(c); c.close(); engine.dispose()'],
                        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])+os.pathsep+os.environ.get('PYTHONPATH',''),
                             'DB_DIALECT':'sqlite','SQLITE_DB_PATH':str(Path(folder)/'rehearsal/upgraded.db')},
                        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   self.assertEqual(ready.returncode,0,ready.stdout)
 def test_sql2017_structure_compile(self):
  sql=str(CreateTable(self.table).compile(dialect=mssql.dialect()))
  self.assertIn('NVARCHAR(max)',sql)
  for index in self.table.indexes:self.assertTrue(str(CreateIndex(index).compile(dialect=mssql.dialect())))
if __name__=='__main__':unittest.main()
