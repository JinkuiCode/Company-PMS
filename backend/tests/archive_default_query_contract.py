"""Archive categories OR and code ordering run before paging and retain scope."""
import os,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['DB_DIALECT']='sqlite';os.environ['SQLITE_DB_PATH']=str(Path(tempfile.mkdtemp())/'query.db')
from app.core.database import Base,engine,SessionLocal
from app.models import project,rbac
from app.services.project import get_archive_list
from fastapi import HTTPException
from sqlalchemy.dialects import mssql
from app.services.list_query import apply_archive_list_query,archive_columns
Base.metadata.create_all(engine)
with SessionLocal() as db:
 for i in range(42):
  db.add(project.PmsProjectArchive(project_code=f'A-{42-i:04}',project_name='test',archive_category=(i%3)+1 if i<40 else None,customer='match' if i%2==0 else 'other',is_enabled=1))
 db.commit()
 codes=[v.project_code for v in get_archive_list(db,page_size=10)['items']]
 assert codes==[f'A-{v:04}' for v in range(42,32,-1)],'Default sorting must use project code, not insertion ID'
 selected=get_archive_list(db,page_size=10,filters=json.dumps([{'field':'archive_category','operator':'in','value':[1,2]}]))
 expected=sorted([a.project_code for a in db.query(project.PmsProjectArchive) if a.archive_category in (1,2)],reverse=True)
 assert selected['total']==len(expected) and [a.project_code for a in selected['items']]==expected[:10]
 second=get_archive_list(db,page=2,page_size=10,filters=json.dumps([{'field':'archive_category','operator':'in','value':[1,2]}]))
 assert [a.project_code for a in second['items']]==expected[10:20]
 assert get_archive_list(db,page_size=50)['total']==42,'Cleared category query includes null and all categories'
 combo=[{'field':'archive_category','operator':'in','value':[1,2]},{'field':'customer','operator':'equals','value':'match'}]
 assert get_archive_list(db,filters=json.dumps(combo))['total']==len([a for a in db.query(project.PmsProjectArchive) if a.archive_category in (1,2) and a.customer=='match'])
 assert get_archive_list(db,filters=json.dumps(combo),scope_context={'permissions':[],'user_id':999,'product_category_ids':[]})['total']==0
 ascending=get_archive_list(db,page_size=10,sort='[{"colId":"project_code","sort":"asc"}]')
 assert [a.project_code for a in ascending['items']]==[f'A-{i:04}' for i in range(1,11)]
 for value in ([],[True],[0],[-1],['1'],[1.2],list(range(1,102)),1):
  try:
   get_archive_list(db,filters=json.dumps([{'field':'archive_category','operator':'in','value':value}]))
   raise AssertionError('Invalid category input was accepted')
  except HTTPException as e:assert e.status_code==422
 with_sort=apply_archive_list_query(db.query(project.PmsProjectArchive),sort='[{"colId":"project_code","sort":"desc"}]')
 order_sql=str(with_sort.statement.compile(dialect=mssql.dialect())).split('ORDER BY')[-1]
 assert order_sql.count('pms_project_archive.project_code')==1,'SQL Server forbids repeated ORDER BY columns'
 for field,direction in (('project_code','asc'),('id','desc')):
  ordered=apply_archive_list_query(db.query(project.PmsProjectArchive),sort=json.dumps([{'colId':field,'sort':direction}]))
  sql=str(ordered.statement.compile(dialect=mssql.dialect())).split('ORDER BY')[-1]
  assert sql.count('pms_project_archive.'+field)==1
 for field in archive_columns():
  ordered=apply_archive_list_query(db.query(project.PmsProjectArchive),sort=json.dumps([{'colId':field,'sort':'asc'}]))
  str(ordered.statement.compile(dialect=mssql.dialect()))
print('archive default query contract passed')
