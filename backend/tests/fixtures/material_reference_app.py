"""Loopback-only C2 browser fixture. Never import this from the application."""
import json
import os
import socket
import tempfile
from pathlib import Path
import sys
from contextlib import contextmanager
from datetime import date,datetime
from decimal import Decimal
from threading import Event
from threading import Lock
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from material_reference_contract import Cursor
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base,get_db
import app.models.init_db
from app.services.authorization import get_current_user_context
from app.api import purchase_reports as purchase,inventory_reports as inventory,stock_detail_reports as stock,report_exports
from app.services import inventory_reader,purchase_reader,report_export_data,report_export_jobs,purchase_connection,report_material_reference
from app.services.report_filters import matches_filters
from app.services.stock_detail_balance import InventoryKey
import app.services.stock_detail_fetch as fetch_service

original_connect=socket.socket.connect
def loopback_connect(sock,address):
    if isinstance(address,tuple) and address[0] not in ('127.0.0.1','::1'):
        raise RuntimeError('C2 fixture forbids external connections')
    return original_connect(sock,address)
socket.socket.connect=loopback_connect

temporary_db=tempfile.TemporaryDirectory(prefix='c2-fixture-',dir=os.environ['PMS_C2_TEST_OUTPUT'])
engine=create_engine('sqlite:///'+str(Path(temporary_db.name)/'pms-fixture.sqlite'),connect_args={'check_same_thread':False})
Base.metadata.create_all(engine)
Session=sessionmaker(bind=engine)
ctx={'user_id':997,'permissions':['report:purchase:view','report:purchase:export','report:inventory:view','report:inventory:export','report:stock-detail:list','report:stock-detail:view','report:stock-detail:export'],'product_line_ids':[1,2],'data_scope':4}
master=Cursor();master.add('0007-A','合成甲',11);master.add('0008-B','合成乙',11)
master.db.execute('CREATE TABLE dbo.T_ORG_ORGANIZATIONS_L(FORGID INTEGER,FNAME TEXT,FLOCALEID INTEGER)')
master.db.executemany('INSERT INTO dbo.T_ORG_ORGANIZATIONS_L VALUES (?,?,2052)',[(11,'合成组织甲'),(12,'合成组织乙')])
for i in range(510):master.add(f'MAT-{i:04}','合成分页'+str(i),11)
for i in range(180):master.add(f'LONG-{i:04}-'+('X'*12),'合成长编码'+str(i),11)
calls=[]
fixture_errors=[]
master_lock=Lock()
class MasterCursor(Cursor):
    def __init__(self):
        master_lock.acquire();self.closed=False;self.db=master.db;self.calls=[]
    def close(self):
        if not self.closed:self.closed=True;master_lock.release()
class Connection:
    def cursor(self):
        return MasterCursor()
@contextmanager
def connection():yield Connection()
def db_session():
    with Session() as db:yield db
lines=[SimpleNamespace(id=i,organization_id=org,display_name=label,is_enabled=True) for i,org,label in [(1,11,'合成产品线甲'),(2,12,'合成产品线乙')]]
for api in [purchase,inventory,stock]:
    api.purchase_connection=connection
    api.authorized_organizations=lambda db,context:[11,12]
    api.scoped_lines=lambda db,context:lines
inventory.resolve_product_lines=lambda *args:None
inventory_reader.resolve_product_lines=lambda *args:None
purchase.project_scope=lambda *args:[purchase_reader.OrganizationGrant(11),purchase_reader.OrganizationGrant(12)]
purchase.enrich_product_lines=lambda *args:None
purchase._rows=lambda *args:[{'id':11,'name':'合成组织甲'},{'id':12,'name':'合成组织乙'}]
stock.enrich_stock_product_lines=lambda *args:None
purchase_connection.purchase_connection=connection
report_export_data.purchase_connection=connection
report_export_jobs.scope_signature=lambda *args:'synthetic-c2-scope'
report_export_jobs.build_authorization_context=lambda *args:ctx
report_export_jobs.EXPORT_ROOT=Path(os.environ['PMS_C2_TEST_OUTPUT'])/'exports'

def purchase_rows(query):
    rows=[dict(id=i+1,organization_id=11,project_code='C2-P1',product_line_name='合成产品线甲',bill_no=f'REQ-{i+1}',line_no=i+1,
        material_code=code,material_name=name,application_date='2026-10-10',unit_name='个',document_status='C',
        progress='complete',requested=1,approved=1,ordered=1,received=1,apply_quantity=1,approved_quantity=1,order_quantity=1,received_quantity=1) for i,(code,name) in enumerate([('0007-A','合成甲'),('0008-B','合成乙'),('OTHER','不在选择范围')])]
    return [r for r in rows if matches_filters(r,query.conditions())]
def list_requests(conn,query,scope):
    calls.append({'kind':'purchase','parameters':query.model_dump(mode='json')})
    rows=purchase_rows(query);return dict(items=rows,total=len(rows))
def list_overview(conn,query,scope):
    calls.append({'kind':'overview','parameters':query.model_dump(mode='json')})
    count=len(purchase_rows(query))
    rows=[dict(id='11:C2-P1',organization_id=11,product_line_name='合成产品线甲',project_code='C2-P1',project_name='',total_lines=count,complete_lines=count,receiving_lines=0,ordering_lines=0,not_ordered_lines=0,review_lines=0,completion_rate=100,conversion_rate=100)] if count else []
    return dict(items=rows,total=len(rows),total_lines=count,complete_lines=count,review_lines=0)
def list_inventory(conn,query,scope):
    calls.append({'kind':'inventory','parameters':query.model_dump(mode='json')})
    rows=[dict(FID=str(i),product_line_name='合成产品线甲',MaterialCode=code,MaterialName=name,Stock='合成仓库',FBaseQty='6',Unit='个') for i,(code,name) in enumerate([('0007-A','合成甲'),('0008-B','合成乙'),('OTHER','不在选择范围')])]
    rows=[r for r in rows if matches_filters(r,query.conditions())]
    return dict(items=rows,total=len(rows))
def stock_dataset(conn,query,scope):
    report_material_reference.validate_reference_query(conn,query,scope)
    calls.append({'kind':'stock','parameters':query.model_dump(mode='json')})
    selected=query.material_codes or [code for code in ['0007-a','0008-b'] if query.material.lower() in code]
    rows=[];openings={};labels={}
    for i,(code,name) in enumerate([('0007-A','合成甲'),('0008-B','合成乙')]):
        if code.lower() not in selected:continue
        key=InventoryKey(11,10+i,20,10000,'BD_OwnerOrg',11,10087)
        openings[key]=Decimal(i*10+5);labels[key]=dict(product_line_name='合成产品线甲',material_code=code,material_name=name,stock_name='合成仓库',unit_name='个')
        rows.append(dict(**labels[key],inventory_key=key,row_id='fixture:'+str(i),bill_date=date(2026,10,10),created_at=datetime(2026,10,10),source_order=0,bill_name='合成入库',bill_no='IN-'+str(i),bill_seq=i+1,income_qty=Decimal(6),issue_qty=Decimal(0)))
    return dict(rows=rows,openings=openings,labels=labels)
purchase.list_requests=list_requests;purchase.list_overview=list_overview
inventory.list_inventory=list_inventory
stock.read_dataset=stock_dataset;fetch_service.read_dataset=stock_dataset
def inventory_batches(conn,query,scope):
    report_material_reference.validate_reference_query(conn,query,scope)
    yield list_inventory(conn,query,scope)['items']
report_export_data.inventory_batches=inventory_batches
report_export_data.overview_batches=lambda conn,query,scope:iter([list_overview(conn,query,scope)['items']])
report_export_data.purchase_batches=lambda conn,query,scope:iter([list_requests(conn,query,scope)['items']])
purchase_reader.load_chains=lambda conn,rows:{r['id']:dict(orders=[],receipts=[],summary={}) for r in rows}
purchase_reader._decorate_rows=lambda *args,**kwargs:None
write_report=report_export_data.write_report
def checked_write_report(*args):
    try:return write_report(*args)
    except Exception as error:
        import traceback
        traceback.print_exc()
        fixture_errors.append(type(error).__name__+': '+str(error))
        raise
report_export_data.write_report=checked_write_report

app=FastAPI()
for api in [purchase,inventory,stock,report_exports]:app.include_router(api.router)
app.dependency_overrides[get_db]=db_session
app.dependency_overrides[get_current_user_context]=lambda:ctx
@app.get('/api/test/state')
def state():return {'calls':calls,'errors':fixture_errors,'synthetic':True}
@app.post('/api/test/run-exports')
def run_exports():
    with Session() as db:report_export_jobs.run_next(db,Event())
    return {'done':True}
