import copy, importlib.util, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import program_update as u

PINS=dict(host="10.10.1.228",sql_host="10.10.1.230",database="PMS",schema="2026-10-16-form-draft-02",baseline_head="a"*40,baseline_runtime_commit="b"*40,baseline_version="v1.1.0",commit="c"*40,version="v1.2.1")
def context():
    return dict(host=PINS["host"],sql_host=PINS["sql_host"],database="PMS",schema=PINS["schema"],head=PINS["baseline_head"],version="v1.1.0",runtime_commit=PINS["baseline_runtime_commit"],clean=True,protected_unchanged=True,backend_stopped=True,pending=0,auto_restart=False,approved=True,process_verified=True)

class GuardTests(unittest.TestCase):
    def test_install_rejects_each_unapproved_or_drifted_context(self):
        u.guard_context(context(),PINS,stopped=True)
        for key,value in dict(host="10.10.91.251",sql_host="10.10.1.149",database="master",schema="governance-01",head="d"*40,version="v9.0.0",runtime_commit="d"*40,clean=False,protected_unchanged=False,backend_stopped=False,pending=1,auto_restart=True,approved=False,process_verified=False).items():
            with self.subTest(key=key),self.assertRaises(RuntimeError):
                s=context();s[key]=value;u.guard_context(s,PINS,stopped=True)
    def test_maintenance_allows_only_local_read_acceptance_and_login(self):
        for method,path in [("GET","/api/projects"),("POST","/api/auth/login"),("POST","/api/auth/logout")]:self.assertTrue(u.allowed_request(method,path))
        for method,path in [("POST","/api/projects"),("PUT","/api/form-drafts/1"),("POST","/api/releases/publish"),("GET","/api/erp/config"),("GET","/api/reports/inventory"),("GET","/api/sso/oa-login"),("GET","/api/users/oa-options"),("GET","/api/product-lines/organizations")]:
            with self.subTest(path=path):self.assertFalse(u.allowed_request(method,path))
if __name__=="__main__":unittest.main()
