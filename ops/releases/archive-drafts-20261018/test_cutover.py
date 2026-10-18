import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


class CutoverSafety(unittest.TestCase):
    def module(self):
        self.assertTrue((HERE / 'cutover.py').is_file(), 'Approved cutover controller is missing')
        import cutover
        return cutover

    def test_upgrade_requires_actual_formal_target_stop_and_fresh_verified_backup(self):
        m = self.module()
        valid = dict(approved=True, actual_database='PMS', sql_host='10.10.1.230', backend_stopped=True,
                     restored_verified=True, database_revision=m.h.PREVIOUS,
                     backup=dict(copy_only=True, checksum=True, verifyonly=True, backup_sets=1, sha256='a'*64))
        m.guard_upgrade(valid)
        for key, value in [('approved', False), ('actual_database', 'OA'), ('sql_host', '10.10.1.247'),
                           ('backend_stopped', False), ('restored_verified', False), ('database_revision', m.h.CURRENT)]:
            with self.subTest(key=key), self.assertRaises(m.h.GateError):
                m.guard_upgrade(dict(valid, **{key: value}))
        with self.assertRaises(m.h.GateError): m.guard_upgrade(dict(valid, backup={}))

    def test_pipeline_never_upgrades_after_gate_or_backup_failure(self):
        m = self.module()
        for failed in ('preflight', 'backup_program', 'credentials', 'stop', 'backup_database', 'verify_restored'):
            class Fake:
                def __init__(self): self.calls=[]
                def __getattr__(self, name):
                    def call():
                        self.calls.append(name)
                        if name == failed: raise m.h.GateError('test failure')
                    return call
            f = Fake()
            with self.assertRaises(m.h.GateError): m.pipeline(f)
            self.assertNotIn('upgrade', f.calls)
            self.assertNotIn('install', f.calls)

    def test_pipeline_preserves_failure_and_never_automatically_restores(self):
        m = self.module()
        class Fake:
            def __init__(self): self.calls=[]
            def __getattr__(self, name):
                def call():
                    self.calls.append(name)
                    if name == 'upgrade': raise m.h.GateError('upgrade failed')
                return call
        f = Fake()
        with self.assertRaises(m.h.GateError): m.pipeline(f)
        self.assertNotIn('install', f.calls)
        self.assertNotIn('restore', f.calls)
        self.assertNotIn('start_old', f.calls)

    def test_success_requires_restore_proof_before_upgrade_and_verify_after_start(self):
        m=self.module()
        class Fake:
            def __init__(self):self.calls=[]
            def __getattr__(self,name):
                return lambda:self.calls.append(name)
        f=Fake();m.pipeline(f)
        self.assertEqual(f.calls,['preflight','backup_program','credentials','preflight','stop','backup_database','verify_restored','upgrade','install','start','verify'])

    def test_install_gate_cannot_skip_verified_upgrade(self):
        m = self.module()
        good = dict(backend_stopped=True, phase='formal-upgrade-verified', database_revision=m.h.CURRENT,
                    business_preserved=True, protected_configs_unchanged=True)
        m.guard_install(good)
        for key in good:
            with self.subTest(key=key), self.assertRaises(m.h.GateError):
                m.guard_install(dict(good, **{key:False}))

    def test_program_copy_is_exact_and_never_overwrites_backup(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);src=r/'src';src.mkdir();(src/'a').write_bytes(b'old')
            hashes=m.backup_tree(src,r/'copy')
            self.assertEqual(hashes, {'a':m.h.hashfile(src/'a')})
            self.assertEqual((r/'copy/a').read_bytes(),b'old')
            with self.assertRaises(m.h.GateError): m.backup_tree(src,r/'copy')
            (src/'link').symlink_to(src/'a')
            with self.assertRaises(m.h.GateError): m.backup_tree(src,r/'bad')

    def test_source_canonicalization_only_accepts_windows_newline_differences(self):
        m=self.module()
        self.assertTrue(callable(getattr(m,'canonicalize_source',None)),'Strict newline-only installation guard missing')
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'source.py';p.write_bytes(b'one\r\ntwo\r\n')
            m.canonicalize_source(p,b'one\ntwo\n')
            self.assertEqual(p.read_bytes(),b'one\ntwo\n')
            p.write_bytes(b'UNAPPROVED\r\n')
            with self.assertRaises(m.h.GateError):m.canonicalize_source(p,b'one\ntwo\n')

    def test_old_settings_without_manifest_field_are_accepted_but_external_path_is_not(self):
        from types import SimpleNamespace
        m=self.module();self.assertTrue(callable(getattr(m,'guard_manifest_path',None)),'Old-settings manifest compatibility guard missing')
        m.guard_manifest_path(SimpleNamespace(),{},Path('C:/PMS'))
        for settings,env in [(SimpleNamespace(PMS_RELEASE_MANIFEST='C:/other.json'),{}),(SimpleNamespace(),{'PMS_RELEASE_MANIFEST':'C:/other.json'})]:
            with self.assertRaises(m.h.GateError):m.guard_manifest_path(settings,env,Path('C:/PMS'))

    def test_postdeploy_status_only_allows_exact_generated_untracked_manifest(self):
        m=self.module();self.assertTrue(callable(getattr(m,'guard_checkout_status',None)),'Generated manifest status guard missing')
        m.guard_checkout_status('',allow_manifest=False)
        m.guard_checkout_status('?? release.json',allow_manifest=True)
        for status,allow in [('?? release.json',False),('?? secret.txt',True),(' M backend/main.py',True),('?? release.json\n?? other.txt',True),(' M release.json',True)]:
            with self.subTest(status=status),self.assertRaises(m.h.GateError):m.guard_checkout_status(status,allow_manifest=allow)

    def test_process_guard_cannot_stop_unrelated_or_reused_pid(self):
        m=self.module()
        p=dict(pid=123,created='now',executable='C:/PMS/backend/.venv/Scripts/python.exe',
               command='python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000')
        m.guard_process(p,p, p['executable'])
        for key,value in [('pid',999),('created','later'),('executable','C:/OA/python.exe'),('command','python.exe other.py')]:
            with self.subTest(key=key),self.assertRaises(m.h.GateError): m.guard_process(p,dict(p,**{key:value}),p['executable'])

    def test_new_listener_must_be_exact_controlled_process_with_same_owner(self):
        m=self.module();self.assertTrue(callable(getattr(m,'guard_controlled_process',None)),'New listener ownership guard missing')
        launcher='C:/PMS/.runtime/cutover/controlled.py';exe='C:/PMS/python.exe'
        process=dict(pid=50,executable=exe,command='python.exe '+launcher+' main:app',owner_sid='S-1-old')
        proof=dict(pid=50,maintenance_writes_blocked=True)
        m.guard_controlled_process(50,process,proof,exe,launcher,'S-1-old')
        for key,value in [('pid',51),('executable','C:/OA/python.exe'),('command','python.exe main:app'),('owner_sid','S-1-other')]:
            with self.subTest(key=key),self.assertRaises(m.h.GateError):m.guard_controlled_process(50,dict(process,**{key:value}),proof,exe,launcher,'S-1-old')
        for key,value in [('pid',51),('maintenance_writes_blocked',False)]:
            with self.subTest(key=key),self.assertRaises(m.h.GateError):m.guard_controlled_process(50,process,dict(proof,**{key:value}),exe,launcher,'S-1-old')

    def test_public_receipt_excludes_credentials_and_raw_snapshots(self):
        m=self.module()
        s=dict(phase='stopped',password='secret',username='secret',protected_hashes={'secret':'secret'},
               business_before={'raw':'secret'},error='secret',backup={'password':'secret','verifyonly':True})
        out=m.safe_receipt(s)
        self.assertNotIn('secret',str(out));self.assertEqual(out['backup'],{'verifyonly':True})

    def test_acceptance_policy_blocks_data_changes_but_allows_signin(self):
        m=self.module()
        for method,path in [('POST','/api/projects'),('DELETE','/api/users/1'),('PATCH','/api/projects/1')]:
            self.assertFalse(m.allowed_request(method,path))
        for method,path in [('GET','/api/projects'),('POST','/api/auth/login'),('POST','/api/auth/logout')]:
            self.assertTrue(m.allowed_request(method,path))
        self.assertFalse(m.allowed_request('POST','/api/sso/callback'))
        self.assertFalse(m.allowed_request('GET','/api/sso/url/verify'))
        self.assertFalse(m.allowed_request('GET','/api/sso/callback'))

    def test_worker_pause_is_exhaustive_and_unrelated_thread_is_not_started(self):
        m=self.module()
        self.assertEqual(m.PAUSED_WORKERS,{'pms-erp-worker','pms-report-export-worker','pms-feedback-mail-worker','pms-release-mail-worker'})
        import threading
        from unittest.mock import patch
        started=[]
        with patch.object(threading.Thread,'start',lambda s:started.append(s.name)):
            restore=m.pause_workers()
            try:
                threads=[threading.Thread(target=lambda:None,name=n) for n in sorted(m.PAUSED_WORKERS)]
                for t in threads:t.start();t.join()
                threading.Thread(target=lambda:None,name='unrelated').start()
                self.assertEqual(started,['unrelated'])
            finally:restore()

    def test_actual_acceptance_middleware_rejects_writes_without_calling_business_api(self):
        import ast,asyncio
        from types import SimpleNamespace
        m=self.module();tree=ast.parse((HERE/'controlled.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='maintenance_writes')
        fn.decorator_list=[]
        namespace={'allowed_request':m.allowed_request,'JSONResponse':lambda body,status_code:SimpleNamespace(status_code=status_code,body=body)}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'actual-middleware','exec'),namespace)
        seen=[]
        async def next_call(request):seen.append(request.url.path);return SimpleNamespace(status_code=200)
        for method,path,expected in [('PATCH','/api/projects/1',503),('GET','/api/sso/callback',503),('GET','/api/users/oa-options',503),('GET','/api/reports/purchase',503),('GET','/api/product-lines/options',503),('GET','/api/product-lines/organizations',503),('GET','/api/auth/me',200),('POST','/api/auth/login',200)]:
            request=SimpleNamespace(method=method,url=SimpleNamespace(path=path))
            result=asyncio.run(namespace['maintenance_writes'](request,next_call))
            self.assertEqual(result.status_code,expected)
        self.assertEqual(seen,['/api/auth/me','/api/auth/login'])


    def test_release_package_and_source_identity_are_pinned(self):
        m=self.module()
        _,files=m.h.read_package(m.ARTIFACTS/'candidate.zip')
        import json
        release=json.loads(files['release.json'])
        self.assertEqual(release['version'],'v1.1.0')
        self.assertEqual(release['commit'],m.h.CANDIDATE)
        self.assertEqual(release['database_revision'],m.h.CURRENT)
        self.assertIn('backend/app/services/form_draft_management_migration.py',files)
        self.assertFalse(any('.env' in n or '/prototypes/' in n for n in files))

    def test_readonly_acceptance_blocks_erp_and_draft_writes(self):
        m=self.module()
        for method,path in [('GET','/api/erp/query'),('GET','/api/reports/purchase'),('GET','/api/reports/inventory/options'),('GET','/api/users/oa-options'),('GET','/api/product-lines/options'),('GET','/api/product-lines/organizations'),('POST','/api/form-drafts'),('DELETE','/api/archive-draft-management/x')]:
            self.assertFalse(m.allowed_request(method,path))

    def test_no_receipt_upload_destination_is_accepted(self):
        m=self.module()
        m.guard_receipt_destination(None)
        with self.assertRaises(m.h.GateError):m.guard_receipt_destination('http://anything/receipt')

    def test_rollback_requires_separate_approval_matching_database_and_stopped_backend(self):
        m=self.module()
        good=dict(approved=True,actual_database='PMS',sql_host='10.10.1.230',revision=m.h.PREVIOUS,backend_stopped=True,backup_verified=True)
        m.guard_program_rollback(good)
        for key,value in [('approved',False),('actual_database','OA'),('sql_host','other'),('revision',m.h.CURRENT),('backend_stopped',False),('backup_verified',False)]:
            with self.subTest(key=key),self.assertRaises(m.h.GateError):m.guard_program_rollback(dict(good,**{key:value}))


    def test_ready_or_processing_mail_blocks_cutover_before_service_stop(self):
        from types import SimpleNamespace
        m=self.module()
        for active in ('pms_feedback_notification','pms_release_mail'):
            for status in ('pending','waiting','processing'):
                class Connection:
                    def __enter__(self):return self
                    def __exit__(self,*args):pass
                    def execute(self,statement):
                        return SimpleNamespace(scalar_one=lambda:1 if active in str(statement) and "'"+status+"'" in str(statement) else 0)
                instance=m.Cutover.__new__(m.Cutover)
                instance.engine=SimpleNamespace(connect=Connection);instance.text=lambda s:s
                with self.subTest(table=active,status=status),self.assertRaises(m.h.GateError):instance.pending()

if __name__=='__main__': unittest.main()
