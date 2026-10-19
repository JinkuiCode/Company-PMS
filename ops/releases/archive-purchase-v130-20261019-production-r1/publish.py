"""Authenticated v1.3.0 publication and one bounded delivery pass; no grants/restart."""
from pathlib import Path
import json,os,sys

def publish_current(db,actor_id,manifest,receipt,*,verify_actor,expected_users,record):
 from app.services import releases
 from app.models.user import SysUser
 from app.services.authorization import build_authorization_context,enforce_permission
 if verify_actor()!=actor_id:raise RuntimeError('Authenticated actor differs')
 context=build_authorization_context(db,actor_id);enforce_permission(context,'system:release:publish')
 if manifest['version']!='v1.3.0' or [r.version for r in db.query(releases.PmsRelease).order_by(releases.PmsRelease.id)]!=['v1.0.2','v1.1.0','v1.2.0','v1.2.1']:raise RuntimeError('Release ledger differs; inspect, do not repeat')
 if db.query(SysUser).filter_by(status=1).count()!=expected_users:raise RuntimeError('Audience changed')
 row=releases.publish_release(db,context,manifest,receipt)
 record(phase='published',release_id=row.id,version=row.version)
 return row

def deliver_current_release(db,release_id,*,expected_users,record):
 from app.models.release import PmsReleaseMail as Mail,PmsReleaseNotice,PmsRelease
 from app.services import release_mail
 from unittest.mock import patch
 release=db.get(PmsRelease,release_id)
 if not release or release.version!='v1.3.0':raise RuntimeError('Wrong mail release')
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
  if len(mail)!=1 or mail[0].id not in ids or str(message['Message-ID'])!=f'<pms-release-{release_id}-{mail[0].id}@{config["sender"].split("@")[-1]}>' or not str(message['Subject']).startswith('PMS升级通知 v1.3.0：'):raise RuntimeError('Unexpected outgoing release message')
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


import subprocess
from pathlib import PurePosixPath
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True,stderr=subprocess.PIPE).strip()
def guard_paths(paths,fixed,allowed):
 for name in paths:
  p=PurePosixPath(name)
  if p.is_absolute() or '..' in p.parts or name in fixed or name not in allowed:raise RuntimeError('Refusing runtime or out-of-scope checkout changes')
def synchronize_checkout(root,bundle,baseline,target,fixed,allowed):
 if git(root,'rev-parse','HEAD')!=baseline or git(root,'status','--porcelain') not in ('','?? release.json'):raise RuntimeError('Checkout drifted')
 if subprocess.run(['git','-C',str(root),'symbolic-ref','-q','HEAD'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:raise RuntimeError('Expected detached release checkout')
 if 'branch refs/heads/master' in git(root,'worktree','list','--porcelain'):raise RuntimeError('Master already checked out')
 git(root,'bundle','verify',str(bundle));git(root,'fetch',str(bundle),'refs/heads/master')
 if git(root,'rev-parse','FETCH_HEAD')!=target:raise RuntimeError('Bundle target mismatch')
 git(root,'merge-base','--is-ancestor',baseline,target)
 paths=git(root,'diff','--name-only',baseline,target).splitlines();guard_paths(paths,fixed,allowed)
 try:old=git(root,'rev-parse','--verify','refs/heads/master')
 except subprocess.CalledProcessError:old='0'*40
 if old!='0'*40:git(root,'merge-base','--is-ancestor',old,target)
 git(root,'update-ref','-m','Approved v1.3.0 source alignment','refs/heads/master',target,old)
 git(root,'-c','core.autocrlf=false','-c','core.eol=lf','switch','master')
 if git(root,'rev-parse','HEAD')!=target or git(root,'status','--porcelain') not in ('','?? release.json'):raise RuntimeError('Checkout verification failed')
 return paths


BUILD='5c5baea86c6abbc3d0dddc9f3d7bfaea53f11997'
APPROVAL='conversation:call_2953949e83114a4e99aafadee3a060d4'

def validate_evidence(state,acceptance,manifest):
 checks={'version_and_guides','archive_draft_required','archive_defaults_unit','archive_linkage','archive_historical_display','purchase_eligibility','purchase_query_conditions'}
 if not(state.get('phase')=='normal-runtime-restored' and state.get('normal_runtime_restored') is True and state.get('browser_accepted') is True and state.get('version_mail_environment_value')=='false'):raise RuntimeError('Normal formal acceptance incomplete')
 if manifest.get('commit')!=BUILD or manifest.get('version')!='v1.3.0' or state.get('commit')!=BUILD or acceptance.get('commit')!=BUILD:raise RuntimeError('Build or acceptance differs')
 if acceptance.get('accepted') is not True or set(acceptance.get('checks',{}))!=checks or not all(v is True for v in acceptance['checks'].values()):raise RuntimeError('Browser acceptance incomplete')

def main():
 import argparse,getpass,hashlib,re
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['publish']);parser.add_argument('--approval',required=True);args=parser.parse_args()
 root=Path('C:/PMS');here=Path(__file__).resolve().parent
 if os.name!='nt' or here!=root/'.runtime/archive-purchase-v130-20261019-production-r1' or args.approval!=APPROVAL:raise RuntimeError('Explicit approval or formal host directory differs')
 if hashlib.sha256((here/'windows_update.py').read_bytes()).hexdigest()!='bc2aa2e1f850851337d96dcc16c040a0ac7d8c7e69ebfca1d073c7e7e8a090d2':raise RuntimeError('Pinned runtime validator differs')
 import windows_update as w
 c=w.WindowsUpdate(w.load_pins()['formal_window_approval'])
 try:
  from app.services.runtime_release import load_runtime_manifest,manifest_digest
  from app.core.database import SessionLocal
  from app.models.user import SysUser
  from app.models.release import PmsRelease,PmsReleaseNotice,PmsReleaseMail
  from app.services.authorization import authenticate_session,build_authorization_context,enforce_permission
  from app.services.auth import login
  from app.schemas.user import LoginRequest
  from fastapi.security import HTTPAuthorizationCredentials
  manifest=load_runtime_manifest();acceptance=json.loads((here/'browser-acceptance.json').read_text(encoding='utf-8'))
  validate_evidence(c.state,acceptance,manifest)
  import resume
  resume.guard_acceptance(acceptance,c.pins,c.state['controlled_pid'])
  before=w.process();w.verify_process(before,c.state['normal_process'],c.cfg['pythonExe'])
  payload=w.u.read_package(here/'candidate.zip',c.pins)
  fixed={name for name in payload if name.startswith(('backend/','ops/windows/','frontend/dist/')) or name=='release.json'}
  def verify_runtime():
   c.files.config_guard()
   for name in fixed:
    if (root/name).read_bytes()!=payload[name]:raise RuntimeError('Installed runtime bytes differ')
   if w.u.tree(root/'frontend/dist')!={n[len('frontend/dist/'):]:w.u.digest(payload[n]) for n in fixed if n.startswith('frontend/dist/')}:raise RuntimeError('Frontend tree differs')
   if w.process()!=before:raise RuntimeError('Normal process changed')
   with c.engine.connect() as con:
    if con.execute(c.text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one()!=c.pins['schema']:raise RuntimeError('Database schema differs')
   with c.opener.open('http://127.0.0.1:8000/api/health',timeout=8) as r:
    if json.load(r).get('status')!='ok':raise RuntimeError('Normal health failed')
  verify_runtime()
  if git(root,'rev-parse','HEAD')!=BUILD:raise RuntimeError('Source build differs')
  state_path=here/'v130-publication-state.json'
  if state_path.exists():raise RuntimeError('Prior publication state exists; inspect, do not repeat')
  state={}
  def record(**values):
   state.update(values);state_path.write_text(json.dumps(state,indent=2),encoding='utf-8');print('V130 '+values['phase'],flush=True)
  token=None
  try:
   with SessionLocal() as db:
    users=db.query(SysUser).filter_by(status=1).all();expected=len(users)
    actor=db.query(SysUser).filter_by(username='ael',status=1).one()
    context=build_authorization_context(db,actor.id);enforce_permission(context,'system:release:publish')
    from app.services.feedback_mail import configuration
    if not configuration(db) or db.query(PmsReleaseMail).filter(PmsReleaseMail.status.notin_(['accepted','failed'])).count():raise RuntimeError('Mail configuration or existing queue requires review')
    if [r.version for r in db.query(PmsRelease).order_by(PmsRelease.id)]!=['v1.0.2','v1.1.0','v1.2.0','v1.2.1']:raise RuntimeError('Release ledger drift')
    receipt={'manifest_sha256':manifest_digest(manifest),'accepted':True,'validated_at':acceptance['verified_at']}
    record(phase='preflight-verified',version='v1.3.0',enabled_users=expected,valid_mailboxes=sum(bool(re.fullmatch(r'[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+',(u.email or '').strip())) for u in users))
    token=login(db,LoginRequest(username='ael',password=getpass.getpass('PMS ael password (hidden): '),remember_me=False)).access_token
    def verify_actor():return authenticate_session(HTTPAuthorizationCredentials(scheme='Bearer',credentials=token),db)['user_id']
    verify_runtime()
    row=publish_current(db,actor.id,manifest,receipt,verify_actor=verify_actor,expected_users=expected,record=record)
    if db.query(PmsReleaseNotice).filter_by(release_id=row.id).count()!=expected:raise RuntimeError('Notice count differs')
    counts=deliver_current_release(db,row.id,expected_users=expected,record=record)
    db.expire_all()
    if build_authorization_context(db,actor.id)!=context:raise RuntimeError('Authorization changed')
    # Users may explicitly read a live notice during delivery; this helper never marks it read.
    verify_runtime()
    record(phase='publication-and-mail-complete',release_id=row.id,notices=expected,mail_counts=counts,no_restart_or_configuration_change=True,permissions_unchanged=True)
    print('V130_PUBLISHED '+json.dumps(state),flush=True)
  except Exception as error:
   record(phase='publication-stopped',error_type=type(error).__name__);print('V130_STOPPED; preserve state, no automatic retry',flush=True);raise
  finally:token=None
 finally:c.engine.dispose()

if __name__=='__main__':
 try:main()
 except Exception as error:print('CLOSEOUT_STOPPED '+type(error).__name__+'; preserve evidence; no automatic retry',flush=True);raise SystemExit(1)
