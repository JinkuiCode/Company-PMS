"""Approved COPY_ONLY restore and isolated probe; never upgrades/stops production."""
import argparse,getpass,hashlib,importlib.util,json,os,re,socket,subprocess,sys,uuid,warnings
from pathlib import Path
from urllib.request import build_opener,ProxyHandler
import program_update as u
import windows_update as w
ROOT=Path('C:/PMS');HERE=Path(__file__).resolve().parent
PREFIX='PMS_V130_REHEARSAL_20261019_'
ISOLATION_APPROVAL='conversation:call_6d4a1965dc384eaeb0adae85e90ccdbe'

def hidden_input(prompt):
 with warnings.catch_warnings():
  warnings.simplefilter('error',getpass.GetPassWarning)
  return getpass.getpass(prompt)

def guard_reference(value):u.check(isinstance(ISOLATION_APPROVAL,str) and len(ISOLATION_APPROVAL)>=8 and value==ISOLATION_APPROVAL,'Exact separately approved R2 rehearsal reference required')
def guard_child(payload):
 u.check(payload.get('host')=='10.10.1.230' and payload.get('source')=='PMS','Wrong isolated SQL host/source')
 u.check(re.fullmatch(re.escape(PREFIX)+'[0-9a-f]{8}',payload.get('database','')) is not None,'Refuse non-isolated database')

def probe_environment(source):
 env={k:v for k,v in source.items() if not k.startswith(('DB_','K3_','SSO_','OA_','PMS_','ERP_'))}
 env.update(PMS_CONFIG_FILE=str(HERE/'never-created.env'),PYTHONDONTWRITEBYTECODE='1',ERP_SYNC_WORKER_ENABLED='false',PMS_RELEASE_MAIL_WORKER_ENABLED='false',SSO_ENABLED='false')
 return env

def backup_primitives(root=ROOT):
 """Reuse only the already tested backup/restore helpers, not their upgrade flow."""
 pins=w.load_pins();path=root/'ops/releases/archive-drafts-20261018/rehearsal_base.py'
 u.check(u.hashfile(path)==pins['rehearsal_base_sha256'],'Backup primitive source differs')
 spec=importlib.util.spec_from_file_location('pms_v130_backup_primitives',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.HERE=HERE;module.PREFIX=PREFIX
 return module

class Rehearsal:
 def __init__(self):
  self.pins=w.load_pins();w.guard_host(os.name,ROOT,HERE,socket.gethostbyname_ex(socket.gethostname())[2],self.pins)
  self.owner=w.ps('[Security.Principal.WindowsIdentity]::GetCurrent().User.Value');w.require_private_acl(HERE,self.owner)
  u.check(not (HERE/'rehearsal-state.json').exists(),'Existing rehearsal state; inspect rather than rerun')
  self.base=backup_primitives();self.state={'phase':'initial','candidate':self.pins['commit'],'backend_stopped':False}
  self.cfg=json.loads((ROOT/'ops/windows/pms-operations.json').read_text(encoding='utf-8-sig'))
  u.check(Path(self.cfg['installRoot'])==ROOT and self.cfg.get('autoRestart') is False,'Unexpected PMS operations context')
  os.environ.update(PMS_CONFIG_FILE=self.cfg['protectedConfig'],PMS_PURCHASE_CONFIG_FILE=self.cfg['purchaseConfig'],PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True
  sys.path.insert(0,str(ROOT/'backend'))
  from app.core.config import settings,validate_runtime_config
  from app.core.database import engine
  from sqlalchemy import text
  validate_runtime_config(settings)
  u.check(settings.PMS_ENV=='production' and settings.DB_HOST=='10.10.1.230' and settings.DB_NAME=='PMS' and settings.DB_DIALECT=='pyodbc','Wrong production read-only context')
  self.settings,self.engine,self.text=settings,engine,text
  self.protected={str(p):u.hashfile(p) for p in dict.fromkeys([ROOT/'backend/.env.local',ROOT/'ops/windows/pms-operations.json',Path(self.cfg['protectedConfig']),Path(self.cfg['purchaseConfig']),Path('C:/nginx/conf/nginx.conf'),Path('C:/nginx/conf/pms.conf')])}
  self.runtime=self.base.runtime_fingerprint(ROOT);self.process=w.process()
  w.WindowsUpdate.verify_normal_origin(self,self.process)
 def record(self,phase,**extra):
  w.require_private_acl(HERE,self.owner);self.state.update(extra,phase=phase)
  steps=HERE/'rehearsal-steps';steps.mkdir(exist_ok=True)
  u.save(steps/(str(len(list(steps.glob('*.json')))).zfill(3)+'-'+phase+'.json'),self.state)
  temp=HERE/'rehearsal-state.tmp';u.check(not temp.exists(),'Existing state transaction');temp.write_text(json.dumps(self.state,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(HERE/'rehearsal-state.json')
  print('V130_REHEARSAL_PHASE '+phase,flush=True)
 def verify_live(self):
  u.check(u.git(ROOT,'rev-parse','HEAD')==self.pins['baseline_head'] and u.clean(ROOT),'Production source changed')
  manifest=json.loads((ROOT/'release.json').read_text(encoding='utf-8'))
  u.check(manifest['version']==self.pins['baseline_version'] and manifest['commit']==self.pins['baseline_runtime_commit'] and manifest['database_revision']==self.pins['schema'],'Production runtime manifest changed')
  u.check(self.base.runtime_fingerprint(ROOT)==self.runtime and all(u.hashfile(p)==h for p,h in self.protected.items()),'Production runtime/configuration changed')
  w.verify_process(w.process(),self.process,self.cfg['pythonExe'])
  with build_opener(ProxyHandler({})).open('http://127.0.0.1:8000/api/health',timeout=8) as response:u.check(json.load(response).get('status')=='ok','Production health check failed')
  with self.engine.connect() as c:
   u.check(c.execute(self.text('SELECT DB_NAME()')).scalar_one()=='PMS','Wrong production database')
   u.check(c.execute(self.text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one()==self.pins['schema'],'Production schema changed')
 def preflight(self,*,record=True):
  self.verify_live();u.read_package(HERE/'candidate.zip',self.pins)
  import sqlalchemy,pyodbc
  u.check(sqlalchemy.__version__=='2.0.37' and pyodbc.version=='5.2.0','Unexpected server SQL dependency versions')
  with self.engine.connect() as c:
   version=str(c.execute(self.text("SELECT SERVERPROPERTY('ProductVersion')")).scalar_one());u.check(version.startswith('14.'),'SQL Server 2017 required')
   queues={table:c.execute(self.text('SELECT COUNT(*) FROM '+table+' WHERE status IN ('+statuses+')')).scalar_one() for table,statuses in [('erp_sync_task',"'queued','running','review'"),('pms_report_export_job',"'queued','running'"),('pms_feedback_notification',"'pending','waiting','processing'"),('pms_release_mail',"'pending','waiting','processing'")]}
   u.check(not any(queues.values()),'PMS background work active; preserve state and schedule another window')
  info={'host':'10.10.1.228','source_head':self.pins['baseline_head'],'runtime_commit':self.pins['baseline_runtime_commit'],'version':self.pins['baseline_version'],'schema':self.pins['schema'],'pid':self.process['pid'],'sql_version':version,'queues':queues,'protected_unchanged':True,'service_unchanged':True,'candidate':self.pins['commit']}
  u.save(HERE/('readonly-preflight-'+uuid.uuid4().hex[:8]+'.json'),info)
  if record:self.record('preflight-verified',**info)
  else:print('V130_READONLY_PREFLIGHT '+json.dumps(info),flush=True)
 def extract(self):
  files=u.read_package(HERE/'candidate.zip',self.pins);dest=HERE/'candidate';u.check(not dest.exists(),'Existing isolated candidate directory')
  dest.mkdir()
  for name,data in files.items():
   p=dest/name;p.parent.mkdir(parents=True,exist_ok=True)
   with p.open('xb') as stream:stream.write(data)
  u.save(HERE/'candidate-files.json',{name:u.digest(data) for name,data in files.items()})
  w.require_private_acl(HERE,self.owner)
 def backup_restore(self,username,password):return self.base.Rehearsal.backup_restore(self,username,password)
 def execute(self,reference):
  guard_reference(reference);self.preflight();self.extract();self.record('awaiting-local-sql-identity')
  username=password=None;payload={}
  try:
   username=hidden_input('SQL backup/restore administrator username (hidden): ').strip()
   password=hidden_input('SQL backup/restore password (hidden): ')
   self.verify_live();target=self.backup_restore(username,password);username=password=None
   self.verify_live();self.record('isolated-probe-running')
   payload=dict(database=target,source='PMS',host=self.settings.DB_HOST,port=self.settings.DB_PORT,driver=self.settings.DB_DRIVER,username=self.settings.DB_USER,password=self.settings.DB_PASSWORD)
   guard_child(payload)
   result=subprocess.run([sys.executable,'-B',str(HERE/'isolated_probe.py')],input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True,env=probe_environment(os.environ),timeout=180)
   payload.clear()
   u.check(result.returncode==0,'Isolated probe failed; inspect sanitized probe-error.json; no automatic retry')
   verification=json.loads((HERE/'isolated-verification.json').read_text(encoding='utf-8'))
   u.check(verification.get('passed') is True and verification.get('candidate')==self.pins['commit'] and verification.get('database')==target,'Isolated receipt target differs')
   self.verify_live();self.record('complete',verification=verification,service_unchanged=True,protected_configs_unchanged=True)
  finally:
   payload.clear();username=password=None;self.engine.dispose()

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--preflight-only',action='store_true');parser.add_argument('--approved-reference');args=parser.parse_args();worker=None
 try:
  if not args.preflight_only:guard_reference(args.approved_reference)
  worker=Rehearsal()
  if args.preflight_only:worker.preflight(record=False)
  else:worker.execute(args.approved_reference)
  return 0
 except Exception as error:
  if worker:worker.record('failed',error_type=type(error).__name__,gate_error=str(error) if type(error) is RuntimeError else None)
  print('V130_REHEARSAL_STOPPED '+type(error).__name__+'; no automatic retry, production change or cleanup',flush=True);return 1
 finally:
  if worker:worker.engine.dispose()
if __name__=='__main__':raise SystemExit(main())
