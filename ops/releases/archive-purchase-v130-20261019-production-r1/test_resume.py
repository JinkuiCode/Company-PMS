import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import resume as r
class ResumeTests(unittest.TestCase):
    def test_no_resume_for_incomplete_or_different_actual_acceptance(self):
        pins={'commit':'candidate','archive_sha256':'digest'}
        ok={'commit':'candidate','archive_sha256':'digest','controlled_pid':123,'accepted':True,'verified_at':'time','verified_by':'operator','checks':{k:True for k in r.CHECKS}}
        r.guard_acceptance(ok,pins,123)
        for key,value in [('commit','other'),('archive_sha256','other'),('controlled_pid',124),('accepted',False),('checks',{}),('checks',{k:False for k in r.CHECKS}),('verified_by','')]:
            with self.subTest(key=key),self.assertRaises(RuntimeError):r.guard_acceptance(dict(ok,**{key:value}),pins,123)
    def test_resume_restores_original_erp_setting_and_keeps_version_mail_off(self):
        source={'PYTHONPATH':'maintenance','ERP_SYNC_WORKER_ENABLED':'false','PMS_RELEASE_MAIL_WORKER_ENABLED':'true','PMS_CONFIG_FILE':'private-config','PMS_PURCHASE_CONFIG_FILE':'private-report'}
        actual=r.normal_environment(source);self.assertNotIn('PYTHONPATH',actual);self.assertNotIn('ERP_SYNC_WORKER_ENABLED',actual);self.assertEqual(actual['PMS_RELEASE_MAIL_WORKER_ENABLED'],'false');self.assertEqual(actual['PMS_CONFIG_FILE'],source['PMS_CONFIG_FILE']);self.assertEqual(source['ERP_SYNC_WORKER_ENABLED'],'false')
if __name__=='__main__':unittest.main()
