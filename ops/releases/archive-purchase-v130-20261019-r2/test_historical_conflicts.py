"""Historical duplicates are reported without cleanup or bypassing uniqueness."""
import json,sys,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).parent),str(Path(__file__).resolve().parents[3]/'backend')]
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session
from isolated_probe import existing_conflict_count
class HistoricalConflicts(unittest.TestCase):
 def test_existing_conflict_report_preserves_rows_and_does_not_block_other_checks(self):
  engine=create_engine('sqlite://')
  try:
   with engine.begin() as c:
    c.exec_driver_sql('CREATE TABLE pms_project_archive(id INTEGER PRIMARY KEY,project_code_key TEXT)')
    c.exec_driver_sql('CREATE TABLE pms_form_draft(id TEXT PRIMARY KEY,resource TEXT,status TEXT,payload_json TEXT)')
    c.exec_driver_sql("INSERT INTO pms_project_archive VALUES (1,'l_b-202608')")
    for identity,code in [('old','L_B-202608'),('other','UNUSED')]:c.exec_driver_sql('INSERT INTO pms_form_draft VALUES (?,?,?,?)',(identity,'archive-create','active',json.dumps({'project_code':code})))
   with Session(engine) as db:
    before=list(db.execute(text('SELECT * FROM pms_form_draft ORDER BY id')));db.rollback()
    self.assertEqual(existing_conflict_count(db,[('old','l_b-202608'),('other','unused')]),1)
    self.assertEqual(list(db.execute(text('SELECT * FROM pms_form_draft ORDER BY id'))),before)
    self.assertEqual(db.execute(text('SELECT COUNT(*) FROM pms_project_archive')).scalar_one(),1)
  finally:engine.dispose()
if __name__=='__main__':unittest.main()
