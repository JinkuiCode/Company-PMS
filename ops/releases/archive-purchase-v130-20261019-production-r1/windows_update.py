"""Program-only Windows maintenance. Preparation is NOT production approval."""
import argparse,json,os,re,socket,subprocess,sys,time
from pathlib import Path
from urllib.request import build_opener,ProxyHandler
import program_update as u
HERE=Path(__file__).resolve().parent
ROOT=Path('C:/PMS')
PIN_SHA256='ad16e483f0aa62e37abdc901f64ba349a0c9a4bf869b65ca6decbab0808597d0'

def load_pins():
    u.check(u.hashfile(HERE/'pins.json')==PIN_SHA256,'Pinned maintenance identity changed')
    return json.loads((HERE/'pins.json').read_text(encoding='utf-8'))

def guard_acl(metadata,sid):
    allowed={sid,'S-1-5-18','S-1-5-32-544'}
    u.check(metadata.get('protected') is True and metadata.get('reparse') is False and metadata.get('owner') in allowed,'Private directory ACL/owner unverified')
    objects=metadata.get('objects')
    u.check(isinstance(objects,list) and bool(objects),'Recursive per-object ACL evidence missing')
    for item in [metadata,*objects]:
        entries=item.get('entries',[])
        u.check(item.get('owner') in allowed and item.get('reparse') is False,'Private child owner or reparse differs')
        # NULL/empty DACL must fail for EACH object, not disappear in an aggregate.
        u.check(entries and {e.get('sid') for e in entries}==allowed,'Private object ACL is empty or principals differ')
        u.check(all(e.get('allow') is True and e.get('full') is True for e in entries),'Private object access differs')

def require_private_acl(path,sid):
    script="$d=Get-Item -LiteralPath "+literal(path)+" -Force;$a=Get-Acl -LiteralPath $d.FullName;$all=@($d)+@(Get-ChildItem -LiteralPath $d.FullName -Force -Recurse);$objects=@();foreach($i in $all){$acl=Get-Acl -LiteralPath $i.FullName;$entries=@();foreach($r in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){$entries+=@{sid=$r.IdentityReference.Value;allow=($r.AccessControlType -eq 'Allow');full=(($r.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl)-eq [Security.AccessControl.FileSystemRights]::FullControl)}};$objects+=@{owner=($acl.GetOwner([Security.Principal.SecurityIdentifier])).Value;entries=$entries;reparse=(($i.Attributes -band [IO.FileAttributes]::ReparsePoint)-ne 0)}};@{protected=$a.AreAccessRulesProtected;owner=$objects[0].owner;entries=$objects[0].entries;reparse=$objects[0].reparse;objects=$objects}|ConvertTo-Json -Depth 6 -Compress"
    guard_acl(json.loads(ps(script)),sid)

def guard_host(os_name,root,work,addresses,pins):
    u.check(os_name=='nt' and root==type(root)('C:/PMS') and work==root/'.runtime/archive-purchase-v130-20261019-production-r1' and pins['host'] in addresses,'Wrong Windows host/root/private directory')

def pipeline(controller):
    for step in ('preflight','stage','backup','preflight','stop','install','start','verify'):getattr(controller,step)()

def ps(script):return u.run(['powershell.exe','-NoProfile','-Command',script])
def literal(value):return "'"+str(value).replace("'","''")+"'"

def process():
    raw=ps("$ids=@((Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess|Sort-Object -Unique);if($ids.Count -eq 0){'null';exit};if($ids.Count -ne 1){throw 'Ambiguous listener'};$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$ids[0]);$o=Invoke-CimMethod -InputObject $p -MethodName GetOwnerSid;if($o.ReturnValue -ne 0){throw 'Cannot verify owner'};@{pid=$p.ProcessId;created=$p.CreationDate.ToUniversalTime().ToString('o');executable=$p.ExecutablePath;command=$p.CommandLine;owner_sid=$o.Sid}|ConvertTo-Json -Compress")
    return json.loads(raw)

def verify_process(actual,expected,python,*,launcher=None):
    norm=lambda v:str(v).replace('\\','/').casefold()
    u.check(actual is not None and expected is not None,'PMS listener missing')
    u.check(all(actual.get(k)==expected.get(k) for k in ('pid','created','owner_sid')) and norm(actual.get('executable'))==norm(python),'PMS process identity changed')
    command=actual.get('command','').replace('\\','/').strip()
    def path_pattern(value):
        escaped=re.escape(str(value).replace('\\','/'))
        return '(?i:(?:'+escaped+'|"'+escaped+'"))'
    tail=(r'\s+-B\s+'+path_pattern(launcher)) if launcher else r'\s+-m\s+uvicorn\s+main:app\s+--host\s+127\.0\.0\.1\s+--port\s+8000'
    u.check(re.fullmatch(path_pattern(python)+tail,command) is not None,'Unexpected full PMS command')

def stop_process(expected):
    # No process name, server reboot, SQL service, or arbitrary PID termination.
    ps("$p=Get-CimInstance Win32_Process -Filter 'ProcessId="+str(int(expected['pid']))+"';if(-not $p -or $p.CreationDate.ToUniversalTime().ToString('o') -ne "+literal(expected['created'])+"){throw 'PMS PID reused'};Stop-Process -Id $p.ProcessId;$until=(Get-Date).AddSeconds(20);while(Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue){if((Get-Date)-gt $until){throw 'PMS stop deadline'};Start-Sleep -Milliseconds 250};if(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue){throw 'PMS listener remains'}")

class WindowsUpdate:
    def __init__(self,approval_reference):
        self.pins=load_pins();guard_host(os.name,ROOT,HERE,socket.gethostbyname_ex(socket.gethostname())[2],self.pins)
        u.check(not ROOT.is_symlink() and not HERE.is_symlink(),'Linked Windows directory refused')
        self.reference=approval_reference;self.owner=ps('[Security.Principal.WindowsIdentity]::GetCurrent().User.Value');require_private_acl(HERE,self.owner);self.state_path=HERE/'deployment-state.json'
        self.state=json.loads(self.state_path.read_text(encoding='utf-8')) if self.state_path.exists() else {}
        self.cfg=json.loads((ROOT/'ops/windows/pms-operations.json').read_text(encoding='utf-8-sig'))
        u.check(Path(self.cfg['installRoot'])==ROOT and self.cfg.get('backendPort')==8000 and self.cfg.get('autoRestart') is False,'Unexpected operations config')
        u.check(Path(self.cfg['pythonExe'])==Path(self.pins['python_executable']),'Unexpected PMS interpreter location')
        u.check(Path(self.cfg['pythonExe']).is_file() and (Path(self.cfg['dataRoot'])/'pids').is_dir(),'Runtime paths missing')
        os.environ.update(PMS_CONFIG_FILE=self.cfg['protectedConfig'],PMS_PURCHASE_CONFIG_FILE=self.cfg['purchaseConfig'],PYTHONDONTWRITEBYTECODE='1')
        sys.path.insert(0,str(ROOT/'backend'))
        from app.core.config import settings,validate_runtime_config
        from app.core.database import engine
        from sqlalchemy import text
        validate_runtime_config(settings)
        u.check(settings.PMS_ENV=='production' and settings.DB_HOST==self.pins['sql_host'] and settings.DB_NAME==self.pins['database'],'Wrong runtime SQL settings')
        self.settings,self.engine,self.text=settings,engine,text
        for value in (getattr(settings,'PMS_RELEASE_MANIFEST',''),os.environ.get('PMS_RELEASE_MANIFEST','')):
            u.check(not value or Path(value)==ROOT/'release.json','Custom runtime manifest requires review')
        paths=list(dict.fromkeys([ROOT/'backend/.env.local',ROOT/'ops/windows/pms-operations.json',Path(self.cfg['protectedConfig']),Path(self.cfg['purchaseConfig']),Path('C:/nginx/conf/nginx.conf'),Path('C:/nginx/conf/pms.conf')]))
        self.files=u.ProgramFiles(ROOT,HERE,self.pins,paths)
        # An earlier process's baseline hashes are authoritative after restart.
        if self.state.get('protected'):self.files.protected=self.state['protected']
        self.opener=build_opener(ProxyHandler({}))
    def approval(self):u.check(isinstance(self.pins.get('formal_window_approval'),str) and len(self.pins['formal_window_approval'])>=8 and self.reference==self.pins['formal_window_approval'],'Exact separately approved formal window reference required')
    def record(self,phase,**extra):
        require_private_acl(HERE,self.owner)
        self.state.update(extra,phase=phase,commit=self.pins['commit'],database_modified=False)
        steps=HERE/'steps';steps.mkdir(exist_ok=True);n=len(list(steps.glob('*.json')))
        u.save(steps/(str(n).zfill(3)+'-'+phase+'.json'),self.state)
        temp=HERE/'deployment-state.tmp';u.check(not temp.exists(),'State transaction already present');temp.write_text(json.dumps(self.state,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(self.state_path)
        print('PMS_PROGRAM_PHASE '+phase,flush=True)
    def verify_normal_origin(self,actual):
        receipt_path=ROOT/'.runtime/feedback-reference-v121-20261019/deployment-state.json'
        u.check(u.hashfile(receipt_path)==self.pins['baseline_state_sha256'],'Previous normal startup evidence changed')
        u.check(u.hashfile(ROOT/'ops/windows/Start-Pms.ps1')==self.pins['baseline_start_script_sha256'] and u.hashfile(ROOT/'release.json')==self.pins['baseline_manifest_sha256'],'Trusted startup/runtime source differs')
        state=json.loads(receipt_path.read_text(encoding='utf-8'))
        u.check(state.get('phase')=='normal-runtime-restored' and state.get('normal_runtime_restored') is True and state.get('browser_accepted') is True and state.get('version_mail_environment_value')=='false','Previous release acceptance incomplete')
        verify_process(actual,state.get('normal_process'),self.cfg['pythonExe'])
        u.check(int((Path(self.cfg['dataRoot'])/'pids/backend.pid').read_text(encoding='utf-8').strip())==actual['pid'],'Runtime PID file differs')
    def read_state(self,*,for_rollback=False):
        require_private_acl(HERE,self.owner)
        self.files.config_guard();p=process()
        if p:u.check(p['owner_sid']==self.owner,'Runtime owner differs')
        with self.engine.connect() as con:
            actual=con.execute(self.text('SELECT DB_NAME()')).scalar_one()
            revision=con.execute(self.text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one()
            pending=0
            for table,statuses in [('erp_sync_task',"'queued','running','review'"),('pms_report_export_job',"'queued','running'"),('pms_feedback_notification',"'pending','waiting','processing'"),('pms_release_mail',"'pending','waiting','processing'")]:
                pending+=con.execute(self.text('SELECT COUNT(*) FROM '+table+' WHERE status IN ('+statuses+')')).scalar_one()
        release={} if for_rollback else json.loads((ROOT/'release.json').read_text(encoding='utf-8'))
        if not for_rollback:u.check(release.get('database_revision')==self.pins['schema'],'Runtime manifest schema differs')
        head=u.git(ROOT,'rev-parse','HEAD')
        verified=p is None
        if p:
            self.verify_normal_origin(p)
            expected=self.state.get('old_process') or p
            verify_process(p,expected,self.cfg['pythonExe']);verified=True
        return dict(host=self.pins['host'],sql_host=self.settings.DB_HOST,database=actual,schema=revision,head=head,version=release.get('version'),runtime_commit=release.get('commit'),clean=u.clean(ROOT),protected_unchanged=True,backend_stopped=p is None,pending=pending,auto_restart=self.cfg.get('autoRestart'),approved=bool(self.reference),process_verified=verified)
    def preflight(self):
        s=self.read_state();u.guard_context(dict(s,approved=True),self.pins,stopped=False)
        ps("foreach($t in Get-ScheduledTask){if($t.State -ne 'Disabled'){foreach($a in $t.Actions){if($a.Arguments -match 'Test-PmsHealth' -and $a.Arguments -match '-AutoRestart'){throw 'Restart override enabled'}}}};if((Get-PSDrive C).Free -lt 2GB){throw 'Insufficient backup space'}")
        with self.opener.open('http://127.0.0.1:8000/api/health',timeout=8) as r:u.check(json.load(r).get('status')=='ok','PMS health failed')
        u.read_package(HERE/'candidate.zip',self.pins)
        u.check(u.hashfile(HERE/'source.bundle')==self.pins['bundle_sha256'],'Bundle digest differs')
        current=process();verify_process(current,self.state.get('old_process') or current,self.cfg['pythonExe'])
        result=dict(head=s['head'],runtime_commit=s['runtime_commit'],version=s['version'],schema=s['schema'],pending=s['pending'],protected_configs_verified=True,host=self.pins['host'],read_only=True)
        if self.reference:
            self.record('preflight-verified',old_process=current,protected=self.files.protected,approval_reference=self.reference)
        else:print(json.dumps(result,ensure_ascii=False),flush=True)
        return result
    def stage(self):self.approval();self.files.stage();self.record('stage-verified')
    def backup(self):
        self.approval();require_private_acl(HERE,self.owner);self.files.backup(self.read_state());require_private_acl(HERE,self.owner);self.record('program-backup-verified')
    def stop(self):
        self.approval();s=self.read_state();u.guard_context(s,self.pins,stopped=False);self.files.verify_backup()
        current=process();verify_process(current,self.state['old_process'],self.cfg['pythonExe'])
        self.record('stopping-pms');stop_process(current);u.guard_context(self.read_state(),self.pins,stopped=True);self.record('pms-stopped')
    def install(self):self.approval();self.files.install(self.read_state);self.record('candidate-installed')
    def start(self):
        self.approval();self.files.verify_installed();u.check(process() is None,'PMS port in use')
        with self.engine.connect() as con:u.check(con.execute(self.text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one()==self.pins['schema'],'Schema drift before start')
        u.check(not (HERE/'controlled-ready.json').exists(),'Previous startup proof exists')
        env=os.environ.copy();env.update(ERP_SYNC_WORKER_ENABLED='false',PMS_RELEASE_MAIL_WORKER_ENABLED='false',PYTHONIOENCODING='utf-8')
        with (HERE/'controlled-stdout.log').open('xb') as out,(HERE/'controlled-stderr.log').open('xb') as err:
            child=subprocess.Popen([self.cfg['pythonExe'],'-B',str(HERE/'controlled.py')],cwd=ROOT/'backend',env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        env.clear();(Path(self.cfg['dataRoot'])/'pids/backend.pid').write_text(str(child.pid),encoding='ascii')
        self.record('controlled-launch-requested',controlled_pid=child.pid)
        for _ in range(60):
            u.check(child.poll() is None,'Controlled startup failed')
            if (HERE/'controlled-ready.json').exists() and process() is not None:break
            time.sleep(.5)
        else:raise RuntimeError('Controlled startup deadline')
        proof=json.loads((HERE/'controlled-ready.json').read_text(encoding='utf-8'));p=process()
        u.check(p['pid']==child.pid==proof['pid'] and p['owner_sid']==self.owner,'Controlled process mismatch')
        verify_process(p,p,self.cfg['pythonExe'],launcher=HERE/'controlled.py')
        self.record('controlled-started',controlled_process=p)
    def verify(self):
        self.files.verify_installed();p=process();verify_process(p,self.state['controlled_process'],self.cfg['pythonExe'],launcher=HERE/'controlled.py')
        proof=json.loads((HERE/'controlled-ready.json').read_text(encoding='utf-8'));u.check(proof['commit']==self.pins['commit'] and proof['version']==self.pins['version'] and proof['background_workers_running']==[] and proof['maintenance_writes_blocked'] is True,'Controlled proof differs')
        with self.engine.connect() as con:u.check(con.execute(self.text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one()==self.pins['schema'],'Schema drift after start')
        with self.opener.open('http://127.0.0.1:8000/api/health',timeout=8) as r:u.check(json.load(r).get('status')=='ok','Controlled health failed')
        with self.opener.open('http://127.0.0.1/',timeout=8) as r:u.check(r.read()==(ROOT/'frontend/dist/index.html').read_bytes(),'Served frontend differs')
        self.record('awaiting-browser-acceptance',browser_accepted=False,normal_runtime_restored=False,notifications_published=False)
    def stop_controlled(self):
        self.approval();self.files.config_guard();p=process();verify_process(p,self.state['controlled_process'],self.cfg['pythonExe'],launcher=HERE/'controlled.py');u.check(p['owner_sid']==self.owner,'Controlled owner mismatch');stop_process(p);self.record('controlled-stopped')
    def rollback(self):
        self.approval();u.check(process() is None,'Program rollback requires PMS stopped')
        # read_state deliberately requires normal commands only when a listener exists.
        self.files.rollback(self.read_state(for_rollback=True));self.record('old-program-restored-pms-stays-stopped')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['preflight','deploy','stop-controlled','rollback']);parser.add_argument('--approved-window-reference');args=parser.parse_args();controller=None
    try:
        controller=WindowsUpdate(args.approved_window_reference)
        if args.action=='preflight':controller.preflight()
        elif args.action=='deploy':
            controller.approval();u.check(not controller.state_path.exists(),'Existing maintenance state; inspect instead of rerunning');pipeline(controller)
        elif args.action=='stop-controlled':controller.stop_controlled()
        else:controller.rollback()
    except Exception as error:
        if controller and args.action!='preflight':controller.record('failed',error_type=type(error).__name__)
        print('PMS_PROGRAM_STOPPED '+type(error).__name__+'; preserve evidence; no automatic rollback/retry',flush=True);return 1
    finally:
        if controller:controller.engine.dispose()
    return 0
if __name__=='__main__':raise SystemExit(main())
