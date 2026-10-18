"""Separate approved PROGRAM rollback only; never restores databases or starts workers."""
import argparse,json,os,shutil,socket,sys,zipfile
from pathlib import Path
import cutover as c


def verify_program_backup(path):
    c.h.check((path/'backup-manifest.json').is_file(),'Program backup manifest missing')
    manifest=json.loads((path/'backup-manifest.json').read_text(encoding='utf-8'))
    c.h.check(c.h.hashfile(path/'source.zip')==manifest['source_sha256']
              and c.h.hashfile(path/'history.bundle')==manifest['history_sha256'],'Program backup digest mismatch')
    with zipfile.ZipFile(path/'source.zip') as z:c.h.check(z.testzip() is None,'Old source archive CRC mismatch')
    actual={p.relative_to(path/'dist').as_posix():c.h.hashfile(p) for p in (path/'dist').rglob('*') if p.is_file()}
    c.h.check(actual==manifest['dist'],'Previous frontend backup changed')
    c.h.check(c.h.hashfile(path/'release.json')==manifest.get('runtime',{}).get('runtime_manifest_sha256'),
              'Previous runtime manifest bytes changed')
    release=json.loads((path/'release.json').read_text(encoding='utf-8'))
    c.h.check(release['version']=='v1.0.2' and release['commit']==c.h.BASELINE
              and release['database_revision']==c.h.PREVIOUS,'Previous release identity mismatch')
    return manifest


def pipeline(controller):
    for name in ('verify','restore','verify_restored'):getattr(controller,name)()


class ProgramRollback:
    def __init__(self,approved):
        c.h.check(approved,'Separate program rollback approval required')
        c.h.check(os.name=='nt' and c.HERE==c.ROOT/'.runtime/archive-draft-cutover-20261018','Wrong rollback host directory')
        c.h.guard_host(socket.gethostbyname_ex(socket.gethostname())[2])
        self.backup=c.HERE/'previous-program';self.manifest=verify_program_backup(self.backup)
        self.displaced=c.HERE/'rollback-displaced';c.h.check(not self.displaced.exists(),'Previous rollback evidence exists')
        cfg=json.loads((c.ROOT/'ops/windows/pms-operations.json').read_text(encoding='utf-8-sig'))
        os.environ.update(PMS_CONFIG_FILE=cfg['protectedConfig'],PMS_PURCHASE_CONFIG_FILE=cfg['purchaseConfig'],PYTHONDONTWRITEBYTECODE='1')
        sys.path.insert(0,str(c.ROOT/'backend'))
        from app.core.config import settings,validate_runtime_config
        from app.core.database import engine
        from sqlalchemy import text
        validate_runtime_config(settings)
        c.h.check(settings.PMS_ENV=='production' and settings.DB_HOST=='10.10.1.230' and settings.DB_NAME=='PMS','Wrong rollback database settings')
        self.settings,self.engine,self.text=settings,engine,text
        self.before=json.loads((c.HERE/'formal-before.json').read_text(encoding='utf-8'))

    def config_guard(self):
        c.h.check(all(c.h.hashfile(p)==sha for p,sha in self.manifest['protected'].items()),'Protected configuration differs; no config overwrite is allowed')

    def verify(self):
        self.config_guard();verify_program_backup(self.backup)
        c.ps("if(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue){throw 'PMS must stay stopped'}")
        with self.engine.connect() as con:
            actual=con.execute(self.text('SELECT DB_NAME()')).scalar_one()
            revision=con.execute(self.text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one()
            c.guard_program_rollback(dict(approved=True,actual_database=actual,sql_host=self.settings.DB_HOST,
                revision=revision,backend_stopped=True,backup_verified=True))
            c.h.check(c.h.capture(con)==self.before,'Database does not match the verified pre-cutover snapshot; no program rollback')
        c.h.check(c.h.run(['git.exe','-C',str(c.ROOT),'rev-parse','HEAD']) in (c.h.CANDIDATE,c.h.BASELINE),'Unexpected current source')
        c.guard_checkout_status(c.h.run(['git.exe','-C',str(c.ROOT),'status','--porcelain']),allow_manifest=True)
        c.h.run(['git.exe','-C',str(c.ROOT),'bundle','verify',str(self.backup/'history.bundle')])

    def restore(self):
        # Re-check actual database, protected files and stopped listener immediately before writes.
        self.verify()
        self.displaced.mkdir()
        shutil.copy2(c.ROOT/'release.json',self.displaced/'release.json')
        c.h.run(['git.exe','-C',str(c.ROOT),'-c','core.autocrlf=false','-c','core.eol=lf','switch','--detach',c.h.BASELINE])
        live_dist=c.ROOT/'frontend/dist'
        if live_dist.exists():
            live_dist.rename(self.displaced/'dist')
        else:
            c.h.save(self.displaced/'missing-live-dist.json',{'missing_before_rollback':True},new=True)
        c.backup_tree(self.backup/'dist',c.ROOT/'frontend/dist')
        shutil.copy2(self.backup/'release.json',c.ROOT/'release.json')
        self.config_guard()

    def verify_restored(self):
        self.config_guard()
        c.h.check(c.h.run(['git.exe','-C',str(c.ROOT),'rev-parse','HEAD'])==c.h.BASELINE,'Restored source commit mismatch')
        with zipfile.ZipFile(self.backup/'source.zip') as z:
            for name in z.namelist():
                if not name.endswith('/'):c.canonicalize_source(c.ROOT/name,z.read(name))
        c.h.check({p.relative_to(c.ROOT/'frontend/dist').as_posix():c.h.hashfile(p) for p in (c.ROOT/'frontend/dist').rglob('*') if p.is_file()}==self.manifest['dist'],'Restored frontend mismatch')
        c.h.check(c.h.hashfile(c.ROOT/'release.json')==c.h.hashfile(self.backup/'release.json'),'Restored release mismatch')
        c.guard_checkout_status(c.h.run(['git.exe','-C',str(c.ROOT),'status','--porcelain']),allow_manifest=True)
        c.ps("if(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue){throw 'PMS unexpectedly started'}")
        c.h.save(c.HERE/'program-rollback-result.json',dict(program_restored=True,database_restored_by_this_helper=False,
            source=c.h.BASELINE,database_revision=c.h.PREVIOUS,backend_started=False),new=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--approved-program-rollback',action='store_true');args=parser.parse_args();controller=None
    try:
        controller=ProgramRollback(args.approved_program_rollback);pipeline(controller)
        print('PROGRAM_ROLLBACK_VERIFIED_PMS_REMAINS_STOPPED',flush=True)
    except Exception as error:
        print('PROGRAM_ROLLBACK_STOPPED '+type(error).__name__+'; preserve evidence; no automatic retry',flush=True)
        raise SystemExit(1)
    finally:
        if controller:controller.engine.dispose()

if __name__=='__main__':main()
