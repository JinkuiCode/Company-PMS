"""Pinned program-only update primitives. No database/credential/network API."""
import hashlib
import json
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

WORKERS={'pms-erp-worker','pms-report-export-worker','pms-feedback-mail-worker','pms-release-mail-worker'}
EXTRAS={'release.json','SHA256SUMS','SOURCE-PROVENANCE.json','RELEASE-MANIFEST.txt','SERVER-DEPLOYMENT.md'}

def check(ok,message):
    if not ok:raise RuntimeError(message)

def hashfile(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(data):return hashlib.sha256(data).hexdigest()
def save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
def run(args):
    result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
    check(result.returncode==0,'Local program command failed; preserve private evidence')
    return result.stdout.strip()
def git(root,*args):return run(['git','-C',str(root),*args])

def tree(path):
    path=Path(path);check(path.is_dir() and not path.is_symlink(),'Program directory missing or linked')
    check(not any(p.is_symlink() for p in path.rglob('*')),'Linked program entry refused')
    return {p.relative_to(path).as_posix():hashfile(p) for p in path.rglob('*') if p.is_file()}

def copy_tree(source,dest):
    expected=tree(source);check(not dest.exists(),'Destination already exists')
    shutil.copytree(source,dest);check(tree(dest)==expected,'Program copy bytes differ');return expected

def clean(root):
    return git(root,'status','--porcelain') in ('','?? release.json')

def guard_context(state,pins,*,stopped):
    for key in ('host','sql_host','database','schema'):check(state.get(key)==pins[key],'Unexpected '+key)
    for key in ('clean','protected_unchanged','process_verified'):check(state.get(key) is True,'Unverified '+key)
    check(state.get('approved') is True,'Separate maintenance approval required')
    check(state.get('backend_stopped') is stopped,'Unexpected PMS listener state')
    check(state.get('pending')==0 and state.get('auto_restart') is False,'Background work or automatic restart present')
    check(state.get('head')==pins['baseline_head'],'Source baseline changed')
    check(state.get('version')==pins['baseline_version'] and state.get('runtime_commit')==pins['baseline_runtime_commit'],'Runtime baseline changed')

def allowed_request(method,path):
    if path.startswith(('/api/sso/','/api/erp/','/api/reports/')):return False
    if path in ('/api/users/oa-options','/api/product-lines/options','/api/product-lines/organizations'):return False
    return method in ('GET','HEAD','OPTIONS') or (method=='POST' and path in ('/api/auth/login','/api/auth/logout'))

def read_package(path,pins):
    check(hashfile(path)==pins['archive_sha256'],'Fixed package digest changed')
    files={};folded=set()
    with zipfile.ZipFile(path) as z:
        check(sum(i.file_size for i in z.infolist())<512*1024*1024,'Package too large')
        for i in z.infolist():
            name=i.filename;parts=PurePosixPath(name).parts
            check(name.startswith(pins['build_id']+'/') and len(parts)>1 and not i.is_dir(),'Unexpected package prefix')
            check(not name.startswith('/') and '..' not in parts and '\\' not in name and ':' not in name,'Unsafe package path')
            check(not stat.S_ISLNK(i.external_attr>>16) and not any(p.endswith((' ','.')) for p in parts),'Unsafe package entry')
            rel=name[len(pins['build_id'])+1:];check(rel.casefold() not in folded,'Duplicate Windows path');folded.add(rel.casefold())
            check(rel in EXTRAS or rel.startswith(('backend/','ops/windows/','frontend/dist/')),'Unexpected payload')
            check(not set(parts)&{'.git','.runtime','outputs','node_modules','__pycache__','prototypes','attachments'},'Private payload refused')
            check(not any(p.startswith('.env') and not p.endswith('.example') for p in parts),'Protected config refused')
            check(Path(rel).suffix.lower() not in {'.db','.bak','.xlsx','.pyc','.log'},'Private data refused')
            files[rel]=z.read(i)
    check(set(EXTRAS)<=set(files),'Release metadata missing')
    sums={}
    for line in files['SHA256SUMS'].decode().splitlines():
        sha,name=line.split('  ',1);check(name not in sums and name in files and digest(files[name])==sha,'Payload checksum differs');sums[name]=sha
    check(set(sums)==set(files)-{'SHA256SUMS'},'Incomplete payload checksums')
    release=json.loads(files['release.json']);prov=json.loads(files['SOURCE-PROVENANCE.json'])
    check(all(release.get(k)==pins[k] for k in ('version','commit','build_id')) and release.get('database_revision')==pins['schema'],'Candidate identity differs')
    check(prov.get('commit')==pins['commit'] and prov.get('schema_changed') is False,'Candidate provenance differs')
    return files

class ProgramFiles:
    """Real file/Git actions; caller supplies fresh verified stopped-server state."""
    def __init__(self,root,work,pins,protected):
        self.root=Path(root);self.work=Path(work);self.pins=pins;self.protected={str(Path(p)):hashfile(p) for p in protected}
        check(not self.root.is_symlink() and not self.work.is_symlink(),'Linked root refused')
    def config_guard(self):
        check(all(hashfile(p)==sha for p,sha in self.protected.items()),'Protected configuration changed')
    def backup(self,state):
        guard_context(state,self.pins,stopped=False);self.config_guard()
        check(git(self.root,'rev-parse','HEAD')==self.pins['baseline_head'] and clean(self.root),'Checkout changed')
        dest=self.work/'previous-program';dest.mkdir()
        copy_tree(self.root/'frontend/dist',dest/'dist')
        shutil.copy2(self.root/'release.json',dest/'release.json')
        git(self.root,'archive','--format=zip','--output='+str(dest/'source.zip'),'HEAD')
        git(self.root,'bundle','create',str(dest/'history.bundle'),'HEAD');git(self.root,'bundle','verify',str(dest/'history.bundle'))
        private=dest/'private';private.mkdir()
        protected_copies={}
        for n,(path,sha) in enumerate(self.protected.items()):
            target=private/str(n);shutil.copy2(path,target);check(hashfile(target)==sha,'Private backup mismatch');protected_copies[str(n)]=sha
        save(dest/'manifest.json',dict(head=self.pins['baseline_head'],source=hashfile(dest/'source.zip'),history=hashfile(dest/'history.bundle'),dist=tree(dest/'dist'),release=hashfile(dest/'release.json'),protected=self.protected,private=protected_copies))
        self.verify_backup();return dest
    def verify_backup(self):
        d=self.work/'previous-program';m=json.loads((d/'manifest.json').read_text())
        check(m['head']==self.pins['baseline_head'] and m['protected']==self.protected,'Backup identity differs')
        check(hashfile(d/'source.zip')==m['source'] and hashfile(d/'history.bundle')==m['history'] and hashfile(d/'release.json')==m['release'] and tree(d/'dist')==m['dist'],'Backup changed')
        check(all(hashfile(d/'private'/p)==sha for p,sha in m['private'].items()),'Private backup changed')
        r=json.loads((d/'release.json').read_text());check(r['version']==self.pins['baseline_version'] and r['commit']==self.pins['baseline_runtime_commit'] and r['database_revision']==self.pins['schema'],'Backup runtime differs')
        with zipfile.ZipFile(d/'source.zip') as z:check(z.testzip() is None,'Source backup CRC differs')
        return m
    def stage(self):
        files=read_package(self.work/'candidate.zip',self.pins)
        check(hashfile(self.work/'source.bundle')==self.pins['bundle_sha256'],'Source bundle changed')
        git(self.root,'bundle','verify',str(self.work/'source.bundle'))
        check(git(self.root,'bundle','list-heads',str(self.work/'source.bundle'))==self.pins['commit']+' HEAD','Wrong bundle head')
        stage=self.work/'source-checkout';check(not stage.exists(),'Stage already exists')
        run(['git','clone','--no-checkout','--shared',str(self.root),str(stage)])
        git(stage,'fetch',str(self.work/'source.bundle'),'HEAD');git(stage,'-c','core.autocrlf=false','checkout','--detach',self.pins['commit'])
        for name,data in files.items():
            if name.startswith(('backend/','ops/windows/')):check((stage/name).read_bytes()==data,'Bundle/package source differs')
        dist=self.work/'candidate-dist';dist.mkdir()
        for name,data in files.items():
            if name.startswith('frontend/dist/'):
                p=dist/name[len('frontend/dist/'):];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        return files
    def install(self,fresh_state):
        guard_context(fresh_state(),self.pins,stopped=True);self.config_guard();self.verify_backup()
        check(git(self.root,'rev-parse','HEAD')==self.pins['baseline_head'] and clean(self.root),'Checkout drift before install')
        files=read_package(self.work/'candidate.zip',self.pins)
        check(hashfile(self.work/'source.bundle')==self.pins['bundle_sha256'],'Source bundle drift')
        stage=self.work/'source-checkout'
        check(git(stage,'rev-parse','HEAD')==self.pins['commit'] and clean(stage),'Staged source drift')
        for name,data in files.items():
            if name.startswith(('backend/','ops/windows/')):check((stage/name).read_bytes()==data,'Staged source bytes drift')
            if name.startswith('frontend/dist/'):check((self.work/'candidate-dist'/name[len('frontend/dist/'):]).read_bytes()==data,'Staged frontend drift')
        save(self.work/'install-started.json',{'commit':self.pins['commit'],'database_modified':False})
        git(self.root,'fetch',str(self.work/'source.bundle'),'HEAD')
        check(git(self.root,'rev-parse','FETCH_HEAD')==self.pins['commit'],'Fetched head drift')
        git(self.root,'-c','core.autocrlf=false','switch','--detach',self.pins['commit'])
        for name,data in files.items():
            if name.startswith(('backend/','ops/windows/')):
                p=self.root/name;actual=p.read_bytes();check(actual==data or actual.replace(b'\r\n',b'\n')==data,'Installed source mismatch')
                if actual!=data:p.write_bytes(data)
        (self.root/'frontend/dist').rename(self.work/'displaced-dist')
        copy_tree(self.work/'candidate-dist',self.root/'frontend/dist')
        (self.root/'release.json').write_bytes(files['release.json'])
        self.config_guard();self.verify_installed();save(self.work/'installed.json',{'commit':self.pins['commit'],'schema':self.pins['schema'],'database_modified':False})
    def verify_installed(self):
        files=read_package(self.work/'candidate.zip',self.pins)
        check(git(self.root,'rev-parse','HEAD')==self.pins['commit'] and clean(self.root),'Installed checkout differs')
        expected_dist={}
        for name,data in files.items():
            if name.startswith(('backend/','ops/windows/','frontend/dist/')) or name=='release.json':check((self.root/name).read_bytes()==data,'Installed payload differs')
            if name.startswith('frontend/dist/'):expected_dist[name[len('frontend/dist/'):]]=digest(data)
        check(tree(self.root/'frontend/dist')==expected_dist,'Unexpected frontend payload');self.config_guard()
    def rollback(self,state):
        for key in ('host','sql_host','database','schema'):check(state.get(key)==self.pins[key],'Rollback target drift')
        check(state.get('approved') is True and state.get('backend_stopped') is True and state.get('process_verified') is True and state.get('pending')==0 and state.get('auto_restart') is False,'Separate approved stopped rollback required')
        check(git(self.root,'rev-parse','HEAD') in (self.pins['commit'],self.pins['baseline_head']) and clean(self.root),'Rollback checkout drift')
        self.config_guard();m=self.verify_backup();dest=self.work/'rollback-displaced';dest.mkdir()
        git(self.root,'-c','core.autocrlf=false','switch','--detach',self.pins['baseline_head'])
        if (self.root/'frontend/dist').exists():(self.root/'frontend/dist').rename(dest/'dist')
        if (self.root/'release.json').exists():shutil.copy2(self.root/'release.json',dest/'release.json')
        copy_tree(self.work/'previous-program/dist',self.root/'frontend/dist')
        shutil.copy2(self.work/'previous-program/release.json',self.root/'release.json')
        with zipfile.ZipFile(self.work/'previous-program/source.zip') as z:
            for name in z.namelist():
                if name.endswith('/'):continue
                p=self.root/name;expected=z.read(name);actual=p.read_bytes();check(actual==expected or actual.replace(b'\r\n',b'\n')==expected,'Old source mismatch')
                if actual!=expected:p.write_bytes(expected)
        check(git(self.root,'rev-parse','HEAD')==self.pins['baseline_head'] and clean(self.root) and tree(self.root/'frontend/dist')==m['dist'] and hashfile(self.root/'release.json')==m['release'],'Restored program differs')
        self.config_guard();save(self.work/'rolled-back.json',{'head':self.pins['baseline_head'],'database_modified':False,'backend_started':False})
