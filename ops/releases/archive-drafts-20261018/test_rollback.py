import sys,tempfile,unittest,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))

class RollbackSafety(unittest.TestCase):
 def module(self):
  self.assertTrue((HERE/'rollback.py').is_file(),'Separate rollback helper is missing')
  import rollback
  return rollback
 def test_corrupted_or_missing_program_backup_refused(self):
  m=self.module()
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder);(p/'dist').mkdir();(p/'dist/index.html').write_text('old')
   with self.assertRaises(m.c.h.GateError):m.verify_program_backup(p)
 def test_backup_release_bytes_must_match_saved_runtime_digest(self):
  m=self.module()
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder);(p/'dist').mkdir();(p/'dist/index.html').write_text('old')
   import zipfile
   with zipfile.ZipFile(p/'source.zip','w') as z:z.writestr('a','old')
   (p/'history.bundle').write_bytes(b'fixture')
   release=dict(version='v1.0.2',commit=m.c.h.BASELINE,database_revision=m.c.h.PREVIOUS,title='old')
   (p/'release.json').write_text(json.dumps(release))
   meta=dict(source_sha256=m.c.h.hashfile(p/'source.zip'),history_sha256=m.c.h.hashfile(p/'history.bundle'),dist={'index.html':m.c.h.hashfile(p/'dist/index.html')},runtime={'runtime_manifest_sha256':m.c.h.hashfile(p/'release.json')})
   (p/'backup-manifest.json').write_text(json.dumps(meta))
   m.verify_program_backup(p)
   release['title']='changed';(p/'release.json').write_text(json.dumps(release))
   with self.assertRaises(m.c.h.GateError):m.verify_program_backup(p)
 def test_rollback_pipeline_stops_on_any_precondition_failure(self):
  m=self.module()
  for failed in ('verify','restore'):
   class Fake:
    def __init__(self):self.calls=[]
    def __getattr__(self,n):
     def call():
      self.calls.append(n)
      if n==failed:raise m.c.h.GateError('failure')
     return call
   fake=Fake()
   with self.assertRaises(m.c.h.GateError):m.pipeline(fake)
   self.assertNotIn('start',fake.calls);self.assertNotIn('database_restore',fake.calls)
 def test_only_program_restore_and_verify_are_in_pipeline(self):
  m=self.module()
  class Fake:
   def __init__(self):self.calls=[]
   def __getattr__(self,n):return lambda:self.calls.append(n)
  fake=Fake();m.pipeline(fake)
  self.assertEqual(fake.calls,['verify','restore','verify_restored'])

if __name__=='__main__':unittest.main()
