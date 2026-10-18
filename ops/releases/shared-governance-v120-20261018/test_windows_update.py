import sys,unittest
from pathlib import Path,PureWindowsPath
sys.path.insert(0,str(Path(__file__).parent))
import windows_update as w
class WindowsGuards(unittest.TestCase):
    def test_wrong_machine_or_private_location_refused(self):
        root=PureWindowsPath('C:/PMS');work=root/'.runtime/shared-governance-v120-20261018';pins={'host':'10.10.1.228'}
        w.guard_host('nt',root,work,['10.10.1.228'],pins)
        for os_name,r,p,ips in [('posix',root,work,['10.10.1.228']),('nt',root,work,['10.10.91.251']),('nt',PureWindowsPath('D:/PMS'),work,['10.10.1.228']),('nt',root,root/'ops',['10.10.1.228'])]:
            with self.subTest(os=os_name,root=r,ips=ips),self.assertRaises(RuntimeError):w.guard_host(os_name,r,p,ips,pins)
    def test_private_acl_requires_only_maintainer_system_and_administrators(self):
        sid='S-1-5-21-123-456';allowed=[sid,'S-1-5-18','S-1-5-32-544']
        good=dict(protected=True,reparse=False,owner=sid,entries=[dict(sid=s,allow=True,full=True) for s in allowed]);good['objects']=[dict(owner=sid,reparse=False,entries=good['entries'])]
        w.guard_acl(good,sid)
        bad=[dict(good,protected=False),dict(good,reparse=True),dict(good,owner='S-1-1-0'),dict(good,entries=[]),dict(good,entries=good['entries']+[dict(sid='S-1-1-0',allow=True,full=False)])]
        for item in bad:
            with self.subTest(acl=item),self.assertRaises(RuntimeError):w.guard_acl(item,sid)
    def test_private_child_null_dacl_is_rejected(self):
        sid='S-1-5-21-123';entries=[dict(sid=s,allow=True,full=True) for s in [sid,'S-1-5-18','S-1-5-32-544']]
        metadata=dict(protected=True,reparse=False,owner=sid,entries=entries,objects=[dict(owner=sid,reparse=False,entries=[])])
        with self.assertRaises(RuntimeError):w.guard_acl(metadata,sid)
    def test_process_rejects_source_overrides_and_pid_identity_changes(self):
        python='C:/PMS/backend/.venv/Scripts/python.exe'
        p=dict(pid=123,created='2026-10-18T00:00:00Z',owner_sid='S-1-5-21-123',executable=python,command=python+' -m uvicorn main:app --host 127.0.0.1 --port 8000')
        w.verify_process(p,p,python)
        for suffix in [' --app-dir D:/OtherPMS/backend',' --reload',' --factory']:
            bad=dict(p,command=p['command']+suffix)
            with self.subTest(suffix=suffix),self.assertRaises(RuntimeError):w.verify_process(bad,p,python)
        for key,value in [('pid',124),('created','different'),('owner_sid','other'),('executable','D:/Other/python.exe')]:
            with self.subTest(key=key),self.assertRaises(RuntimeError):w.verify_process(dict(p,**{key:value}),p,python)
    def test_existing_process_requires_the_pinned_trusted_startup_receipt(self):
        import json,tempfile
        from unittest.mock import patch
        python='C:/Python313/python.exe'
        proc=dict(pid=123,created='start-time',owner_sid='maintainer',executable=python,command=python+' -m uvicorn main:app --host 127.0.0.1 --port 8000')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/'.runtime/archive-draft-resume-20261018';old.mkdir(parents=True);(root/'ops/windows').mkdir(parents=True);(root/'pids').mkdir()
            receipt=old/'normal-process.json';receipt.write_text(json.dumps(proc));(old/'resume_runtime.py').write_bytes(b'previous verified launcher');(root/'ops/windows/Start-Pms.ps1').write_bytes(b'known start script');(root/'release.json').write_bytes(b'previous runtime');(root/'pids/backend.pid').write_text('123')
            instance=w.WindowsUpdate.__new__(w.WindowsUpdate);instance.cfg={'pythonExe':python,'dataRoot':str(root)}
            instance.pins=dict(start_receipt_sha256=w.u.hashfile(receipt),start_launcher_sha256=w.u.hashfile(old/'resume_runtime.py'),baseline_start_script_sha256=w.u.hashfile(root/'ops/windows/Start-Pms.ps1'),baseline_manifest_sha256=w.u.hashfile(root/'release.json'))
            with patch.object(w,'ROOT',root):
                instance.verify_normal_origin(proc)
                with self.assertRaises(RuntimeError):instance.verify_normal_origin(dict(proc,created='reused-pid'))
                (root/'pids/backend.pid').write_text('124')
                with self.assertRaises(RuntimeError):instance.verify_normal_origin(proc)
                (root/'pids/backend.pid').write_text('123');receipt.write_text('{}')
                with self.assertRaises(RuntimeError):instance.verify_normal_origin(proc)
    def test_stopped_rollback_does_not_depend_on_a_partially_written_live_manifest(self):
        import tempfile,types
        from unittest.mock import patch
        class Cell:
            def __init__(self,value):self.value=value
            def scalar_one(self):return self.value
        class Connection:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def execute(self,sql):return Cell('PMS' if 'DB_NAME' in sql else 'schema02' if 'SELECT revision' in sql else 0)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'release.json').write_text('{partially-written')
            c=w.WindowsUpdate.__new__(w.WindowsUpdate);c.owner='maintainer';c.reference='approved-window';c.cfg={'autoRestart':False};c.pins={'host':'10.10.1.228','schema':'schema02'};c.settings=types.SimpleNamespace(DB_HOST='10.10.1.230');c.engine=types.SimpleNamespace(connect=Connection);c.text=lambda value:value;c.files=types.SimpleNamespace(config_guard=lambda:None)
            with patch.object(w,'ROOT',root),patch.object(w,'process',return_value=None),patch.object(w,'require_private_acl'),patch.object(w.u,'git',return_value='old-head'),patch.object(w.u,'clean',return_value=True):
                state=c.read_state(for_rollback=True);self.assertEqual(state['schema'],'schema02');self.assertTrue(state['backend_stopped']);self.assertIsNone(state['version'])
                with self.assertRaises(ValueError):c.read_state()
    def test_failure_stops_without_recovery_or_next_phase(self):
        phases=['preflight','stage','backup','preflight','stop','install','start','verify']
        for fail in range(len(phases)):
            calls=[]
            class Fake:
                def __getattr__(self,name):
                    def call():
                        calls.append(name)
                        if len(calls)-1==fail:raise RuntimeError('injected')
                    return call
            with self.subTest(fail=fail),self.assertRaises(RuntimeError):w.pipeline(Fake())
            self.assertEqual(calls,phases[:fail+1]);self.assertNotIn('rollback',calls)
if __name__=='__main__':unittest.main()
