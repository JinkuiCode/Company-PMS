"""No database/network/credentials: fail-closed rehearsal boundary tests."""
import unittest
from unittest.mock import Mock,patch
from pathlib import Path,PureWindowsPath
import server_rehearsal as r
class RehearsalGuards(unittest.TestCase):
 def test_cannot_point_probe_at_production_or_another_host(self):
  good={'database':'PMS_V130_REHEARSAL_20261019_ab12cd34','source':'PMS','host':'10.10.1.230'}
  r.guard_child(good)
  for change in [{'database':'PMS'},{'database':'master'},{'database':'PMS_V130_REHEARSAL_20261019_x;DROP'},{'source':'Other'},{'host':'10.10.1.149'}]:
   with self.subTest(change=change),self.assertRaises(RuntimeError):r.guard_child({**good,**change})
 def test_only_explicit_isolation_approval_is_accepted(self):
  if r.ISOLATION_APPROVAL is None:
   with self.assertRaises(RuntimeError):r.guard_reference(None)
  else:r.guard_reference(r.ISOLATION_APPROVAL)
  for value in [None,'approved','continue','formal-window-other']:
   with self.subTest(value=value),self.assertRaises(RuntimeError):r.guard_reference(value)
 def test_environment_cannot_inherit_production_or_external_background(self):
  env=r.probe_environment({'PMS_CONFIG_FILE':'private','DB_NAME':'PMS','K3_URL':'url','SSO_ENABLED':'true','ERP_SYNC_WORKER_ENABLED':'true','PMS_RELEASE_MAIL_WORKER_ENABLED':'true','PATH':'keep'})
  self.assertEqual(env['PATH'],'keep');self.assertNotIn('DB_NAME',env);self.assertNotIn('K3_URL',env)
  self.assertEqual(env['ERP_SYNC_WORKER_ENABLED'],'false');self.assertEqual(env['PMS_RELEASE_MAIL_WORKER_ENABLED'],'false');self.assertEqual(env['SSO_ENABLED'],'false')
 def test_drift_after_hidden_input_stops_before_backup(self):
  c=r.Rehearsal.__new__(r.Rehearsal);c.preflight=Mock();c.extract=Mock();c.record=Mock();c.verify_live=Mock(side_effect=RuntimeError('state changed'));c.backup_restore=Mock();c.engine=Mock();c.settings=Mock()
  with patch.object(r,'ISOLATION_APPROVAL','fixture-approval-only'),patch.object(r.getpass,'getpass',side_effect=['fixture-user','fixture-password']),self.assertRaises(RuntimeError):c.execute('fixture-approval-only')
  c.backup_restore.assert_not_called();c.engine.dispose.assert_called_once()
 def test_hidden_input_refuses_getpass_echo_fallback(self):
  import warnings
  def fallback(prompt):warnings.warn('cannot hide fixture input',r.getpass.GetPassWarning);raise AssertionError('must never read fallback input')
  with patch.object(r.getpass,'getpass',side_effect=fallback),self.assertRaises(r.getpass.GetPassWarning):r.hidden_input('fixture prompt')
 def test_private_initializer_matches_r2_work_directory(self):
  source=(Path(__file__).parent/'Initialize-PrivateWorkspace.ps1').read_text()
  self.assertIn('archive-purchase-v130-20261019-r2',source)
  self.assertNotIn("archive-purchase-v130-20261019'",source)
 def test_restores_never_replace_database_or_reuse_files(self):
  base=r.backup_primitives(Path(__file__).resolve().parents[3])
  name=r.PREFIX+'ab12cd34';sql,paths=base.restore_plan('PMS',name,'D:\\Backup\\fresh.bak',[{'Type':'D','FileId':1,'LogicalName':'PMS'},{'Type':'L','FileId':2,'LogicalName':'PMS_log'}],'D:\\Data','E:\\Log')
  self.assertNotIn('REPLACE',sql);self.assertIn('CHECKSUM,RECOVERY',sql)
  for names,used in [([name],[]),([],paths)]:
   with self.assertRaises(RuntimeError):base.ensure_new_target(name,names,paths,used)
if __name__=='__main__':unittest.main()
