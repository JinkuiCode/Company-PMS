"""Authenticated v1.1.0 publication and one bounded delivery pass; no grants/restart."""
from pathlib import Path
import json,os,sys

def publish_current(db,actor_id,manifest,receipt,*,verify_actor,expected_users,record):
 from app.services import releases
 from app.models.user import SysUser
 from app.services.authorization import build_authorization_context,enforce_permission
 if verify_actor()!=actor_id:raise RuntimeError('Authenticated actor differs')
 context=build_authorization_context(db,actor_id);enforce_permission(context,'system:release:publish')
 if manifest['version']!='v1.1.0' or [r.version for r in db.query(releases.PmsRelease).order_by(releases.PmsRelease.id)]!=['v1.0.2']:raise RuntimeError('Release ledger differs; inspect, do not repeat')
 if db.query(SysUser).filter_by(status=1).count()!=expected_users:raise RuntimeError('Audience changed')
 row=releases.publish_release(db,context,manifest,receipt)
 record(phase='published',release_id=row.id,version=row.version)
 return row

def deliver_current_release(db,release_id,*,expected_users,record):
 from app.models.release import PmsReleaseMail as Mail,PmsReleaseNotice,PmsRelease
 from app.services import release_mail
 from unittest.mock import patch
 release=db.get(PmsRelease,release_id)
 if not release or release.version!='v1.1.0':raise RuntimeError('Wrong mail release')
 rows=db.query(Mail).join(PmsReleaseNotice,Mail.notice_id==PmsReleaseNotice.id).filter(PmsReleaseNotice.release_id==release_id).order_by(Mail.id).all()
 if len(rows)!=expected_users or any(r.status!='pending' or r.attempts!=0 for r in rows):raise RuntimeError('Initial mail batch differs; inspect rather than rerun')
 ids={r.id for r in rows};original_send=release_mail.send_mail
 def check_queue():
  db.expire_all()
  active=db.query(Mail).filter(Mail.status.in_(['pending','waiting','processing','unknown'])).all()
  if any(r.id not in ids or r.status!='pending' or r.attempts!=0 for r in active):raise RuntimeError('Unreviewed active mail; stopped')
 def send_guard(config,message,addresses):
  # Before SMTP, prove this exact message belongs to the current approved batch.
  mail=db.query(Mail).filter_by(status='processing').all()
  if len(mail)!=1 or mail[0].id not in ids or str(message['Message-ID'])!=f'<pms-release-{release_id}-{mail[0].id}@{config["sender"].split("@")[-1]}>' or not str(message['Subject']).startswith('PMS升级通知 v1.1.0：'):raise RuntimeError('Unexpected outgoing release message')
  original_send(config,message,addresses)
 check_queue()
 for expected in rows:
  check_queue()
  next_mail=db.query(Mail).filter(Mail.status=='pending').order_by(Mail.id).first()
  if not next_mail or next_mail.id!=expected.id:raise RuntimeError('Delivery order or queue changed')
  with patch.object(release_mail,'send_mail',side_effect=send_guard):
   if not release_mail.process_one(db):raise RuntimeError('No exact queued mail claimed')
  db.refresh(expected)
  record(phase='mail-processed',mail_id=expected.id,status=expected.status,attempts=expected.attempts)
  if expected.status not in ('accepted','failed'):raise RuntimeError('Mail result needs inspection; no automatic retry')
 return {s:sum(r.status==s for r in rows) for s in sorted({r.status for r in rows})}

def main():
 import argparse,getpass,hashlib,re
 parser=argparse.ArgumentParser();parser.add_argument('--approved-publish-and-mail',action='store_true');args=parser.parse_args()
 if not args.approved_publish_and_mail:raise SystemExit('Explicit publication/mail approval required')
 root=Path('C:/PMS');here=Path(__file__).resolve().parent;control=root/'.runtime/archive-draft-cutover-20261018';resume=root/'.runtime/archive-draft-resume-20261018'
 if os.name!='nt' or here!=root/'.runtime/archive-draft-closeout-20261018':raise SystemExit('Wrong host path')
 if hashlib.sha256((control/'cutover.py').read_bytes()).hexdigest()!='9aaaef6e34e5ab81cf9a2ae64f34f60212327c7899c5346d7236ee667147226c':raise SystemExit('Pinned validator changed')
 sys.path.insert(0,str(control));import cutover as c
 c.h.guard_host(__import__('socket').gethostbyname_ex(__import__('socket').gethostname())[2])
 cfg=json.loads((root/'ops/windows/pms-operations.json').read_text(encoding='utf-8-sig'))
 os.environ.update(PMS_CONFIG_FILE=cfg['protectedConfig'],PMS_PURCHASE_CONFIG_FILE=cfg['purchaseConfig'],PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True;sys.path.insert(0,str(root/'backend'))
 from app.core.config import settings,validate_runtime_config
 from app.core.database import SessionLocal,engine
 from app.models.user import SysUser
 from app.models.release import PmsReleaseNotice,PmsReleaseMail
 from app.services.runtime_release import load_runtime_manifest,manifest_digest
 from app.services.database_revision import check_database_ready
 from app.services.authorization import authenticate_session,build_authorization_context
 from app.services.auth import login
 from app.schemas.user import LoginRequest
 from fastapi.security import HTTPAuthorizationCredentials
 import app.models.init_db
 validate_runtime_config(settings);check_database_ready(engine)
 if settings.DB_HOST!='10.10.1.230' or settings.DB_NAME!='PMS' or settings.PMS_ENV!='production':raise RuntimeError('Wrong formal database')
 manifest=load_runtime_manifest();receipt=json.loads((control/'browser-acceptance.json').read_text())
 if manifest['commit']!=c.h.CANDIDATE or manifest['version']!='v1.1.0' or receipt['manifest_sha256']!=manifest_digest(manifest) or not receipt['read_only_acceptance']:raise RuntimeError('Acceptance/build differs')
 accepted=json.loads((resume/'formal-draft-acceptance.json').read_text())
 if accepted['sample']!='PMS-DRAFT-ACCEPT-20261018-001' or accepted['draft_status']!='deleted' or not accepted['all_logs_success']:raise RuntimeError('Formal write acceptance missing')
 expected_process=json.loads((resume/'normal-process.json').read_text());actual=c.Cutover.process(None)
 c.guard_process(expected_process,actual,cfg['pythonExe'])
 if actual['owner_sid']!=expected_process['owner_sid']:raise RuntimeError('Process owner changed')
 _,files=c.h.read_package(control/'candidate.zip')
 for name,data in files.items():
  if name!='SHA256SUMS' and (root/name).read_bytes()!=data:raise RuntimeError('Pinned runtime changed')
 baseline=json.loads((control/'previous-program/backup-manifest.json').read_text())
 if not all(c.h.hashfile(p)==sha for p,sha in baseline['protected'].items()):raise RuntimeError('Protected configuration changed')
 state_path=here/'publication-state.json'
 if state_path.exists():raise RuntimeError('Prior execution state exists; inspect instead of rerun')
 state={}
 def record(**values):
  state.update(values);state_path.write_text(json.dumps(state,indent=2),encoding='utf8');print('V110 '+values['phase'],flush=True)
 token=None
 try:
  with SessionLocal() as db:
   users=db.query(SysUser).filter_by(status=1).all()
   if len(users)!=18 or sum(bool(re.fullmatch(r'[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+',(u.email or '').strip())) for u in users)!=17:raise RuntimeError('Audience differs')
   actor=db.query(SysUser).filter_by(username='ael',status=1).one()
   approved=json.loads((control/'authorization-after-closeout.json').read_text())
   if not approved['data_scope_preserved'] or approved['user']!='ael':raise RuntimeError('Approved authorization evidence missing')
   from app.services.feedback_mail import configuration
   if not configuration(db):raise RuntimeError('Mail configuration not ready')
   if db.query(PmsReleaseMail).filter(PmsReleaseMail.status.notin_(['accepted','failed'])).count():raise RuntimeError('Unreviewed existing mail')
   record(phase='preflight-verified')
   token=login(db,LoginRequest(username='ael',password=getpass.getpass('PMS ael password (hidden): '),remember_me=False)).access_token
   def verify_actor():return authenticate_session(HTTPAuthorizationCredentials(scheme='Bearer',credentials=token),db)['user_id']
   row=publish_current(db,actor.id,manifest,receipt,verify_actor=verify_actor,expected_users=18,record=record)
   if db.query(PmsReleaseNotice).filter_by(release_id=row.id).count()!=18:raise RuntimeError('Notice audience differs')
   counts=deliver_current_release(db,row.id,expected_users=18,record=record)
   if counts!={'accepted':17,'failed':1}:raise RuntimeError('Mail result requires review')
   record(phase='publication-and-mail-complete',notices=18,mail_counts=counts,long_term_permissions_retained=True,no_restart_or_configuration_change=True)
   print('V110_PUBLISHED '+json.dumps(state),flush=True)
 except Exception as error:
  record(phase='publication-stopped',error_type=type(error).__name__);print('V110_STOPPED; preserve state and do not retry automatically',flush=True);raise SystemExit(1)
 finally:
  token=None;engine.dispose()
if __name__=='__main__':main()
