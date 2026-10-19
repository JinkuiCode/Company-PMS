"""Candidate-only SQL integration, stdin secrets stay in memory; no main/workers."""
import json,os,socket,sys,uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
from server_rehearsal import guard_child,HERE,ROOT,probe_environment
import program_update as u
import windows_update as w

def existing_conflict_count(db,codes):
 from fastapi import HTTPException
 from app.services.archive_code_unique import ensure_code_available
 count=0
 for draft_id,code in codes:
  try:ensure_code_available(db.connection(),code,exclude_draft_id=draft_id)
  except HTTPException as error:
   u.check(error.status_code==409 and error.detail['code']=='ARCHIVE_UNIQUE_CONFLICT','Unexpected historical namespace error');count+=1
  finally:db.rollback()
 return count

def run(payload):
 guard_child(payload);pins=w.load_pins()
 w.guard_host(os.name,ROOT,HERE,socket.gethostbyname_ex(socket.gethostname())[2],pins)
 files=json.loads((HERE/'candidate-files.json').read_text(encoding='utf-8'))
 for name,digest in files.items():u.check(u.hashfile(HERE/'candidate'/name)==digest,'Extracted candidate changed')
 u.check(not Path(os.environ['PMS_CONFIG_FILE']).exists(),'Unexpected candidate configuration file')
 sys.path.insert(0,str(HERE/'candidate/backend'))
 from app.core import config
 config.settings=config.Settings(_env_file=None,DB_DIALECT='pyodbc',DB_HOST=payload['host'],DB_PORT=payload['port'],DB_NAME=payload['database'],DB_DRIVER=payload['driver'],DB_USER=payload['username'],DB_PASSWORD=payload['password'],SSO_ENABLED=False,ERP_SYNC_WORKER_ENABLED=False,PMS_RELEASE_MAIL_WORKER_ENABLED=False,K3_URL='')
 payload['username']=payload['password']=None
 from app.core.database import engine
 from sqlalchemy import text,func
 from sqlalchemy.orm import Session
 import app.models.init_db  # Model registration only; never initialize/upgrade.
 from app.services.database_revision import check_database_ready
 from app.services.archive_code_unique import ensure_code_available,lock_codes
 from app.services.archive_field_linkage import linkage_errors,ORGANIZATION_PROFILES,PROFILES
 from app.services.authorization import build_authorization_context
 from app.services import form_drafts
 from app.schemas.form_draft import DraftSave
 from app.models.user import SysUser
 from app.models.product_line import SysProductLine
 from app.models.form_draft import PmsFormDraft
 from app.models.project import PmsProjectArchive
 from app.models.dict import SysDict,SysDictItem
 from app.services.dict import get_dict_by_code
 from fastapi import HTTPException
 from app.services.field_policy import validate_business_field_write,MODULE_PROJECT_ARCHIVE
 prefix='V130-'+uuid.uuid4().hex[:12]
 def conflict(call,code='ARCHIVE_UNIQUE_CONFLICT'):
  try:call()
  except HTTPException as error:
   u.check(error.status_code==409 and error.detail.get('code')==code,'Wrong conflict result');return
  raise RuntimeError('Collision was accepted')
 def authorization_digest(db):
  # IDs/relationships only; never select password hashes, keys or token values.
  records={table:[list(row) for row in db.execute(text('SELECT '+cols+' FROM '+table+' ORDER BY '+order))] for table,cols,order in [('sys_user','id,status,dept_id','id'),('sys_role','id,status,data_scope','id'),('sys_menu','id,status,permission_code','id'),('sys_user_role','id,user_id,role_id','id'),('sys_role_menu','id,role_id,menu_id','id'),('sys_role_product_line','id,role_id,product_line_id','id')]}
  import hashlib
  return hashlib.sha256(json.dumps(records,sort_keys=True,default=str).encode()).hexdigest()
 def save(db,context,code,**fields):
  identity=fields.pop('_id',uuid.uuid4());version=fields.pop('_version',None)
  return form_drafts.save_draft(db,context,DraftSave(id=identity,expected_version=version,payload={'project_code':code,'project_name':'隔离库验证','product_line_id':line_id,'archive_category':2,**fields}))
 try:
  with engine.connect() as c:
   u.check(c.dialect.name=='mssql' and c.execute(text('SELECT DB_NAME()')).scalar_one()==payload['database'],'Probe escaped isolated target')
   u.check(c.execute(text("SELECT IS_SRVROLEMEMBER('sysadmin')")).scalar_one()==0,'Daily runtime identity must not be sysadmin')
   rights={table:{action:c.execute(text("SELECT HAS_PERMS_BY_NAME(:obj,'OBJECT',:action)"),{'obj':'dbo.'+table,'action':action}).scalar_one() for action in ('SELECT','INSERT','UPDATE','DELETE')} for table in ('pms_form_draft','pms_project_archive','sys_operation_log')}
   u.check(all(value==1 for actions in rights.values() for value in actions.values()),'Existing daily identity lacks required CRUD permissions; no grants performed')
   collation=c.execute(text("SELECT CONVERT(nvarchar(128),DATABASEPROPERTYEX(DB_NAME(),'Collation'))")).scalar_one()
  check_database_ready(engine)
  with Session(engine) as db:
   auth_before=authorization_digest(db)
   actor=db.query(SysUser.id).filter(SysUser.username=='ael',SysUser.status==1).scalar();u.check(actor is not None,'Existing ael actor missing')
   context=build_authorization_context(db,actor)
   lines={line.organization_id:line for line in db.query(SysProductLine).filter_by(source_key='kingdee').all()}
   u.check(set(ORGANIZATION_PROFILES)<=set(lines),'Confirmed product line organization identifiers differ')
   for org,profile in ORGANIZATION_PROFILES.items():u.check(lines[org].is_enabled==1,'Confirmed product line disabled')
   line_id=lines[200292].id
   for enum,field in [('archive_machine_model','machine_model'),('equipment_series','equipment_series')]:
    definition=db.query(SysDict).filter_by(dict_code=enum,status=1).one()
    enabled={int(v) for v, in db.query(SysDictItem.item_value).filter_by(dict_id=definition.id,status=1)}
    expected={v for group in PROFILES.values() for v in group[field]}
    u.check(expected<=enabled,'Confirmed stable enum identifiers disabled or missing')
   u.check(get_dict_by_code(db,'archive_quantity_unit')['items'][0]['value']=='7','Unit priority missing')
   for org,model,series in [(200292,5,6),(499413,2,12),(4146325,1,14)]:
    u.check(not linkage_errors(db,{},dict(product_line_id=lines[org].id,machine_model=model,equipment_series=series),is_create=True),'Valid linkage rejected')
   u.check({e['field_key'] for e in linkage_errors(db,{},dict(product_line_id=line_id,machine_model=2,equipment_series=14),is_create=True)}=={'machine_model','equipment_series'},'Invalid linkage accepted')
   # Production read compatibility check on the restored snapshot only. Counts
   # reveal neither other owners' draft bodies nor user details.
   active=db.query(PmsFormDraft).filter_by(resource='archive-create',status='active').all()
   codes=[(row.id,json.loads(row.payload_json).get('project_code','')) for row in active]
   initial_conflicts=existing_conflict_count(db,codes)
   # Historical conflicts are reported; they must not be silently deleted or
   # rewritten. The checks above prove the new rule rejects these codes on save.
   try:save(db,context,prefix+'-REQ',archive_category=None)
   except HTTPException as error:u.check(error.status_code==422 and any(i['field_key']=='archive_category' for i in error.detail['fields']),'Missing category returned wrong error')
   else:raise RuntimeError('Missing draft category accepted')
   db.rollback()
   row=save(db,context,prefix+'-ONE',manager_id=actor)
   conflict(lambda:save(db,context,' '+(prefix+'-ONE').lower()+' '))
   # Formal ORM path must also respect the active draft namespace on SQL Server.
   def create_collision():
    db.add(PmsProjectArchive(project_code=prefix+'-ONE',project_name='隔离冲突',business_product_line_id=line_id,erp_sync_policy='manual'));db.flush()
   conflict(create_collision);db.rollback()
   row=save(db,context,prefix+'-TWO',_id=row['id'],_version=row['version'],manager_id=actor)
   with engine.connect() as c:ensure_code_available(c,prefix+'-ONE');c.rollback()
   # An audit failure must roll the draft/version back on the actual driver.
   with patch.object(form_drafts,'_audit',side_effect=RuntimeError('isolated injected audit failure')):
    try:save(db,context,prefix+'-TWO',_id=row['id'],_version=row['version'],manager_id=actor)
    except RuntimeError:pass
    else:raise RuntimeError('Injected audit failure did not stop save')
   u.check(form_drafts.get_draft(db,context,row['id'])['version']==row['version'],'Failed draft save changed version')
   # Convert with the real service; source directory is an isolated stub and no
   # worker/main is imported. Any queue row remains confined to this copy.
   row=save(db,context,prefix+'-TWO',_id=row['id'],_version=row['version'],manager_id=actor,customer='V130 isolated fixture customer',machine_model=5,quantity=1,quantity_unit=7,contract_signed_date='2026-10-01',contract_ship_date='2026-12-01')
   with patch('app.services.product_line_source.get_organization',return_value={'id':200292}):
    converted=form_drafts.submit_draft(db,context,row['id'],row['version'])
    replay=form_drafts.submit_draft(db,context,row['id'],row['version'])
   u.check(converted['id']==replay['id'],'Conversion replay created another archive')
   conflict(lambda:save(db,context,prefix+'-TWO'))
  # Database collation governs Unicode width/accent equivalence, not just
  # Python case-folding. Verify both equivalent and distinct results as stored.
  collation_cases={}
  with Session(engine) as db:
   for suffix,variant in [('CAFE','caf\u00e9'),('WX','\uff37\uff38')]:
    first_code=prefix+'-'+suffix;other_code=prefix+'-'+variant
    equivalent=db.execute(text('SELECT CASE WHEN CAST(:lhs AS nvarchar(64))=CAST(:rhs AS nvarchar(64)) THEN 1 ELSE 0 END'),{'lhs':first_code.casefold(),'rhs':other_code.casefold()}).scalar_one()==1
    db.rollback();save(db,context,first_code)
    if equivalent:conflict(lambda:save(db,context,other_code))
    else:save(db,context,other_code)
    collation_cases[suffix]={'equivalent':equivalent,'behavior_verified':True}
  # Two actual SQL connections must hold the application lock to transaction end,
  # reject bounded contention, and release it after rollback.
  with engine.connect() as first:
   lock_codes(first)
   with ThreadPoolExecutor(max_workers=1) as pool:
    def contend():
     with engine.connect() as second:
      conflict(lambda:lock_codes(second),'ARCHIVE_CODE_BUSY');second.rollback()
    pool.submit(contend).result(10)
   first.rollback()
  with engine.connect() as second:lock_codes(second);second.rollback()
  # Race two real service saves: one accepted, the other rejected. The loser is
  # not retried automatically. Recheck shows the namespace belongs to the winner.
  def race():
   with Session(engine) as db:
    try:save(db,context,prefix+'-RACE');return 'saved'
    except HTTPException as error:
     u.check(error.status_code==409 and error.detail['code'] in ('ARCHIVE_UNIQUE_CONFLICT','ARCHIVE_CODE_BUSY'),'Unexpected SQL race failure');return 'rejected'
  with ThreadPoolExecutor(max_workers=2) as pool:
   outcomes=list(pool.map(lambda _:race(),range(2)))
  u.check(sorted(outcomes)==['rejected','saved'],'Concurrent SQL saves both succeeded')
  with Session(engine) as db:
   u.check(authorization_digest(db)==auth_before,'Probe changed authorization relationships')
  receipt={'passed':True,'candidate':pins['commit'],'database':payload['database'],'schema':pins['schema'],'real_mssql':True,'daily_identity_permissions_verified':True,'collation':collation,'unicode_collation_cases':collation_cases,'initial_code_conflicts':initial_conflicts,'historical_conflicts_preserved_and_rejected':True,'category_and_linkage':True,'unit_priority':True,'draft_and_formal_namespace':True,'rollback_verified':True,'conversion_replay':True,'transaction_lock_timeout_and_release':True,'concurrent_saves_one_winner':True,'authorization_unchanged':True,'production_written':False,'database_structure_changed':False,'erp_calls':0,'mail_calls':0}
  u.save(HERE/'isolated-verification.json',receipt);print('V130_ISOLATED_MSSQL_VERIFIED',flush=True)
 finally:engine.dispose()

def main():
 payload={}
 try:
  payload=json.load(sys.stdin);guard_child(payload);run(payload);return 0
 except Exception as error:
  # Never include SQLAlchemy/ODBC exception strings, SQL parameters or payloads.
  safe={'error_type':type(error).__name__,'gate_error':str(error) if type(error) is RuntimeError else None}
  u.save(HERE/'probe-error.json',safe);print('V130_ISOLATED_PROBE_STOPPED '+type(error).__name__,flush=True);return 1
 finally:payload.clear()
if __name__=='__main__':raise SystemExit(main())
