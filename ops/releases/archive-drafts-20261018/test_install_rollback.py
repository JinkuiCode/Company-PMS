"""Real Git/file install and program rollback in disposable local clones; no services or SQL."""
import json,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
import cutover as c
import rollback as rb
original_run=c.h.run

def local_run(argv,**kwargs):
    if argv[0]=='git.exe':argv=['git',*argv[1:]]
    return original_run(argv,**kwargs)

missing_dist=sys.argv[1:]==['--missing-live-dist']
assert not sys.argv[1:] or missing_dist
baseline=ROOT/'.runtime/log-reference-windows-20261016/source'
assert local_run(['git','-C',str(baseline),'rev-parse','HEAD'])==c.h.BASELINE
artifacts=c.ARTIFACTS
with tempfile.TemporaryDirectory(prefix='pms-draft-install-rollback-') as folder:
    root=Path(folder)/'PMS';work=Path(folder)/'work';work.mkdir()
    local_run(['git','clone','--no-checkout','--shared',str(baseline),str(root)])
    local_run(['git','-C',str(root),'-c','core.autocrlf=false','checkout','--detach',c.h.BASELINE])
    (root/'frontend/dist').mkdir(parents=True);(root/'frontend/dist/index.html').write_bytes(b'OLD FRONTEND')
    old_manifest=dict(version='v1.0.2',commit=c.h.BASELINE,database_revision=c.h.PREVIOUS)
    (root/'release.json').write_text(json.dumps(old_manifest))
    old_release=(root/'release.json').read_bytes()
    for name in ('source.bundle','candidate.zip'):shutil.copy2(artifacts/name,work/name)
    c.h.extract_package(work/'candidate.zip',work/'candidate')
    previous=work/'previous-program';previous.mkdir()
    old_dist=c.backup_tree(root/'frontend/dist',previous/'dist')
    local_run(['git','-C',str(root),'archive','--format=zip','--output='+str(previous/'source.zip'),c.h.BASELINE])
    local_run(['git','-C',str(root),'bundle','create',str(previous/'history.bundle'),'HEAD'])
    shutil.copy2(root/'release.json',previous/'release.json')
    c.h.save(previous/'backup-manifest.json',dict(source_sha256=c.h.hashfile(previous/'source.zip'),history_sha256=c.h.hashfile(previous/'history.bundle'),dist=old_dist,protected={},runtime={'runtime_manifest_sha256':c.h.hashfile(previous/'release.json')}),new=True)
    c.ROOT=root;c.HERE=work;c.h.run=local_run
    instance=c.Cutover.__new__(c.Cutover);instance.state=dict(backend_stopped=True,phase='formal-upgrade-verified',database_revision=c.h.CURRENT,business_preserved=True,protected_configs_unchanged=True);instance.protected={};instance.result_url=None
    instance.install()
    assert local_run(['git','-C',str(root),'rev-parse','HEAD'])==c.h.CANDIDATE
    assert (previous/'live-dist-before-swap/index.html').read_bytes()==b'OLD FRONTEND'
    _,files=c.h.read_package(work/'candidate.zip')
    for name,data in files.items():
        if name!='SHA256SUMS':assert (root/name).read_bytes()==data,name
    c.guard_checkout_status(local_run(['git','-C',str(root),'status','--porcelain']),allow_manifest=True)
    if missing_dist:shutil.rmtree(root/'frontend/dist')
    restored=rb.ProgramRollback.__new__(rb.ProgramRollback);restored.backup=previous;restored.manifest=rb.verify_program_backup(previous);restored.displaced=work/'rollback-displaced'
    # Only the database/listener checks are replaced: this test never imports app/SQL or starts services.
    verified=[];restored.verify=lambda:verified.append(True)
    calls=[];c.ps=lambda script:calls.append(script)
    restored.restore();restored.verify_restored()
    assert verified==[True]
    assert local_run(['git','-C',str(root),'rev-parse','HEAD'])==c.h.BASELINE
    assert (root/'frontend/dist/index.html').read_bytes()==b'OLD FRONTEND'
    assert (root/'release.json').read_bytes()==old_release
    if not missing_dist:assert (restored.displaced/'dist/index.html').read_bytes()==files['frontend/dist/index.html']
    else:assert not (restored.displaced/'dist').exists()
    assert all('Stop-Process' not in s and 'Start-Process' not in s for s in calls)
    result=dict(disposable_clone=True,installed_file_count=len(files)-1,old_dist_preserved=True,rollback_old_source_verified=True,rollback_old_frontend_verified=True,old_release_restored=True,candidate_frontend_preserved=not missing_dist,missing_live_dist_recovered=missing_dist,sql_connections=0,service_actions=0)
    print(json.dumps(result))
