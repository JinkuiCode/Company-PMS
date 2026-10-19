"""Actual fixed ZIP/bundle in disposable clones; zero service or SQL operations."""
import json,shutil,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import program_update as u
ROOT=Path(__file__).resolve().parents[3]
PINS=json.loads((Path(__file__).parent/'pins.json').read_text())
ARTIFACT=ROOT/'release/archive-purchase-v1.3.0-20261019'

class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pms-program-only-');self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name)/'work';self.work.mkdir();self.root=Path(self.temp.name)/'PMS'
        u.run(['git','clone','--shared','--no-checkout',str(ROOT),str(self.root)])
        u.git(self.root,'-c','core.autocrlf=false','checkout','--detach',PINS['baseline_head'])
        (self.root/'frontend/dist').mkdir();(self.root/'frontend/dist/index.html').write_bytes(b'OLD FRONTEND')
        old=dict(version=PINS['baseline_version'],commit=PINS['baseline_runtime_commit'],database_revision=PINS['schema'])
        (self.root/'release.json').write_text(json.dumps(old));self.old_release=(self.root/'release.json').read_bytes()
        self.config=self.root/'backend/.env.local';self.config.write_bytes(b'isolated-private-fixture')
        self.database=self.work/'untouched-database.bin';self.database.write_bytes(b'ISOLATED-DB-NOT-OPENED')
        shutil.copy2(ARTIFACT/(PINS['build_id']+'.zip'),self.work/'candidate.zip')
        shutil.copy2(ARTIFACT/'source.bundle',self.work/'source.bundle')
        self.files=u.ProgramFiles(self.root,self.work,PINS,[self.config]);self.state=dict(host=PINS['host'],sql_host=PINS['sql_host'],database=PINS['database'],schema=PINS['schema'],head=PINS['baseline_head'],version=PINS['baseline_version'],runtime_commit=PINS['baseline_runtime_commit'],clean=True,protected_unchanged=True,backend_stopped=False,pending=0,auto_restart=False,approved=True,process_verified=True)
    def stopped(self):return dict(self.state,backend_stopped=True)
    def prepare(self):self.files.backup(self.state);self.files.stage()
    def assert_preserved(self):
        self.assertEqual(self.config.read_bytes(),b'isolated-private-fixture');self.assertEqual(self.database.read_bytes(),b'ISOLATED-DB-NOT-OPENED')
    def test_actual_candidate_install_and_program_only_rollback(self):
        self.prepare();self.files.install(self.stopped)
        self.assertEqual(u.git(self.root,'rev-parse','HEAD'),PINS['commit']);self.files.verify_installed()
        self.assertEqual((self.work/'displaced-dist/index.html').read_bytes(),b'OLD FRONTEND')
        self.files.rollback(self.stopped());self.assertEqual(u.git(self.root,'rev-parse','HEAD'),PINS['baseline_head'])
        self.assertEqual((self.root/'frontend/dist/index.html').read_bytes(),b'OLD FRONTEND');self.assertEqual((self.root/'release.json').read_bytes(),self.old_release)
        self.assertFalse(json.loads((self.work/'rolled-back.json').read_text())['backend_started']);self.assert_preserved()
    def test_missing_frontend_after_failed_install_can_be_restored(self):
        self.prepare();self.files.install(self.stopped);shutil.rmtree(self.root/'frontend/dist')
        self.files.rollback(self.stopped());self.assertEqual((self.root/'frontend/dist/index.html').read_bytes(),b'OLD FRONTEND');self.assert_preserved()
    def test_config_change_stops_before_git_switch(self):
        self.prepare();self.config.write_bytes(b'changed-by-other-process')
        with self.assertRaisesRegex(RuntimeError,'Protected'):self.files.install(self.stopped)
        self.assertEqual(u.git(self.root,'rev-parse','HEAD'),PINS['baseline_head']);self.assertFalse((self.work/'install-started.json').exists())
    def test_copy_failure_preserves_partial_state_without_automatic_rollback(self):
        self.prepare()
        with patch.object(u,'copy_tree',side_effect=RuntimeError('simulated disk failure')):
            with self.assertRaisesRegex(RuntimeError,'disk failure'):self.files.install(self.stopped)
        self.assertEqual(u.git(self.root,'rev-parse','HEAD'),PINS['commit']);self.assertFalse((self.work/'installed.json').exists());self.assertFalse((self.work/'rolled-back.json').exists())
        self.assertTrue((self.work/'displaced-dist').is_dir());self.files.rollback(self.stopped());self.assert_preserved()
    def test_staged_bytes_and_backup_tampering_refused(self):
        self.prepare();(self.work/'candidate-dist/index.html').write_bytes(b'tampered')
        with self.assertRaisesRegex(RuntimeError,'Staged frontend'):self.files.install(self.stopped)
        self.assertEqual(u.git(self.root,'rev-parse','HEAD'),PINS['baseline_head'])
        (self.work/'previous-program/release.json').write_bytes(b'tampered')
        with self.assertRaisesRegex(RuntimeError,'Backup changed'):self.files.rollback(self.stopped())
        self.assert_preserved()

class PackageTests(unittest.TestCase):
    def test_rejects_unsafe_and_private_zip_entries_even_with_updated_outer_digest(self):
        for name,symlink in [('backend/../escape.py',False),('backend/.env.local',False),('backend/app/link',True),('frontend/dist/INDEX.HTML',False)]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                path=Path(d)/'attack.zip';shutil.copy2(ARTIFACT/(PINS['build_id']+'.zip'),path)
                with zipfile.ZipFile(path,'a') as z:
                    i=zipfile.ZipInfo(PINS['build_id']+'/'+name)
                    if symlink:i.create_system=3;i.external_attr=0o120777<<16
                    z.writestr(i,b'attack')
                pins=dict(PINS,archive_sha256=u.hashfile(path))
                with self.assertRaises(RuntimeError):u.read_package(path,pins)
if __name__=='__main__':unittest.main()
