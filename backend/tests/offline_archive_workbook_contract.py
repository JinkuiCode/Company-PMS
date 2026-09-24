import sys,unittest,io,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class WorkbookContract(unittest.TestCase):
 def test_workbook_converts_blank_zero_and_source(self):
  from app.services.offline_archive_workbook import read_archive_workbook
  b=io.BytesIO()
  with zipfile.ZipFile(b,"w") as z:
   z.writestr("xl/workbook.xml",'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="合并明细" r:id="rId1"/></sheets></workbook>')
   z.writestr("xl/_rels/workbook.xml.rels",'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
   headers=["归档追溯ID","项目编号","项目名称或内容","数量","来源工作表","来源位置"]
   row=lambda n,vs:'<row r="'+str(n)+'">'+''.join('<c t="inlineStr"><is><t>'+v+'</t></is></c>' for v in vs)+'</row>'
   z.writestr("xl/worksheets/sheet1.xml",'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+row(1,headers)+row(2,["S1-R2","AS-1-1","","0","主机A","主机A!2"])+'</sheetData></worksheet>')
  rows=read_archive_workbook(b.getvalue())
  self.assertEqual(rows[0]["values"]["quantity"],"0")
  self.assertIsNone(rows[0]["values"]["project_name"])
  self.assertEqual(rows[0]["source_row"],2)
 def test_bad_zip_rejected(self):
  from app.services.offline_archive_workbook import read_archive_workbook
  from fastapi import HTTPException
  with self.assertRaises(HTTPException):read_archive_workbook(b"invalid")
if __name__=="__main__":unittest.main()
