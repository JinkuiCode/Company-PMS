"""Authenticated v1.4.0 publication and one bounded delivery pass; no grants/restart."""
from pathlib import Path
import json,os,sys

def publish_current(db,actor_id,manifest,receipt,*,verify_actor,expected_users,record):
 from app.services import releases
 from app.models.user import SysUser
 from app.services.authorization import build_authorization_context,enforce_permission
 if verify_actor()!=actor_id:raise RuntimeError('Authenticated actor differs')
 context=build_authorization_context(db,actor_id);enforce_permission(context,'system:release:publish')
 if manifest['version']!='v1.4.0' or [r.version for r in db.query(releases.PmsRelease).order_by(releases.PmsRelease.id)]!=['v1.0.2','v1.1.0','v1.2.0','v1.2.1','v1.3.0']:raise RuntimeError('Release ledger differs; inspect, do not repeat')
 if db.query(SysUser).filter_by(status=1).count()!=expected_users:raise RuntimeError('Audience changed')
 row=releases.publish_release(db,context,manifest,receipt)
 record(phase='published',release_id=row.id,version=row.version)
 return row

def deliver_current_release(db,release_id,*,expected_users,record):
 from app.models.release import PmsReleaseMail as Mail,PmsReleaseNotice,PmsRelease
 from app.services import release_mail
 from unittest.mock import patch
 release=db.get(PmsRelease,release_id)
 if not release or release.version!='v1.4.0':raise RuntimeError('Wrong mail release')
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
  if len(mail)!=1 or mail[0].id not in ids or str(message['Message-ID'])!=f'<pms-release-{release_id}-{mail[0].id}@{config["sender"].split("@")[-1]}>' or not str(message['Subject']).startswith('PMS升级通知 v1.4.0：'):raise RuntimeError('Unexpected outgoing release message')
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


BUILD = 'eae4b05e3eb56a6be1621c3e2e718f530fc3edd9'
SCHEMA = '2026-10-21-archive-policy-01'
ROOT = Path('C:/PMS')
RELEASE_DIR = ROOT / '.runtime/combined-09178b1-formal-20261025'
HERE = RELEASE_DIR / 'v140-notification-20261027'


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def evidence_manifest(manifest, accepted, closed):
    require(manifest['commit'] == BUILD and manifest['version'] == 'v1.4.0'
            and manifest['database_revision'] == SCHEMA, 'runtime-manifest-differs')
    require(accepted.get('passed') is True and accepted.get('candidate') == BUILD
            and accepted.get('version') == 'v1.4.0' and closed.get('passed') is True
            and closed.get('candidate') == BUILD and closed.get('version') == 'v1.4.0'
            and closed.get('database_revision') == SCHEMA
            and closed.get('tasks_original_definition_and_state_restored') is True,
            'production-acceptance-incomplete')


def main():
    import argparse, getpass, hashlib, re, subprocess, time, urllib.request
    from datetime import datetime, timezone
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['preflight', 'publish'])
    args = parser.parse_args()
    require(os.name == 'nt' and Path(__file__).resolve().parent == HERE,
            'formal-tool-directory-differs')
    cfg = json.loads((ROOT/'ops/windows/pms-operations.json').read_text(encoding='utf-8-sig'))
    require(Path(cfg['installRoot']).resolve() == ROOT.resolve(), 'installation-root-differs')
    os.environ['PMS_CONFIG_FILE'] = cfg['protectedConfig']
    os.environ['PMS_RELEASE_MANIFEST'] = str(ROOT/'release.json')
    sys.path.insert(0, str(ROOT/'backend'))
    from app.core.config import settings, validate_runtime_config
    from app.core.database import SessionLocal, engine
    from app.models.database_revision import PmsDatabaseRevision
    from app.models.user import SysUser
    from app.models.release import PmsRelease, PmsReleaseNotice, PmsReleaseMail
    from app.services.runtime_release import load_runtime_manifest, manifest_digest
    from app.services.authorization import build_authorization_context, enforce_permission, authenticate_session
    from app.services.feedback_mail import configuration
    from app.services.auth import login
    from app.schemas.user import LoginRequest
    from fastapi.security import HTTPAuthorizationCredentials
    validate_runtime_config(settings)
    require(settings.PMS_ENV == 'production' and settings.DB_HOST == '10.10.1.230'
            and settings.DB_NAME == 'PMS', 'database-target-differs')
    proof = RELEASE_DIR/'simple-continuation-20261027-r5'
    accepted = json.loads((proof/'ai-acceptance.json').read_text(encoding='utf-8-sig'))
    closed = json.loads((proof/'closeout-complete.json').read_text(encoding='utf-8-sig'))
    manifest = load_runtime_manifest()
    evidence_manifest(manifest, accepted, closed)
    expected_manifest = json.loads((HERE/'release.json').read_text(encoding='utf-8'))
    require(manifest_digest(manifest) == manifest_digest(expected_manifest), 'fixed-notice-differs')
    protected = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                 [Path(cfg['protectedConfig']), ROOT/'release.json', ROOT/'ops/windows/pms-operations.json']}
    def verify_runtime():
        for name, pin in protected.items():
            require(hashlib.sha256(Path(name).read_bytes()).hexdigest() == pin, 'runtime-file-changed')
        script = "$p=Get-Process -Id 7204 -ErrorAction Stop;$p.StartTime.ToUniversalTime().ToString('o')"
        value = subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
            timeout=15, stderr=subprocess.PIPE).decode('ascii').strip()
        require(value.startswith('2026-10-27T01:16:16'), 'accepted-process-changed')
        with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=8) as response:
            require(json.load(response) == {'status':'ok'}, 'health-failed')
    state = {}
    log = HERE/'publication-state.json'
    def record(**values):
        state.update(values)
        log.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        print('V140 '+values['phase'], flush=True)
    token = None
    try:
        verify_runtime()
        with SessionLocal() as db:
            require(db.get(PmsDatabaseRevision,1).revision == SCHEMA, 'schema-differs')
            require([r.version for r in db.query(PmsRelease).order_by(PmsRelease.id)] ==
                    ['v1.0.2','v1.1.0','v1.2.0','v1.2.1','v1.3.0'], 'release-already-present-or-ledger-changed')
            require(not db.query(PmsReleaseMail).filter(PmsReleaseMail.status.notin_(['accepted','failed'])).count(),
                    'existing-mail-needs-review')
            require(configuration(db) is not None, 'mail-config-not-ready')
            actor = db.query(SysUser).filter_by(username='ael',status=1).one()
            context = build_authorization_context(db, actor.id)
            enforce_permission(context, 'system:release:publish')
            users = db.query(SysUser).filter_by(status=1).all()
            expected = len(users)
            require(0 < expected <= 100, 'audience-outside-bounded-pass')
            print('V140_PREFLIGHT '+json.dumps(dict(version='v1.4.0',enabled_users=expected,
                valid_mailboxes=sum(bool(re.fullmatch(r'[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+',(u.email or '').strip())) for u in users),
                changes=len(manifest['changes']),published=False,permission_verified=True)), flush=True)
            if args.action == 'preflight':
                return
            with log.open('x', encoding='utf-8') as stream:
                json.dump({'phase':'awaiting-publisher-identity'}, stream)
            try:
                password = getpass.getpass('PMS ael password (hidden): ')
                try:
                    token = login(db, LoginRequest(username='ael',password=password,remember_me=False)).access_token
                finally:
                    password = None
                def verify_actor():
                    return authenticate_session(HTTPAuthorizationCredentials(scheme='Bearer',credentials=token),db)['user_id']
                verify_runtime()
                receipt = dict(manifest_sha256=manifest_digest(manifest),accepted=True,
                    validated_at=datetime.fromtimestamp(closed['completed_at'],timezone.utc).isoformat())
                row = publish_current(db,actor.id,manifest,receipt,verify_actor=verify_actor,expected_users=expected,record=record)
                require(db.query(PmsReleaseNotice).filter_by(release_id=row.id).count()==expected,'notice-count-differs')
                counts = deliver_current_release(db,row.id,expected_users=expected,record=record)
                db.expire_all()
                require(build_authorization_context(db,actor.id)==context,'authorization-changed')
                verify_runtime()
                record(phase='publication-and-mail-complete',version='v1.4.0',release_id=row.id,
                    notices=expected,mail_counts=counts,manifest_sha256=manifest_digest(manifest),
                    no_restart_or_configuration_change=True,permissions_unchanged=True,completed_at=time.time())
                print('V140_COMPLETE '+json.dumps(state),flush=True)
            except Exception as error:
                record(phase='publication-stopped',error_type=type(error).__name__)
                raise
    finally:
        token = None
        engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('V140_STOPPED '+type(error).__name__+(' '+str(error) if type(error) is RuntimeError else '')+'; preserve state; no automatic retry',flush=True)
        raise SystemExit(1)
