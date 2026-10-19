"""Resume normal PMS only after separately approved, actual browser acceptance."""
import argparse,json,os,subprocess
from pathlib import Path
import windows_update as w
import program_update as u
CHECKS={'version_and_guide','feedback_person_names','audit_person_names','archive_read'}

def normal_environment(source):
    env=source.copy()
    for key in ('PYTHONPATH','ERP_SYNC_WORKER_ENABLED'):env.pop(key,None)
    env['PMS_RELEASE_MAIL_WORKER_ENABLED']='false'
    return env

def guard_acceptance(value,pins,pid):
    u.check(value.get('commit')==pins['commit'] and value.get('archive_sha256')==pins['archive_sha256'] and value.get('controlled_pid')==pid,'Acceptance target differs')
    u.check(value.get('accepted') is True and bool(value.get('verified_at')) and bool(value.get('verified_by')) and set(value.get('checks',{}))==CHECKS and all(v is True for v in value['checks'].values()),'Actual complete browser acceptance required')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--approved-window-reference',required=True);args=parser.parse_args();c=None
    try:
        c=w.WindowsUpdate(args.approved_window_reference);c.approval()
        u.check(c.state.get('phase')=='awaiting-browser-acceptance','Unexpected maintenance phase')
        guard_acceptance(json.loads((w.HERE/'browser-acceptance.json').read_text()),c.pins,c.state['controlled_pid'])
        c.verify();c.files.config_guard()
        with c.engine.connect() as con:
            for table,statuses in [('erp_sync_task',"'queued','running','review'"),('pms_report_export_job',"'queued','running'"),('pms_feedback_notification',"'pending','waiting','processing'"),('pms_release_mail',"'pending','waiting','processing'")]:
                u.check(con.execute(c.text('SELECT COUNT(*) FROM '+table+' WHERE status IN ('+statuses+')')).scalar_one()==0,'Work appeared during acceptance; review before resume')
        c.stop_controlled();c.files.verify_installed()
        env=normal_environment(os.environ)
        with (w.HERE/'normal-stdout.log').open('xb') as out,(w.HERE/'normal-stderr.log').open('xb') as err:
            result=subprocess.run(['powershell.exe','-NoProfile','-File',str(w.ROOT/'ops/windows/Start-Pms.ps1')],cwd=w.ROOT,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=90)
        env.clear();u.check(result.returncode==0,'Normal PMS startup failed; preserve evidence')
        pid=int((Path(c.cfg['dataRoot'])/'pids/backend.pid').read_text().strip());p=w.process()
        u.check(p is not None and p['pid']==pid and p['owner_sid']==c.owner,'Normal process identity differs');w.verify_process(p,p,c.cfg['pythonExe'])
        c.files.verify_installed()
        with c.engine.connect() as con:u.check(con.execute(c.text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one()==c.pins['schema'],'Schema differs on normal resume')
        with c.opener.open('http://127.0.0.1:8000/api/health',timeout=8) as r:u.check(json.load(r).get('status')=='ok','Normal health failed')
        c.record('normal-runtime-restored',normal_process=p,normal_runtime_restored=True,browser_accepted=True,browser_acceptance_sha256=u.hashfile(w.HERE/'browser-acceptance.json'),notifications_published=False,version_mail_environment_value='false')
    except Exception as error:
        if c:c.record('failed-normal-resume',error_type=type(error).__name__)
        print('NORMAL_RESUME_STOPPED '+type(error).__name__+'; preserve evidence; no automatic retry',flush=True);return 1
    finally:
        if c:c.engine.dispose()
    return 0
if __name__=='__main__':raise SystemExit(main())
