"""Approved loopback integration fixture: real combined routers/services + synthetic ERP.
Never imported by production. No existing config, database, external connector or worker.
"""
import os,json,secrets,socket,importlib.util
from pathlib import Path
from datetime import datetime,timedelta
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(os.environ['PMS_BATCH_TEST_OUTPUT']).resolve()
assert os.environ.get('PMS_BATCH_INTEGRATION')=='1'
assert OUT.is_relative_to(ROOT/'.runtime/batch-integration-20261022')
assert Path(os.environ['PMS_CONFIG_FILE']).resolve()==ROOT/'.runtime/batch-integration-20261022/empty.env'
assert Path(os.environ['PMS_CONFIG_FILE']).read_bytes()==b''
DB=Path(os.environ['SQLITE_DB_PATH']).resolve()
assert DB.is_relative_to(OUT) and not DB.exists()
assert os.environ.get('DB_DIALECT')=='sqlite'
os.environ['SECRET_KEY']=secrets.token_hex(32) # Fresh SYNTHETIC signing material only.
os.environ['PMS_BOOTSTRAP_ADMIN_USERNAME']='synthetic-bootstrap'
os.environ['PMS_BOOTSTRAP_ADMIN_PASSWORD']='Synthetic-only-9!'+secrets.token_hex(12)
os.environ['PMS_C2_TEST_OUTPUT']=str(OUT)
original_connect=socket.socket.connect
original_getaddrinfo=socket.getaddrinfo
def local_connect(sock,address):
    if isinstance(address,tuple) and address[0] not in ('127.0.0.1','::1'):
        raise RuntimeError('Integration fixture forbids external connections')
    return original_connect(sock,address)
def local_dns(host,*args,**kwargs):
    if host not in ('127.0.0.1','::1','localhost',None):raise RuntimeError('External DNS forbidden')
    return original_getaddrinfo(host,*args,**kwargs)
socket.socket.connect=local_connect;socket.getaddrinfo=local_dns

from app.core.config import settings
assert not settings.K3_URL and not settings.DB_HOST and not settings.SSO_ENABLED
assert not settings.ERP_SYNC_WORKER_ENABLED and not settings.PMS_RELEASE_MAIL_WORKER_ENABLED
from app.core.database import engine,get_db
from app.api import inventory_reports as inventory,purchase_reports as purchase,stock_detail_reports as stock
from app.services import report_export_jobs
# Capture ORIGINAL production scope functions before reusing C2's synthetic ERP.
scopes={name:getattr(inventory,name) for name in ('scoped_lines','authorized_organizations')}
project_scope=purchase.project_scope
scope_signature=report_export_jobs.scope_signature
from app.services.authorization import build_authorization_context,get_current_user_context
import material_reference_app as c2
for api in (inventory,purchase,stock):
    for name,function in scopes.items():setattr(api,name,function)
purchase.project_scope=project_scope
report_export_jobs.scope_signature=scope_signature
report_export_jobs.build_authorization_context=build_authorization_context

# Real explicit NEW-install path, on this fresh private file only.
spec=importlib.util.spec_from_file_location('batch_explicit_upgrade',ROOT/'backend/scripts/upgrade_database.py')
upgrade=importlib.util.module_from_spec(spec);spec.loader.exec_module(upgrade);upgrade.upgrade_database()
from app.services.database_revision import check_database_ready,CURRENT_DATABASE_REVISION
check_database_ready(engine)
from sqlalchemy.orm import sessionmaker
from app.models.rbac import SysUserRole,SysRoleMenu,SysMenu,SysRole,SysDept
from app.models.user import SysUser
from app.models.product_line import SysProductLine,SysRoleProductLine
from app.models.project import PmsProjectArchive
from app.models.dict import SysDict,SysDictItem
from app.models.form_draft import PmsFormDraft
from app.models.archive_change import ArchiveChange
from app.models.operation_log import SysOperationLog
from app.models.erp_task import ErpSyncTask
from app.services.archive_code_unique import lock_codes
from app.services.operation_log import serialize_model
from app.services import product_line_source
Session=sessionmaker(bind=engine,autoflush=False)
c2.engine.dispose();c2.Session=Session
app=c2.app
app.dependency_overrides.pop(get_current_user_context,None) # Real JWT and live RBAC.
from app.api import projects,form_drafts,archive_changes,form_draft_management,auth,users,dicts as dict_api,product_lines,operation_logs,document_history,offline_archives
for api in (projects,form_drafts,archive_changes,form_draft_management,auth,users,dict_api,product_lines,operation_logs,document_history,offline_archives):app.include_router(api.router)

PERMISSIONS=['project:archive:view','project:archive:add','project:archive:edit','project:archive:maintain','project:archive:draft:manage','project:archive:export','project:archive:toggle','report:purchase:view','report:purchase:export','report:inventory:view','report:inventory:export','report:stock-detail:list','report:stock-detail:view','report:stock-detail:export','system:operation-log:view']
ROLES={}
with Session() as db:
    dept=SysDept(dept_name='合成项目部',status=1);db.add(dept);db.flush()
    for uid,name in [(997,'合成操作者'),(998,'合成部门负责人'),(999,'合成受限用户')]:
        db.add(SysUser(id=uid,username='synthetic-'+str(uid),real_name=name,password_hash='synthetic-unusable',dept_id=dept.id,status=1,must_change_password=False,local_login_enabled=True,credential_version=0))
    db.flush();dept.leader_id=998
    for line_id,org,name in [(1,11,'合成产品线甲'),(2,12,'合成产品线乙'),(3,200292,'8吋Bench'),(4,499413,'12吋Bench')]:
        db.add(SysProductLine(id=line_id,source_key='kingdee',organization_id=org,organization_code=str(org),organization_name=name,display_name=name,name_key='synthetic-line-'+str(line_id),is_enabled=1,sort=line_id))
    db.flush()
    for uid in (997,998,999):
        role=SysRole(role_code='synthetic-'+str(uid),role_name='合成隔离角色'+str(uid),data_scope=4,status=1)
        db.add(role);db.flush();ROLES[uid]=role.id;db.add(SysUserRole(user_id=uid,role_id=role.id))
        for permission in PERMISSIONS:
            menu=db.query(SysMenu).filter_by(permission_code=permission).first()
            if menu is None:
                menu=SysMenu(menu_name=permission,menu_type='B',permission_code=permission,status=1);db.add(menu);db.flush()
            db.add(SysRoleMenu(role_id=role.id,menu_id=menu.id))
        for line_id in ([2] if uid==999 else [1,2,3,4]):db.add(SysRoleProductLine(role_id=role.id,product_line_id=line_id))
    # Use the already-accepted synthetic enum identities, never real catalogs.
    data=json.loads((ROOT/'frontend/tests/fixtures/archive-policy.json').read_text())
    for code,payload in data['enums'].items():
        definition=db.query(SysDict).filter_by(dict_code=code).first()
        if not definition:continue
        for item in payload.get('items',[]):
            value=str(item['value']);existing=db.query(SysDictItem).filter_by(dict_id=definition.id,item_value=value).first()
            if existing:existing.item_label=item['label'];existing.status=1
            else:db.add(SysDictItem(dict_id=definition.id,item_value=value,item_label=item['label'],status=1,sort=int(value)))
    db.flush();lock_codes(db.connection())
    db.add(PmsProjectArchive(project_code='BATCH-MAIN',project_name='合成主机',manager_id=997,business_product_line_id=3,archive_category=1,equipment_series=8,serial_no='BATCH-MAIN-SN',machine_model=1,quantity=1,quantity_unit=7,governance_legacy=True,erp_sync_policy='manual',created_at=datetime(2020,1,1)))
    db.add(PmsProjectArchive(project_code='BATCH-HIST',project_name='合成历史非主机',manager_id=997,business_product_line_id=3,archive_category=2,equipment_series=8,serial_no='BATCH-HIST-SN',governance_legacy=True,quantity=1,quantity_unit=7,erp_sync_policy='manual',created_at=datetime(2020,1,1)))
    db.add(PmsProjectArchive(project_code='BATCH-ADDRESS',project_name='合成历史地址',manager_id=997,business_product_line_id=3,archive_category=2,data_origin='kingdee_initial',governance_legacy=True,address_detail='  合成历史原地址  ',erp_sync_policy='manual',created_at=datetime(2020,1,1)))
    db.commit()
    # Deliberate pre-upgrade synthetic history: omission/default and hidden-value flows.
    for identifier,code,serial in [('00000000-0000-4000-8000-000000000001','BATCH-OLD-DRAFT','BATCH-OLD-SN'),('00000000-0000-4000-8000-000000000002','BATCH-SERIAL-DRAFT','BATCH-HIST-SN')]:
        db.add(PmsFormDraft(id=identifier,owner_id=997,resource='archive-create',product_line_id=3,version=3,status='active',payload_json=json.dumps({'project_code':code,'project_name':'合成历史草稿'+code,'archive_category':2,'product_line_id':3,'manager_id':998,'equipment_series':8,'serial_no':serial,'remarks':'合成历史隐藏备注'},ensure_ascii=False)))
    db.commit()

# The external ORGANIZATION catalog boundary alone is synthetic.
def organization(organization_id):
    with Session() as db:
        row=db.query(SysProductLine).filter_by(organization_id=organization_id,is_enabled=1).one()
        return SimpleNamespace(organization_id=row.organization_id,code=row.organization_code,name=row.organization_name,active=True)
product_line_source.get_organization=organization
product_lines.get_organization=organization

# Synthetic ERP business rows must respect the REAL computed organization grants.
from app.services.business_data_scope import ALL_DATA_SCOPE
def allowed(scope,query):
    values=None if scope is ALL_DATA_SCOPE else {getattr(v,'organization_id',v) for v in scope}
    selected=set(getattr(query,'organization_ids',[]) or [])
    if getattr(query,'organization_id',None) is not None:selected.add(query.organization_id)
    return (values is None or 11 in values) and (not selected or 11 in selected)
original_requests=c2.list_requests;original_overview=c2.list_overview;original_inventory=c2.list_inventory;original_stock=c2.stock_dataset
def requests(conn,query,scope):
    result=original_requests(conn,query,scope)
    return result if allowed(scope,query) else {'items':[],'total':0}
def overview(conn,query,scope):
    result=original_overview(conn,query,scope)
    return result if allowed(scope,query) else {'items':[],'total':0,'total_lines':0,'complete_lines':0,'review_lines':0}
def inventories(conn,query,scope):
    result=original_inventory(conn,query,scope)
    return result if allowed(scope,query) else {'items':[],'total':0}
def stocks(conn,query,scope):
    result=original_stock(conn,query,scope)
    return result if allowed(scope,query) else {'rows':[],'openings':{},'labels':{}}
purchase.list_requests=requests;purchase.list_overview=overview;inventory.list_inventory=inventories;stock.read_dataset=stocks;c2.fetch_service.read_dataset=stocks
c2.report_export_data.purchase_batches=lambda conn,query,scope:iter([requests(conn,query,scope)['items']])
c2.report_export_data.overview_batches=lambda conn,query,scope:iter([overview(conn,query,scope)['items']])
def inventory_batches(conn,query,scope):
    # Preserve production narrowing and execution-time reference validation; only rows are synthetic.
    from app.services.inventory_reader import effective_organizations
    from app.services.report_material_reference import validate_reference_query
    effective=effective_organizations(query,scope)
    if effective==[]:return
    validate_reference_query(conn,query,effective)
    yield inventories(conn,query,effective)['items']
c2.report_export_data.inventory_batches=inventory_batches

from jose import jwt
@app.get('/api/test/batch-bootstrap')
def bootstrap():
    # Only synthetic bearer sessions. Never write these values to evidence logs.
    return {'tokens':{str(uid):jwt.encode({'sub':str(uid),'credential_version':0,'auth_method':'password','scope':'full','exp':datetime.utcnow()+timedelta(hours=1)},settings.SECRET_KEY,algorithm=settings.ALGORITHM) for uid in (997,998,999)},'synthetic':True,'revision':CURRENT_DATABASE_REVISION}
@app.get('/api/test/batch-state')
def batch_state():
    with Session() as db:
        return {'revision':CURRENT_DATABASE_REVISION,'archives':[serialize_model(a) for a in db.query(PmsProjectArchive)],'drafts':[{'id':d.id,'status':d.status,'version':d.version} for d in db.query(PmsFormDraft)],'pending':db.query(ArchiveChange).filter_by(status=2).count(),'logs':db.query(SysOperationLog).count(),'erp_queued_only':db.query(ErpSyncTask).count(),'workers_started':False,'synthetic_only':True}
@app.post('/api/test/batch-permission')
def set_permission(body:dict):
    assert body['user_id'] in ROLES and body['permission'] in PERMISSIONS
    with Session() as db:
        menu=db.query(SysMenu).filter_by(permission_code=body['permission']).first();role=ROLES[body['user_id']]
        db.query(SysRoleMenu).filter_by(role_id=role,menu_id=menu.id).delete()
        if body['enabled']:db.add(SysRoleMenu(role_id=role,menu_id=menu.id))
        db.commit()
    return {'synthetic_only':True}
