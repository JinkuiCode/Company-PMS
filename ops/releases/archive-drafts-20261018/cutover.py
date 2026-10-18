"""Approved fixed-candidate PMS cutover. Never restores over a production DB."""
import argparse
import getpass
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=Path('C:/PMS')
BASE_FILE=HERE/'rehearsal_base.py'
if hashlib.sha256(BASE_FILE.read_bytes()).hexdigest()!='b8cbdb2e1a70cc7039f94195d4385781ac37a92a47bd18aeaa3ed8fd786072b6':
    raise RuntimeError('Reviewed rehearsal helper changed')
spec=importlib.util.spec_from_file_location('cutover_reviewed_base',BASE_FILE)
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
h.HERE=HERE;h.PREFIX='PMS_DRAFT_CUTOVER_20261018_'
h.CANDIDATE='d71971d9250f74ff560b3f4bfa68a4f95edf3c58'
h.PACKAGE_SHA='5338ee0818e2974ec859b04d653fe39e81e8851dbf10326046c7980e18bc1f05'
BUNDLE_SHA='9530ac7fc1568772e0b21b688d1ffd64ce9ee71d6e961c134e5a35c170b48203'
ARTIFACTS=HERE if os.name=='nt' else Path(__file__).resolve().parents[3]/'.runtime/archive-draft-release-20261018'
PAUSED_WORKERS={'pms-erp-worker','pms-report-export-worker','pms-feedback-mail-worker','pms-release-mail-worker'}


def read_release_package(path):
    h.check(h.hashfile(path)==h.PACKAGE_SHA,'Pinned release ZIP mismatch')
    with h.zipfile.ZipFile(path) as z:
        h.check(z.testzip() is None,'Release ZIP CRC mismatch')
        names=z.namelist()
        h.check(len(names)==len(set(n.casefold() for n in names)),'Duplicate Windows path')
        files={}
        for entry in z.infolist():
            name=entry.filename
            prefix='pms-draft-release-20261018/'
            h.check(name.startswith(prefix) and ':' not in name and '\\' not in name
                    and '..' not in h.PurePosixPath(name).parts and not entry.is_dir()
                    and (entry.external_attr>>16)&0o170000!=0o120000,'Unsafe release ZIP entry')
            name=name[len(prefix):]
            h.check(name and '.env' not in name and '/prototypes/' not in name
                    and (name.startswith(('backend/','ops/windows/','frontend/src/','frontend/dist/'))
                         or name in ('release.json','SHA256SUMS','frontend/index.html','frontend/package.json',
                                     'frontend/package-lock.json','frontend/tsconfig.app.json','frontend/tsconfig.json',
                                     'frontend/tsconfig.node.json','frontend/vite.config.ts')),'Unexpected release payload')
            files[name]=z.read(entry)
        checks={}
        for line in files['SHA256SUMS'].decode().splitlines():
            sha,name=line.split(maxsplit=1)
            h.check(name not in checks and name in files and hashlib.sha256(files[name]).hexdigest()==sha,'Release file mismatch')
            checks[name]=sha
        h.check(set(checks)==set(files)-{'SHA256SUMS'},'Incomplete release manifest')
        release=json.loads(files['release.json'])
        h.check(release['version']=='v1.1.0' and release['commit']==h.CANDIDATE
                and release['database_revision']==h.CURRENT,'Wrong release identity')
        return release,files


h.read_package=read_release_package


def guard_receipt_destination(value):
    h.check(value is None,'Receipt upload is disabled')


def guard_program_rollback(state):
    h.check(state.get('approved') is True and state.get('actual_database')=='PMS'
            and state.get('sql_host')=='10.10.1.230' and state.get('revision')==h.PREVIOUS
            and state.get('backend_stopped') is True and state.get('backup_verified') is True,
            'Separate program rollback approval and matching restored database required')


def guard_upgrade(state):
    h.check(state.get('approved') is True and state.get('actual_database')=='PMS'
            and state.get('sql_host')=='10.10.1.230' and state.get('backend_stopped') is True
            and state.get('restored_verified') is True and state.get('database_revision')==h.PREVIOUS,
            'Formal upgrade prerequisites are incomplete')
    h.guard_backup(state.get('backup',{}))


def guard_install(state):
    h.check(state.get('phase')=='formal-upgrade-verified' and state.get('backend_stopped') is True
            and state.get('database_revision')==h.CURRENT and state.get('business_preserved') is True
            and state.get('protected_configs_unchanged') is True,'Verified formal upgrade required before installation')


def pipeline(controller):
    for step in ('preflight','backup_program','credentials','preflight','stop','backup_database',
                 'verify_restored','upgrade','install','start','verify'):
        getattr(controller,step)()


def backup_tree(source,target):
    h.check(source.is_dir() and not target.exists(),'Backup source missing or destination exists')
    h.check(not any(p.is_symlink() for p in source.rglob('*')),'Backup symlink refused')
    hashes={p.relative_to(source).as_posix():h.hashfile(p) for p in source.rglob('*') if p.is_file()}
    shutil.copytree(source,target)
    h.check(hashes=={p.relative_to(target).as_posix():h.hashfile(p) for p in target.rglob('*') if p.is_file()},'Backup bytes mismatch')
    return hashes


def canonicalize_source(path,data):
    actual=path.read_bytes()
    if actual==data:return
    h.check(actual.replace(b'\r\n',b'\n')==data,'Non-newline source difference; refusing overwrite')
    path.write_bytes(data)


def guard_manifest_path(settings,environment,root):
    for value in (getattr(settings,'PMS_RELEASE_MANIFEST',''),environment.get('PMS_RELEASE_MANIFEST','')):
        h.check(not value or Path(value)==root/'release.json','Custom runtime manifest requires review')


def guard_checkout_status(status,*,allow_manifest=False):
    h.check(status=='' or (allow_manifest and status=='?? release.json'),'Unexpected source or untracked file change')


def guard_process(expected,actual,executable):
    h.check(actual.get('pid')==expected.get('pid') and actual.get('created')==expected.get('created')
        and actual.get('executable','').replace('\\','/').casefold()==executable.replace('\\','/').casefold()
        and re.search(r'(?i)-m\s+uvicorn\s+main:app\s+--host\s+127\.0\.0\.1\s+--port\s+8000(?:\s|$)',actual.get('command','')),
        'PMS process identity changed; refusing stop')


def guard_controlled_process(expected_pid,actual,proof,executable,launcher,owner_sid):
    normalize=lambda s:str(s).replace('\\','/').casefold()
    h.check(actual.get('pid')==expected_pid==proof.get('pid')
        and normalize(actual.get('executable',''))==normalize(executable)
        and normalize(launcher) in normalize(actual.get('command',''))
        and re.search(r'(?:^|\s)main:app(?:\s|$)',actual.get('command',''))
        and actual.get('owner_sid')==owner_sid and proof.get('maintenance_writes_blocked') is True,
        'Listener is not the expected controlled PMS process or owner')


def safe_receipt(state):
    keys={'phase','candidate','source_head','database_revision','sql_host','actual_database','backend_stopped',
          'restored_verified','business_preserved','protected_configs_unchanged','program_backup',
          'isolated_database','verification','failed_phase','error_type','gate_error','approved'}
    out={k:v for k,v in state.items() if k in keys}
    if 'backup' in state:
        out['backup']={k:v for k,v in state['backup'].items() if k in {'path_on_sql_server','copy_only','checksum','verifyonly','backup_sets','sha256','finished','first_lsn','last_lsn'}}
    return out


def allowed_request(method,path):
    if path.startswith(('/api/sso/','/api/erp/','/api/reports/')):return False
    if path in ('/api/users/oa-options','/api/product-lines/options','/api/product-lines/organizations'):return False
    return method in ('GET','HEAD','OPTIONS') or (method=='POST' and path in ('/api/auth/login','/api/auth/logout'))


def pause_workers():
    import threading
    start,join=threading.Thread.start,threading.Thread.join
    paused=set()
    def guarded_start(thread,*a,**kw):
        if thread.name in PAUSED_WORKERS: paused.add(thread);return
        return start(thread,*a,**kw)
    def guarded_join(thread,*a,**kw):
        if thread in paused:return
        return join(thread,*a,**kw)
    threading.Thread.start=guarded_start;threading.Thread.join=guarded_join
    def restore():threading.Thread.start=start;threading.Thread.join=join
    return restore


def ps(script):return h.run(['powershell.exe','-NoProfile','-Command',script])


class Cutover:
    def __init__(self,result_url,approved):
        h.check(os.name=='nt' and HERE==ROOT/'.runtime/archive-draft-cutover-20261018','Wrong cutover directory')
        h.guard_host(socket.gethostbyname_ex(socket.gethostname())[2])
        h.check(approved,'Explicit formal cutover approval missing')
        h.check(not (HERE/'cutover-state.json').exists(),'Existing cutover state; inspect instead of rerunning')
        guard_receipt_destination(result_url)
        self.result_url=result_url;self.opener=h.build_opener(h.ProxyHandler({}))
        self.cfg=json.loads((ROOT/'ops/windows/pms-operations.json').read_text(encoding='utf-8-sig'))
        os.environ.update(PMS_CONFIG_FILE=self.cfg['protectedConfig'],PMS_PURCHASE_CONFIG_FILE=self.cfg['purchaseConfig'],PYTHONDONTWRITEBYTECODE='1')
        sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'backend'))
        from app.core.config import settings,validate_runtime_config
        from app.core.database import engine
        from sqlalchemy import text
        validate_runtime_config(settings)
        self.settings,self.engine,self.text=settings,engine,text
        h.check(settings.PMS_ENV=='production' and settings.DB_HOST=='10.10.1.230' and settings.DB_NAME=='PMS','Wrong formal settings')
        self.state=dict(phase='initial',approved=True,candidate=h.CANDIDATE,backend_stopped=False,sql_host=settings.DB_HOST)
        self.protected={str(p):h.hashfile(p) for p in dict.fromkeys([ROOT/'backend/.env.local',ROOT/'ops/windows/pms-operations.json',Path(self.cfg['protectedConfig']),Path(self.cfg['purchaseConfig']),Path('C:/nginx/conf/nginx.conf'),Path('C:/nginx/conf/pms.conf')])}
        self.initial_runtime=h.runtime_fingerprint();self.old_process=self.process()
        self.current_sid=ps('[Security.Principal.WindowsIdentity]::GetCurrent().User.Value')
        h.check(self.old_process['owner_sid']==self.current_sid,'Runtime OS identity differs; no identity switch is approved')
        self.username=self.password=None

    def record(self,phase):
        self.state['phase']=phase;h.save(HERE/'cutover-state.json',self.state)
        if self.result_url:
            try:self.opener.open(h.Request(self.result_url,data=json.dumps(safe_receipt(self.state),ensure_ascii=False).encode(),headers={'Content-Type':'application/json'}),timeout=10).read()
            except Exception:print('Cutover receipt retained on server',flush=True)
        print('CUTOVER_PHASE '+phase,flush=True)

    def process(self):
        script="$ids=@((Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess|Sort-Object -Unique);if($ids.Count -ne 1){throw 'One PMS listener required'};$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$ids[0]);$o=Invoke-CimMethod -InputObject $p -MethodName GetOwnerSid;if($o.ReturnValue -ne 0){throw 'Cannot verify runtime owner'};@{pid=$p.ProcessId;created=$p.CreationDate.ToUniversalTime().ToString('o');executable=$p.ExecutablePath;command=$p.CommandLine;owner_sid=$o.Sid}|ConvertTo-Json -Compress"
        return json.loads(ps(script))

    def config_guard(self):
        h.check(all(h.hashfile(p)==sha for p,sha in self.protected.items()),'Protected configuration changed')
        self.state['protected_configs_unchanged']=True

    def db_context(self):
        with self.engine.connect() as c:
            actual=c.execute(self.text('SELECT DB_NAME()')).scalar_one()
            rev=c.execute(self.text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one()
        h.check(actual=='PMS','Wrong actual database')
        self.state.update(actual_database=actual,database_revision=rev)
        return rev

    def pending(self):
        with self.engine.connect() as c:
            for table,statuses in (
                ('erp_sync_task',"'queued','running','review'"),
                ('pms_report_export_job',"'queued','running'"),
                ('pms_feedback_notification',"'pending','waiting','processing'"),
                ('pms_release_mail',"'pending','waiting','processing'"),
            ):
                h.check(c.execute(self.text('SELECT COUNT(*) FROM '+table+' WHERE status IN ('+statuses+')')).scalar_one()==0,
                        'Business background work pending')

    def preflight(self):
        self.config_guard();h.check(self.db_context()==h.PREVIOUS,'Unexpected source revision')
        h.check(h.run(['git.exe','-C',str(ROOT),'rev-parse','HEAD'])==h.BASELINE,'Source version changed')
        guard_checkout_status(h.run(['git.exe','-C',str(ROOT),'status','--porcelain']),allow_manifest=True)
        release=json.loads((ROOT/'release.json').read_text(encoding='utf-8'))
        h.check(release['version']=='v1.0.2' and release['commit']==h.BASELINE and release['database_revision']==h.PREVIOUS,'Old release identity changed')
        h.check(h.runtime_fingerprint()==self.initial_runtime,'Runtime changed before cutover')
        guard_process(self.old_process,self.process(),self.cfg['pythonExe'])
        h.check(self.cfg.get('autoRestart') is False,'Automatic restart is enabled')
        ps("foreach($t in Get-ScheduledTask){if($t.State -ne 'Disabled'){foreach($a in $t.Actions){if($a.Arguments -match 'Test-PmsHealth' -and $a.Arguments -match '-AutoRestart'){throw 'Restart override enabled'}}}};if((Get-PSDrive C).Free -lt 2GB){throw 'Insufficient app backup space'}")
        with self.opener.open('http://127.0.0.1:8000/api/health',timeout=8) as response:h.check(json.load(response).get('status')=='ok','PMS unhealthy')
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url
        e=create_engine(make_url(self.settings.DATABASE_URL).set(database='PMS_DRAFT_REHEARSAL_20261018_37eea38c'))
        try:
            with e.connect() as c:
                for t in h.NEW_TABLES:
                    for permission in ('SELECT','INSERT','UPDATE','DELETE'):
                        h.check(c.execute(self.text("SELECT HAS_PERMS_BY_NAME(:t,'OBJECT',:p)"),{'t':'dbo.'+t,'p':permission}).scalar_one()==1,'New-table runtime permission missing')
        finally:e.dispose()
        self.pending();h.read_package(HERE/'candidate.zip')
        bundle_sha=BUNDLE_SHA
        h.check(h.hashfile(HERE/'source.bundle')==bundle_sha,'Pinned bundle changed')
        h.run(['git.exe','-C',str(ROOT),'bundle','verify',str(HERE/'source.bundle')])
        h.check(h.run(['git.exe','-C',str(ROOT),'bundle','list-heads',str(HERE/'source.bundle')])==h.CANDIDATE+' HEAD','Wrong bundle target')
        guard_manifest_path(self.settings,os.environ,ROOT)
        self.state['source_head']=h.BASELINE;self.record('preflight-verified')

    def backup_program(self):
        target=HERE/'previous-program';h.check(not target.exists(),'Previous program backup exists');target.mkdir()
        private=target/'private';private.mkdir()
        for i,(path,sha) in enumerate(self.protected.items()):
            dest=private/(str(i)+'-'+Path(path).name);shutil.copy2(path,dest)
            h.check(h.hashfile(dest)==sha,'Protected backup mismatch')
        hashes=backup_tree(ROOT/'frontend/dist',target/'dist')
        h.run(['git.exe','-C',str(ROOT),'archive','--format=zip','--output='+str(target/'source.zip'),h.BASELINE])
        h.check(h.zipfile.ZipFile(target/'source.zip').testzip() is None,'Source archive CRC failed')
        h.run(['git.exe','-C',str(ROOT),'bundle','create',str(target/'history.bundle'),'HEAD'])
        h.run(['git.exe','-C',str(ROOT),'bundle','verify',str(target/'history.bundle')])
        if (ROOT/'release.json').exists():shutil.copy2(ROOT/'release.json',target/'release.json')
        self.state['program_backup']=str(target)
        h.save(target/'backup-manifest.json',dict(source_sha256=h.hashfile(target/'source.zip'),history_sha256=h.hashfile(target/'history.bundle'),dist=hashes,protected=self.protected,old_branch=h.run(['git.exe','-C',str(ROOT),'branch','--show-current']),runtime=self.initial_runtime),new=True)
        h.extract_package(HERE/'candidate.zip',HERE/'candidate')
        stage=HERE/'source-checkout'
        h.run(['git.exe','clone','--no-checkout','--shared',str(ROOT),str(stage)])
        h.run(['git.exe','-C',str(stage),'fetch',str(HERE/'source.bundle'),'HEAD'])
        h.run(['git.exe','-C',str(stage),'-c','core.autocrlf=false','-c','core.eol=lf','checkout','--detach',h.CANDIDATE])
        _,files=h.read_package(HERE/'candidate.zip')
        for name,data in files.items():
            if not name.startswith('frontend/dist/') and name not in ('release.json','SHA256SUMS'):h.check(h.hashfile(stage/name)==hashlib.sha256(data).hexdigest(),'Bundle and fixed package source differ')
        self.record('program-backup-verified')

    def credentials(self):
        self.record('awaiting-local-sql-identity')
        self.username=getpass.getpass('SQL backup/restore and upgrade administrator username (hidden): ').strip()
        self.password=getpass.getpass('SQL administrator password (hidden): ')
        h.check(self.username and self.password and self.username.casefold()!=self.settings.DB_USER.casefold(),'Separate SQL administrator identity required')
        from sqlalchemy import create_engine
        from sqlalchemy.engine import URL
        e=create_engine(URL.create('mssql+pyodbc',username=self.username,password=self.password,host=self.settings.DB_HOST,port=self.settings.DB_PORT,database='master',query={'driver':self.settings.DB_DRIVER,'Encrypt':'no','TrustServerCertificate':'yes'}))
        try:
            with e.connect() as c:h.check(c.execute(self.text("SELECT IS_SRVROLEMEMBER('sysadmin')")).scalar_one()==1,'Existing authorized administrator required')
        finally:e.dispose()

    def stop(self):
        self.config_guard();self.pending();guard_process(self.old_process,self.process(),self.cfg['pythonExe'])
        self.record('stopping-pms')
        p=self.old_process
        ps("$p=Get-CimInstance Win32_Process -Filter 'ProcessId="+str(p['pid'])+"';if(-not $p -or $p.CreationDate.ToUniversalTime().ToString('o') -ne '"+p['created']+"'){throw 'PID reused'};Stop-Process -Id $p.ProcessId;$until=(Get-Date).AddSeconds(20);while(Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue){if((Get-Date)-gt $until){throw 'PMS did not stop'};Start-Sleep -Milliseconds 250};if(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue){throw 'Listener remains'}")
        self.state['backend_stopped']=True;self.record('pms-stopped')
        self.pending()
        attachment=Path(self.settings.FEEDBACK_ATTACHMENT_DIR)
        if attachment.exists():backup_tree(attachment,HERE/'previous-program/attachments')
        with self.engine.connect() as c:self.before=h.capture(c)
        h.save(HERE/'formal-before.json',self.before,new=True)

    def backup_database(self):
        h.check(self.state.get('backend_stopped') is True,'PMS must be stopped before final backup')
        ps("if(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue){throw 'Unexpected PMS restart'}")
        h.Rehearsal.backup_restore(self,self.username,self.password)

    def verify_restored(self):
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url
        e=create_engine(make_url(self.settings.DATABASE_URL).set(database=self.state['isolated_database']))
        try:
            with e.connect() as c:
                h.guard_target(c.execute(self.text('SELECT DB_NAME()')).scalar_one(),'PMS',self.state['isolated_database'])
                restored=h.capture(c)
            h.check(restored==self.before,'Final backup restore differs from stopped formal snapshot')
        finally:e.dispose()
        self.state['restored_verified']=True;self.record('final-backup-restore-verified')

    def upgrade(self):
        self.config_guard();self.db_context();guard_upgrade(self.state)
        ps("if(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue){throw 'PMS restarted before upgrade'}")
        payload=dict(username=self.username,password=self.password,database='PMS',sql_host='10.10.1.230')
        self.record('formal-upgrade-running')
        try:
            result=subprocess.run([self.cfg['pythonExe'],'-B',str(HERE/'cutover.py'),'--upgrade-child'],input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True)
            h.check(result.returncode==0,'Formal upgrade child stopped; inspect private phase evidence')
        finally:payload.clear();self.username=self.password=None
        with self.engine.connect() as c:after=h.capture(c,projected=True)
        h.validate_upgrade(self.before,after);h.save(HERE/'formal-after.json',after,new=True)
        self.state.update(database_revision=h.CURRENT,business_preserved=True)
        self.config_guard();self.record('formal-upgrade-verified')

    def install(self):
        self.config_guard();guard_install(self.state)
        h.check(h.run(['git.exe','-C',str(ROOT),'rev-parse','HEAD'])==h.BASELINE and h.run(['git.exe','-C',str(ROOT),'status','--porcelain']) in ('','?? release.json'),'Formal checkout changed')
        _,files=h.read_package(HERE/'candidate.zip')
        h.run(['git.exe','-C',str(ROOT),'fetch',str(HERE/'source.bundle'),'HEAD'])
        h.check(h.run(['git.exe','-C',str(ROOT),'rev-parse','FETCH_HEAD'])==h.CANDIDATE,'Fetched candidate mismatch')
        h.run(['git.exe','-C',str(ROOT),'-c','core.autocrlf=false','-c','core.eol=lf','switch','--detach',h.CANDIDATE])
        for name,data in files.items():
            if not name.startswith('frontend/dist/') and name not in ('release.json','SHA256SUMS'):
                canonicalize_source(ROOT/name,data)
                h.check((ROOT/name).is_file() and h.hashfile(ROOT/name)==hashlib.sha256(data).hexdigest(),'Pinned source bytes differ')
        (ROOT/'frontend/dist').rename(HERE/'previous-program/live-dist-before-swap')
        backup_tree(HERE/'candidate/frontend/dist',ROOT/'frontend/dist')
        with (ROOT/'release.json').open('xb' if not (ROOT/'release.json').exists() else 'wb') as stream:stream.write(files['release.json'])
        self.config_guard();guard_checkout_status(h.run(['git.exe','-C',str(ROOT),'status','--porcelain']),allow_manifest=True)
        self.state['source_head']=h.CANDIDATE;self.record('candidate-installed')

    def start(self):
        self.config_guard();h.check(self.db_context()==h.CURRENT,'Wrong database before startup')
        ps("if(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue){throw 'Port already in use'}")
        env=os.environ.copy();env.update(PMS_CONFIG_FILE=self.cfg['protectedConfig'],PMS_PURCHASE_CONFIG_FILE=self.cfg['purchaseConfig'],PMS_RELEASE_MAIL_WORKER_ENABLED='false',ERP_SYNC_WORKER_ENABLED='false',PYTHONIOENCODING='utf-8')
        out=(HERE/'controlled-stdout.log').open('xb');err=(HERE/'controlled-stderr.log').open('xb')
        try:
            p=subprocess.Popen([self.cfg['pythonExe'],'-B',str(HERE/'controlled.py'),'main:app'],cwd=ROOT/'backend',env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        finally:out.close();err.close();env.clear()
        self.state['started_pid']=p.pid
        (Path(self.cfg['dataRoot'])/'pids/backend.pid').write_text(str(p.pid),encoding='ascii')
        for _ in range(60):
            h.check(p.poll() is None,'Controlled PMS startup failed')
            try:
                with self.opener.open('http://127.0.0.1:8000/api/health',timeout=2) as response:
                    if json.load(response).get('status')=='ok':break
            except Exception:pass
            time.sleep(.5)
        else:raise h.GateError('Controlled PMS health deadline exceeded')
        self.state['backend_stopped']=False;self.record('controlled-pms-started')

    def verify(self):
        self.config_guard();h.check(self.db_context()==h.CURRENT,'Live schema differs')
        h.check(h.run(['git.exe','-C',str(ROOT),'rev-parse','HEAD'])==h.CANDIDATE,'Live source differs')
        guard_checkout_status(h.run(['git.exe','-C',str(ROOT),'status','--porcelain']),allow_manifest=True)
        _,files=h.read_package(HERE/'candidate.zip')
        for name,data in files.items():
            if name.startswith(('backend/','ops/','frontend/dist/')) or name=='release.json':
                h.check(h.hashfile(ROOT/name)==hashlib.sha256(data).hexdigest(),'Installed bytes mismatch')
        with self.opener.open('http://127.0.0.1/',timeout=8) as response:h.check(response.read()==files['frontend/dist/index.html'],'Served frontend mismatch')
        proof=json.loads((HERE/'controlled-ready.json').read_text())
        guard_controlled_process(self.state['started_pid'],self.process(),proof,self.cfg['pythonExe'],HERE/'controlled.py',self.old_process['owner_sid'])
        h.check(proof['background_workers_running']==[] and proof['version']=='v1.1.0' and proof['commit']==h.CANDIDATE,'Controlled runtime proof invalid')
        with self.engine.connect() as c:
            current=h.capture(c,projected=True)
            h.validate_upgrade(self.before,current)
            for t in h.NEW_TABLES:
                for permission in ('SELECT','INSERT','UPDATE','DELETE'):
                    h.check(c.execute(self.text("SELECT HAS_PERMS_BY_NAME(:t,'OBJECT',:p)"),{'t':'dbo.'+t,'p':permission}).scalar_one()==1,'New table runtime access missing')
        self.state['verification']=dict(health=True,pinned_files=True,served_frontend=True,background_workers_paused=True,maintenance_write_guard=True,archive_count=current['tables']['pms_project_archive']['count'],existing_tables_preserved=len(self.before['tables']),new_grants=0,release_records=0)
        self.record('deployed-awaiting-browser-acceptance')


def upgrade_child():
    payload=json.load(sys.stdin)
    h.guard_host(socket.gethostbyname_ex(socket.gethostname())[2])
    h.check(payload['database']=='PMS' and payload['sql_host']=='10.10.1.230','Wrong child target')
    state=json.loads((HERE/'cutover-state.json').read_text())
    h.check(state['phase']=='formal-upgrade-running','Wrong formal phase');guard_upgrade(state)
    _,files=h.read_package(HERE/'candidate.zip')
    for name,data in files.items():h.check(h.hashfile(HERE/'candidate'/name)==hashlib.sha256(data).hexdigest(),'Candidate stage changed')
    cfg=json.loads((ROOT/'ops/windows/pms-operations.json').read_text(encoding='utf-8-sig'))
    os.environ['PMS_CONFIG_FILE']=cfg['protectedConfig'];os.environ['PMS_PURCHASE_CONFIG_FILE']=cfg['purchaseConfig']
    sys.path.insert(0,str(HERE/'candidate/backend'))
    from app.core import config
    config.settings=config.settings.model_copy(update={'DB_USER':h.quote(payload['username'],safe=''),'DB_PASSWORD':h.quote(payload['password'],safe='')})
    h.check(config.settings.PMS_ENV=='production' and config.settings.DB_HOST=='10.10.1.230' and config.settings.DB_NAME=='PMS','Child configured DB mismatch')
    from app.core.database import engine
    from sqlalchemy import text
    with engine.connect() as c:
        h.check(c.execute(text('SELECT DB_NAME()')).scalar_one()=='PMS','Child actual DB mismatch')
        h.check(c.execute(text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one()==h.PREVIOUS,'Child revision changed')
    spec=importlib.util.spec_from_file_location('approved_governance_upgrade',HERE/'candidate/backend/scripts/upgrade_database.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.upgrade_database(draft_management_only=True)
    engine.dispose();payload.clear();print('FORMAL_DRAFT_UPGRADE_VERIFIED',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--approved-cutover',action='store_true');parser.add_argument('--result-url');parser.add_argument('--upgrade-child',action='store_true');args=parser.parse_args()
    controller=None
    try:
        if args.upgrade_child:
            try: upgrade_child()
            except Exception as error:
                h.save(HERE/'formal-upgrade-error.json',{'error_type':type(error).__name__,'gate_error':str(error) if isinstance(error,h.GateError) else None},new=True)
                raise SystemExit(1)
            return
        controller=Cutover(args.result_url,args.approved_cutover);pipeline(controller)
        print('PMS_DRAFT_DEPLOYED_CONTROLLED',flush=True)
    except Exception as error:
        if controller:
            controller.state.update(failed_phase=controller.state['phase'],error_type=type(error).__name__)
            if isinstance(error,h.GateError):controller.state['gate_error']=str(error)
            controller.record('failed')
        print('CUTOVER_STOPPED '+type(error).__name__+'; preserve evidence; no automatic database restore',flush=True)
        raise SystemExit(1)
    finally:
        if controller:controller.username=controller.password=None;controller.engine.dispose()


if __name__=='__main__':main()
