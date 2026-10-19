"""Actual pinned app lifespan in a read-only-source SQLite copy; no sockets/listeners."""
import hashlib,json,os,socket,sqlite3,sys,tempfile,threading
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(HERE),str(ROOT/'.runtime/feedback-reference-fixed-20261019/source/backend'),str(ROOT/'backend/.venv-deps312')]
def deny(*args,**kw):raise AssertionError('ISOLATED_NETWORK_DENIED')
socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny
with tempfile.TemporaryDirectory(prefix='pms-v120-controlled-') as d:
    tmp=Path(d);db=tmp/'copy.db'
    source=sqlite3.connect('file:'+str(ROOT/'.runtime/data/pms-dev.db')+'?mode=ro',uri=True);dest=sqlite3.connect(db)
    try:source.backup(dest)
    finally:source.close();dest.close()
    before=hashlib.sha256(db.read_bytes()).hexdigest()
    os.environ.update(PMS_CONFIG_FILE=os.devnull,PMS_ENV='development',DB_DIALECT='sqlite',SQLITE_DB_PATH=str(db),PMS_RELEASE_MANIFEST=str(ROOT/'.runtime/feedback-reference-fixed-20261019/pms-v1.2.1-f15d4f45-20261019/release.json'),SSO_ENABLED='false',ERP_SYNC_WORKER_ENABLED='true',PMS_RELEASE_MAIL_WORKER_ENABLED='true',DB_USER='',DB_PASSWORD='',K3_URL='')
    import controlled
    restore=controlled.pause_workers()
    try:
        import main
        main.settings=main.settings.model_copy(update={'PMS_ENV':'production'})
        # Only production-MSSQL config validation is replaced for this SQLite fixture.
        main.validate_runtime_config=lambda settings:None
        def refuse_init():raise AssertionError('Production must not run schema initialization')
        main.init_db=refuse_init
        from app.services.runtime_release import load_runtime_manifest
        app=controlled.configure(main.app,load_runtime_manifest,tmp/'proof.json')
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            assert client.get('/api/health').json()=={'status':'ok'}
            for method,path in [('POST','/api/projects/archives'),('PUT','/api/form-drafts/1'),('POST','/api/releases/publish'),('GET','/api/erp/config'),('GET','/api/reports/inventory'),('GET','/api/sso/oa-login'),('GET','/api/users/oa-options'),('GET','/api/product-lines/organizations')]:
                assert client.request(method,path).status_code==503,(method,path)
            proof=json.loads((tmp/'proof.json').read_text());pins=json.loads((HERE/'pins.json').read_text())
            assert proof['version']=='v1.2.1' and proof['commit']==pins['commit']
            assert proof['background_workers_running']==[] and proof['maintenance_writes_blocked']
            assert not [t.name for t in threading.enumerate() if t.name in controlled.WORKERS]
        from app.core.database import engine
        engine.dispose();assert hashlib.sha256(db.read_bytes()).hexdigest()==before
        print(json.dumps(dict(pinned_candidate=pins['commit'],actual_asgi_lifespan=True,production_check_only_branch=True,sqlite_fixture_config_exception=True,all_four_workers_suppressed=True,blocked_paths=8,fixture_bytes_unchanged=True,network_connections=0,listeners=0)))
    finally:restore()
