import copy,unittest
import importlib
m=None
class Evidence(unittest.TestCase):
 def setUp(self):
  global m
  from pathlib import Path
  self.assertTrue((Path(__file__).parent/'publish.py').exists(),'Current publication evidence helper missing')
  m=importlib.import_module('publish')
 def test_only_matching_completed_formal_acceptance_can_publish(self):
  self.assertTrue(hasattr(m,'validate_evidence'),'Current acceptance gate missing')
  good={'phase':'normal-runtime-restored','commit':'5c5baea86c6abbc3d0dddc9f3d7bfaea53f11997','normal_runtime_restored':True,'browser_accepted':True,'version_mail_environment_value':'false'}
  a={'commit':good['commit'],'accepted':True,'checks':dict.fromkeys(['version_and_guides','archive_draft_required','archive_defaults_unit','archive_linkage','archive_historical_display','purchase_eligibility','purchase_query_conditions'],True)}
  manifest={'commit':good['commit'],'version':'v1.3.0'}
  m.validate_evidence(good,a,manifest)
  for key,value in [('phase','controlled-stopped'),('browser_accepted',False),('normal_runtime_restored',False),('version_mail_environment_value','true')]:
   bad=copy.deepcopy(good);bad[key]=value
   with self.subTest(key=key),self.assertRaises(RuntimeError):m.validate_evidence(bad,a,manifest)
  bad=copy.deepcopy(a);bad['checks']['archive_linkage']=False
  with self.assertRaises(RuntimeError):m.validate_evidence(good,bad,manifest)
  with self.assertRaises(RuntimeError):m.validate_evidence(good,a,{'commit':'0'*40,'version':'v1.3.0'})


import unittest,tempfile,subprocess
from pathlib import Path
import importlib
m=None
class GitSyncSafety(unittest.TestCase):
 def setUp(self):
  global m
  self.assertTrue((Path(__file__).parent/'publish.py').exists(),'Current alignment helper is not implemented')
  m=importlib.import_module('publish')
 def test_only_metadata_paths_outside_runtime_are_accepted(self):
  allowed={'change.md','docs/a.md','ops/releases/archive-purchase-v130-20261019-production-r1/x.py'}
  m.guard_paths(list(allowed),{'backend/main.py'},allowed)
  for names in (['backend/main.py'],['frontend/src/a.vue'],['ops/windows/Start-Pms.ps1'],['../docs/a.md'],['docs/a.md'],['docs/unapproved.md']):
   fixed={'docs/a.md'} if names==['docs/a.md'] else set()
   with self.subTest(names=names),self.assertRaises(RuntimeError):m.guard_paths(names,fixed,allowed)
 def test_real_detached_checkout_fast_forward_preserves_runtime_and_manifest(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);src=d/'source';live=d/'live';src.mkdir()
   def g(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True,stderr=subprocess.DEVNULL).strip()
   g(src,'init');(src/'backend').mkdir();(src/'backend/main.py').write_text('unchanged runtime\n');(src/'docs').mkdir();(src/'docs/n.md').write_text('old\n')
   g(src,'add','.');g(src,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','baseline');base=g(src,'rev-parse','HEAD');g(src,'branch','-M','master')
   g(src,'clone','--shared',str(src),str(live));g(live,'switch','--detach',base);(live/'release.json').write_text('keep runtime manifest\n')
   (src/'docs/n.md').write_text('new acceptance\n');g(src,'add','.');g(src,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','docs');target=g(src,'rev-parse','HEAD')
   bundle=d/'sync.bundle';g(src,'bundle','create',str(bundle),'refs/heads/master','^'+base)
   m.synchronize_checkout(live,bundle,base,target,{'backend/main.py','release.json'},{'docs/n.md'})
   self.assertEqual(g(live,'rev-parse','HEAD'),target);self.assertEqual(g(live,'branch','--show-current'),'master')
   self.assertEqual((live/'backend/main.py').read_text(),'unchanged runtime\n');self.assertEqual((live/'release.json').read_text(),'keep runtime manifest\n');self.assertEqual((live/'docs/n.md').read_text(),'new acceptance\n')


if __name__=='__main__':unittest.main()
