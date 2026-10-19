"""GBK default must not corrupt UTF-8 Chinese release and maintenance records."""
import json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import windows_update as w
from test_files import FileTests
real_read=Path.read_text
real_write=Path.write_text
def gbk_read(self,encoding=None,errors=None,**kw):return real_read(self,encoding=encoding or 'gbk',errors=errors,**kw)
def gbk_write(self,data,encoding=None,errors=None,**kw):return real_write(self,data,encoding=encoding or 'gbk',errors=errors,**kw)
class ChineseReleaseFiles(FileTests):
 def test_actual_backup_install_rollback_with_chinese_manifest_and_gbk_default(self):
  old=json.loads(self.old_release);old['title']='提报操作记录人员名称显示修复';old['summary']='管理员审计中文名称'
  self.old_release=(json.dumps(old,ensure_ascii=False)+'\n').encode('utf-8');(self.root/'release.json').write_bytes(self.old_release)
  with patch.object(Path,'read_text',gbk_read),patch.object(Path,'write_text',gbk_write):
   self.prepare();self.files.install(self.stopped);self.files.rollback(self.stopped())
  self.assertEqual((self.root/'release.json').read_bytes(),self.old_release);self.assert_preserved()
class ChineseState(unittest.TestCase):
 def test_read_and_record_use_utf8_in_gbk_environment(self):
  class Cell:
   def __init__(self,v):self.v=v
   def scalar_one(self):return self.v
  class Connection:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def execute(self,sql):return Cell('PMS' if 'DB_NAME' in sql else 'schema02' if 'SELECT revision' in sql else 0)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);work=root/'work';work.mkdir()
   (root/'release.json').write_bytes(json.dumps({'version':'v1.2.1','database_revision':'schema02','title':'中文版本说明'},ensure_ascii=False).encode())
   c=w.WindowsUpdate.__new__(w.WindowsUpdate);c.owner='maintainer';c.reference='approved-window';c.cfg={'autoRestart':False};c.pins={'host':'10.10.1.228','schema':'schema02','commit':'fixed'};c.settings=types.SimpleNamespace(DB_HOST='10.10.1.230');c.engine=types.SimpleNamespace(connect=Connection);c.text=lambda v:v;c.files=types.SimpleNamespace(config_guard=lambda:None);c.state={};c.state_path=work/'deployment-state.json'
   with patch.object(w,'ROOT',root),patch.object(w,'HERE',work),patch.object(w,'process',return_value=None),patch.object(w,'require_private_acl'),patch.object(w.u,'git',return_value='old-head'),patch.object(w.u,'clean',return_value=True),patch.object(Path,'read_text',gbk_read),patch.object(Path,'write_text',gbk_write):
    self.assertEqual(c.read_state()['version'],'v1.2.1');c.record('fixture',verified_by='验收人员')
   self.assertEqual(json.loads(c.state_path.read_bytes())['verified_by'],'验收人员')
if __name__=='__main__':
 suite=unittest.TestSuite([ChineseReleaseFiles('test_actual_backup_install_rollback_with_chinese_manifest_and_gbk_default'),ChineseState('test_read_and_record_use_utf8_in_gbk_environment')])
 raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
