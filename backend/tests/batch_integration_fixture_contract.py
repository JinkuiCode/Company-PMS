"""Integration adapter trust boundaries; new private SQLite and synthetic ERP only."""
from pathlib import Path
import os,sys,subprocess,tempfile,json
ROOT=Path(__file__).resolve().parents[2]
if '--worker' not in sys.argv:
    output=ROOT/'.runtime/batch-integration-20261022/evidence'
    run=Path(tempfile.mkdtemp(prefix='adapter-',dir=output))
    empty=ROOT/'.runtime/batch-integration-20261022/empty.env'
    assert empty.read_bytes()==b''
    env={'PATH':os.environ['PATH'],'LANG':'en_US.UTF-8','DB_DIALECT':'sqlite','PMS_CONFIG_FILE':str(empty),'SQLITE_DB_PATH':str(run/'private.sqlite'),'PMS_BATCH_INTEGRATION':'1','PMS_BATCH_TEST_OUTPUT':str(run),'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':':'.join([str(ROOT/'backend/tests/fixtures'),str(ROOT/'backend/tests'),str(ROOT/'backend'),'/Users/jin/Code/PMS/backend/.venv-deps312'])}
    p=subprocess.run([sys.executable,__file__,'--worker'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (run/'execution.log').write_bytes(p.stdout)
    (output/'adapter-contract.json').write_text(json.dumps({'command':[sys.executable,'backend/tests/batch_integration_fixture_contract.py'],'exit_code':p.returncode,'evidence':str(run.relative_to(ROOT))},indent=2)+'\n')
    print(p.stdout.decode()[-2200:]);raise SystemExit(p.returncode)

from fastapi.testclient import TestClient
import batch_integration_app as f
from openpyxl import load_workbook
from io import BytesIO
checks=[]
with TestClient(f.app) as client:
    tokens=client.get('/api/test/batch-bootstrap').json()['tokens']
    headers={'Authorization':'Bearer '+tokens['997']}
    def get(url,status=200):
        r=client.get(url,headers=headers);assert r.status_code==status,r.text;return r
    def post(url,body=None,status=200):
        r=client.post(url,headers=headers,json=body);assert r.status_code==status,r.text;return r.json()
    assert get('/api/reports/inventory?organization_id=12').json()['items']==[]
    job=post('/api/report-exports',{'report':'inventory','parameters':{'organization_id':12},'columns':['MaterialCode']},202)
    post('/api/test/run-exports')
    completed=get('/api/report-exports/'+job['id']).json();assert completed['status']=='success',completed
    book=load_workbook(BytesIO(get('/api/report-exports/'+job['id']+'/download').content),read_only=True)
    assert len(list(book.active.values))==1;book.close()
    checks.append('authorized11/12, selected12: actual inventory API+execution+download contain no org11 rows')
    filters=json.dumps([{'field':'MaterialCode','operator':'reference','value':['0007-a'],'valueEnd':None,'schemaVersion':2}])
    job=post('/api/report-exports',{'report':'inventory','parameters':{'organization_id':11,'filters':filters},'columns':['MaterialCode']},202)
    with f.c2.master_lock:f.c2.master.db.execute("DELETE FROM dbo.T_BD_MATERIAL WHERE FNUMBER='0007-A'")
    post('/api/test/run-exports')
    failed=get('/api/report-exports/'+job['id']).json();assert failed['status']=='failed',failed
    get('/api/report-exports/'+job['id']+'/download',409)
    checks.append('material reference removed after enqueue: execution-time validation fails job and download denied')
    job=post('/api/report-exports',{'report':'inventory','parameters':{'organization_id':11},'columns':['MaterialCode']},202)
    post('/api/test/batch-permission',{'user_id':997,'permission':'report:inventory:export','enabled':False})
    post('/api/test/run-exports')
    get('/api/report-exports/'+job['id'],403)
    with f.Session() as db:
        from app.models.report_export import ReportExportJob
        assert db.get(ReportExportJob,job['id']).status=='failed'
    checks.append('permission revoked after enqueue: real current authorization fails worker and existing JWT cannot inspect/download job')
    assert f.batch_state()['workers_started'] is False
Path(os.environ['PMS_BATCH_TEST_OUTPUT'],'result.json').write_text(json.dumps({'passed':True,'checks':checks,'syntheticOnly':True},indent=2)+'\n')
print('PASS',*checks,sep='\n')
