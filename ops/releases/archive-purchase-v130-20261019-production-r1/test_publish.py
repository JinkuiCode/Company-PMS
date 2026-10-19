import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
r=Path(__file__).resolve().parents[3];sys.path[:0]=[str(r/'backend/tests'),str(r/'backend'),str(Path(__file__).parent)]
os.environ['PMS_CONFIG_FILE']='/dev/null'
import release_center_contract as f
from app.models.release import PmsRelease,PmsReleaseNotice,PmsReleaseMail
class Closeout(unittest.TestCase):
 actor=f.Releases.actor;tearDown=f.Releases.tearDown
 def setUp(self):
  f.Releases.setUp(self);self.manifest['version']='v1.3.0';self.receipt['manifest_sha256']=f.releases.manifest_digest(self.manifest)
  self.db.add(PmsRelease(version='v1.0.2',title='old',summary='old',content_json='[]',manifest_sha256='0'*64,code_commit='0'*40,build_id='old',database_revision=self.manifest['database_revision'],published_by=self.owner.id));self.db.add(PmsRelease(version='v1.1.0',title='old',summary='old',content_json='[]',manifest_sha256='1'*64,code_commit='1'*40,build_id='old11',database_revision=self.manifest['database_revision'],published_by=self.owner.id));self.db.add(PmsRelease(version='v1.2.0',title='old12',summary='old12',content_json='[]',manifest_sha256='2'*64,code_commit='2'*40,build_id='old12',database_revision=self.manifest['database_revision'],published_by=self.owner.id));self.db.add(PmsRelease(version='v1.2.1',title='old121',summary='old121',content_json='[]',manifest_sha256='3'*64,code_commit='3'*40,build_id='old121',database_revision=self.manifest['database_revision'],published_by=self.owner.id));self.db.commit()
 def helper(self):
  self.assertTrue((Path(__file__).parent/'publish.py').exists(),'Current v1.3.0 helper is not implemented')
  import publish;return publish
 def publish(self,**kw):
  args=dict(verify_actor=lambda:self.owner.id,expected_users=3,record=lambda **kw:None);args.update(kw)
  return self.helper().publish_current(self.db,self.owner.id,self.manifest,self.receipt,**args)
 def test_success_targets_current_manifest_and_enabled_users(self):
  row=self.publish();self.assertEqual(row.version,'v1.3.0');self.assertEqual(self.db.query(PmsRelease).count(),5)
  self.assertEqual(self.db.query(PmsReleaseNotice).count(),3)
  self.assertTrue(all(n.read_at is None for n in self.db.query(PmsReleaseNotice)))
 def test_rejected_identity_audience_receipt_or_permission_never_publishes(self):
  for options in ({'verify_actor':lambda:self.other.id},{'expected_users':4}):
   with self.assertRaises(Exception):self.publish(**options)
  self.receipt['accepted']=False
  with self.assertRaises(Exception):self.publish()
  self.receipt['accepted']=True
  from app.models.rbac import SysRoleMenu,SysUserRole
  role=self.db.query(SysUserRole).filter_by(user_id=self.owner.id).one().role_id
  self.db.query(SysRoleMenu).filter_by(role_id=role).delete();self.db.commit()
  with self.assertRaises(Exception):self.publish()
  self.assertEqual(self.db.query(PmsRelease).count(),4)
 def prepared(self):
  from app.models.user import SysUser
  for u in self.db.query(SysUser):u.email=f'fixture{u.id}@example.invalid'
  self.db.commit();return self.publish()
 def test_bounded_current_delivery_keeps_notices_unread(self):
  row=self.prepared();from app.services import release_mail
  with patch.object(release_mail,'configuration',return_value={'sender':'pms@example.invalid'}),patch.object(release_mail,'send_mail') as send:
   result=self.helper().deliver_current_release(self.db,row.id,expected_users=3,record=lambda **kw:None)
  self.assertEqual(send.call_count,3);self.assertEqual(result,{'accepted':3})
  self.assertTrue(all(n.read_at is None for n in self.db.query(PmsReleaseNotice)))
 def test_other_pending_release_stops_before_any_send(self):
  row=self.prepared();from app.services import release_mail
  prior=self.db.query(PmsRelease).filter_by(version='v1.0.2').one()
  n=PmsReleaseNotice(release_id=prior.id,user_id=self.owner.id);self.db.add(n);self.db.flush();self.db.add(PmsReleaseMail(notice_id=n.id));self.db.commit()
  with patch.object(release_mail,'send_mail') as send:
   with self.assertRaises(RuntimeError):self.helper().deliver_current_release(self.db,row.id,expected_users=3,record=lambda **kw:None)
   send.assert_not_called()
 def test_unknown_delivery_stops_without_retry(self):
  row=self.prepared();from app.services import release_mail
  with patch.object(release_mail,'configuration',return_value={'sender':'pms@example.invalid'}),patch.object(release_mail,'send_mail',side_effect=OSError('fixture')) as send:
   with self.assertRaises(RuntimeError):self.helper().deliver_current_release(self.db,row.id,expected_users=3,record=lambda **kw:None)
  self.assertEqual(send.call_count,1);self.assertEqual(self.db.query(PmsReleaseMail).filter_by(status='unknown').count(),1)
 def test_missing_mailbox_has_result_without_smtp_and_notices_remain(self):
  row=self.publish();from app.services import release_mail
  with patch.object(release_mail,'configuration',return_value={'sender':'pms@example.invalid'}),patch.object(release_mail,'send_mail') as send:
   result=self.helper().deliver_current_release(self.db,row.id,expected_users=3,record=lambda **kw:None)
  send.assert_not_called();self.assertEqual(result,{'failed':3})
  self.assertEqual(self.db.query(PmsReleaseNotice).count(),3)
 def test_retryable_smtp_result_stops_after_one_attempt(self):
  import smtplib
  row=self.prepared();from app.services import release_mail
  with patch.object(release_mail,'configuration',return_value={'sender':'pms@example.invalid'}),patch.object(release_mail,'send_mail',side_effect=smtplib.SMTPResponseException(451,b'fixture')) as send:
   with self.assertRaises(RuntimeError):self.helper().deliver_current_release(self.db,row.id,expected_users=3,record=lambda **kw:None)
  self.assertEqual(send.call_count,1)
if __name__=='__main__':unittest.main()
