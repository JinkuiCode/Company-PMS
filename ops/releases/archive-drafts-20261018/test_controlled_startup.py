"""Actual ASGI lifespan/middleware in private SQLite copy; no listeners/external connections."""
import os,sys,json,tempfile,sqlite3,importlib.util,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
with tempfile.TemporaryDirectory(prefix='pms-controlled-fixture-') as folder:
    temporary=Path(folder);database=temporary/'fixture.db'
    source=sqlite3.connect('file:'+str(ROOT/'.runtime/data/pms-dev.db')+'?mode=ro',uri=True)
    target=sqlite3.connect(database)
    try:source.backup(target)
    finally:source.close();target.close()
    digest=lambda:hashlib.sha256(database.read_bytes()).hexdigest()
    before=digest()
    os.environ.update(PMS_CONFIG_FILE=os.devnull,PMS_ENV='development',DB_DIALECT='sqlite',SQLITE_DB_PATH=str(database),
        PMS_RELEASE_MANIFEST=str(ROOT/'.runtime/archive-draft-release-20261018/release.json'),SSO_ENABLED='false',ERP_SYNC_WORKER_ENABLED='false',PMS_RELEASE_MAIL_WORKER_ENABLED='false')
    sys.path[:0]=[str(HERE),str(ROOT/'backend')]
    spec=importlib.util.spec_from_file_location('controlled_acceptance_fixture',HERE/'controlled.py')
    controlled=importlib.util.module_from_spec(spec);spec.loader.exec_module(controlled)
    controlled.HERE=temporary
    import main
    # SQLite fixture cannot satisfy production MSSQL configuration validation. Replace ONLY that check;
    # use the actual production check-only lifespan, database readiness and deployed manifest loader.
    main.settings=main.settings.model_copy(update={'PMS_ENV':'production'})
    main.validate_runtime_config=lambda settings:None
    def refuse_init():raise AssertionError('Production startup must never invoke init_db')
    main.init_db=refuse_init
    from fastapi.testclient import TestClient
    with TestClient(controlled.app) as client:
        assert client.get('/api/health').json()=={'status':'ok'}
        for method,path in [('GET','/api/sso/callback'),('GET','/api/erp/logs/1'),('GET','/api/reports/purchase'),
                            ('GET','/api/users/oa-options'),('GET','/api/product-lines/options'),
                            ('POST','/api/form-drafts/archive-create'),('POST','/api/projects/archives')]:
            assert client.request(method,path).status_code==503,path
        proof=json.loads((temporary/'controlled-ready.json').read_text())
        assert proof['version']=='v1.1.0' and proof['commit']==controlled.h.CANDIDATE
        assert proof['background_workers_running']==[] and proof['maintenance_writes_blocked']
    from app.core.database import engine
    engine.dispose()
    assert digest()==before,'Read-only startup changed fixture bytes'
    print(json.dumps(dict(actual_asgi_lifespan=True,production_check_only_branch=True,sqlite_fixture_validation_exception=True,
        runtime_version=proof['version'],workers_running=[],fixture_bytes_unchanged=True,network_listeners=0,external_requests=0)))
