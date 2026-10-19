import copy,unittest
import publish as m
class Evidence(unittest.TestCase):
 def test_only_matching_completed_formal_acceptance_can_publish(self):
  self.assertTrue(hasattr(m,'validate_evidence'),'Current acceptance gate missing')
  good={'phase':'normal-runtime-restored','commit':'f15d4f4527b5f837b622cf0370f6dadf87e562b2','normal_runtime_restored':True,'browser_accepted':True,'version_mail_environment_value':'false'}
  a={'commit':good['commit'],'accepted':True,'checks':dict.fromkeys(['version_and_guide','feedback_person_names','audit_person_names','archive_read'],True)}
  manifest={'commit':good['commit'],'version':'v1.2.1'}
  m.validate_evidence(good,a,manifest)
  for key,value in [('phase','controlled-stopped'),('browser_accepted',False),('normal_runtime_restored',False),('version_mail_environment_value','true')]:
   bad=copy.deepcopy(good);bad[key]=value
   with self.subTest(key=key),self.assertRaises(RuntimeError):m.validate_evidence(bad,a,manifest)
  bad=copy.deepcopy(a);bad['checks']['feedback_person_names']=False
  with self.assertRaises(RuntimeError):m.validate_evidence(good,bad,manifest)
  with self.assertRaises(RuntimeError):m.validate_evidence(good,a,{'commit':'0'*40,'version':'v1.2.1'})
if __name__=='__main__':unittest.main()
