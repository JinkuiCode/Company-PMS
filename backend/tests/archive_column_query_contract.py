import os, sys, tempfile, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['DB_DIALECT']='sqlite'
os.environ['SQLITE_DB_PATH']=str(Path(tempfile.mkdtemp())/'columns.db')
from fastapi import HTTPException
from app.core.database import Base,engine,SessionLocal
from app.models import project,rbac
from app.services.project import get_archive_list
from app.services.archive_column_query import archive_column_candidates
Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add_all([project.PmsProjectArchive(id=i,project_code=f'A{i}',project_name=name,business_product_line_id=line,is_enabled=1,quantity=qty) for i,name,line,qty in [(1,'A',1,0),(2,'B',1,1),(3,'A',2,None)]])
    db.commit()
    values=lambda field,items:dict(field=field,mode='values',values=items)
    filters=[values('quantity',[0,None])]
    result=get_archive_list(db,column_filters=json.dumps(filters),page_size=1)
    assert result['total']==2 and len(result['items'])==1,'列过滤必须在计数分页前执行'
    assert get_archive_list(db,column_filters=json.dumps([values('quantity',[])]))['total']==0
    from app.services.archive_column_query import apply_archive_column_filters
    from app.services.list_query import apply_archive_list_query
    from sqlalchemy.dialects import mssql
    sorted_query=apply_archive_list_query(db.query(project.PmsProjectArchive),sort=[{'colId':'project_code','sort':'asc'}])
    sorted_query=apply_archive_column_filters(sorted_query,[values('quantity',[0])])
    sorted_query=apply_archive_list_query(sorted_query.order_by(None),sort=[{'colId':'project_code','sort':'asc'}])
    order_sql=str(sorted_query.statement.compile(dialect=mssql.dialect())).split('ORDER BY')[1]
    assert order_sql.count('project_code')==1 and order_sql.count('.id')==1,'MSSQL排序字段不得重复'
    found=archive_column_candidates(db,'quantity',column_filters=json.dumps([values('quantity',[0]),values('project_name',['A'])]))
    assert {v['value'] for v in found['items']}=={0,None},'候选保留其他列，排除本列'
    assert archive_column_candidates(db,'quantity',scope_context={'permissions':[],'data_scope':1,'user_id':99,'product_line_ids':[]})['items']==[]
    assert archive_column_candidates(db,'is_enabled',keyword='启用')['items'][0]['label']=='启用','候选值应显示并搜索枚举名称'
    from unittest.mock import patch
    with patch('app.services.archive_column_query.archive_candidate_labels',return_value={i:str(i) for i in range(1100)}):
        try:archive_column_candidates(db,'is_enabled');raise AssertionError('候选显示标签的SQL参数也要纳入预算')
        except HTTPException as e:assert e.status_code==422
    for invalid in [values('missing',['A']),values('quantity',['invalid']),{'field':'quantity','mode':'bad'}]:
        try:get_archive_list(db,column_filters=json.dumps([invalid]));raise AssertionError('非法列筛选不能扩大范围')
        except HTTPException as e:assert e.status_code==422
    from app.models.user import SysUser
    db.add(SysUser(id=7,username='column-test-user',real_name='Member',password_hash='test-only-placeholder'))
    db.query(project.PmsProjectArchive).filter(project.PmsProjectArchive.id.in_([1,2])).update(
        {'manager_id':7,'created_by':7,'updated_by':7,'erp_sync_by':7},synchronize_session=False)
    db.commit()
    from sqlalchemy.orm import Query
    original_all = Query.all
    compiled_candidates = []
    def checked_all(query):
        dialect = mssql.dialect()
        dialect.server_version_info = (14,0)
        sql = str(query.statement.compile(dialect=dialect,compile_kwargs={'render_postcompile':True}))
        if 'GROUP BY' in sql:
            compiled_candidates.append(sql)
            group = sql.rsplit('GROUP BY',1)[1]
            assert 'SELECT' not in group,'MSSQL GROUP BY不得直接包含人员scalar SELECT'
            assert '.value' in group,'外层聚合必须按派生value别名'
            assert 'pms_project_archive.id AS archive_id' in sql,'派生输入必须保留档案ID及outer FROM'
        return original_all(query)
    for field in ('manager_name','created_by_name','updated_by_name','erp_sync_by_name'):
        found = archive_column_candidates(db,field)
        assert {row['value']:row['count'] for row in found['items']}=={None:1,'Member':2},'人员候选count必须以档案行计数，不是无FROM的标量行'
        with patch.object(Query,'all',checked_all):
            found = archive_column_candidates(db,field,column_filters=[values('quantity',[0,1])],keyword='Member',page_size=1)
        assert found['items']==[{'value':'Member','label':'Member','count':2}] and not found['hasMore']
    assert len(compiled_candidates)==4,'四类人员列都需要MSSQL编译验证'
    print('GREEN personnel candidates: scoped archive id/value derived grouping and MSSQL compile')
    from datetime import datetime
    stamps = [datetime(2026,10,11,0,0),datetime(2026,10,11,23,59,59),datetime(2026,10,12,0,0)]
    for key,stamp in enumerate(stamps,1):
        db.query(project.PmsProjectArchive).filter(project.PmsProjectArchive.id==key).update(
            {'plan_start_date':stamp},synchronize_session=False)
    db.commit()
    found = archive_column_candidates(db,'plan_start_date',page_size=1)
    assert found['items']==[{'value':'2026-10-11','label':'2026-10-11','count':2}] and found['hasMore'],'日期候选按天合并计数后分页'
    selected = [values('plan_start_date',['2026-10-11'])]
    result = get_archive_list(db,column_filters=json.dumps(selected),page_size=1)
    assert result['total']==2 and len(result['items'])==1,'日期checkbox必须匹配当天全部时间，不得用raw DateTime IN day'
    result = get_archive_list(db,column_filters=json.dumps([values('plan_start_date',['2026-10-11','2026-10-12'])]))
    assert result['total']==3,'日期checkbox多天并集不能丢失非零时分秒'
    with patch.object(db.bind.dialect,'name','mssql'):
        query = apply_archive_column_filters(db.query(project.PmsProjectArchive),selected)
    dialect = mssql.dialect(paramstyle='qmark')
    dialect.server_version_info = (14,0)
    compiled = query.statement.compile(dialect=dialect,compile_kwargs={'render_postcompile':True})
    assert 'CAST(pms_project_archive.plan_start_date AS DATE)' in str(compiled),'MSSQL日期membership必须比较DATE投影'
    assert len(compiled.positiontup)==len(compiled.params),'MSSQL日期绑定参数必须完整'
    date_candidate_sql = []
    def compile_date_candidates(query):
        compiled = query.statement.compile(dialect=dialect,compile_kwargs={'render_postcompile':True})
        date_candidate_sql.append(str(compiled))
        assert 'CAST(pms_project_archive.plan_start_date AS DATE)' in str(compiled),'MSSQL日期候选必须使用DATE投影'
        assert 'GROUP BY archive_candidate_rows.value' in str(compiled),'日期候选外层必须按day别名聚合'
        return []
    with patch.object(db.bind.dialect,'name','mssql'),patch.object(Query,'all',compile_date_candidates):
        archive_column_candidates(db,'plan_start_date',keyword='2026-10-11',page=2,page_size=1)
    assert len(date_candidate_sql)==1
    print('GREEN date candidates/filter: day membership, full timestamps, MSSQL DATE compile')
    for key,customer in [(1,None),(2,''),(3,'   ')]:
        db.query(project.PmsProjectArchive).filter(project.PmsProjectArchive.id==key).update(
            {'customer':customer},synchronize_session=False)
    db.commit()
    found = archive_column_candidates(db,'customer')
    assert found['items']==[{'value':None,'label':'（空白）','count':3}],'NULL/空字符串/空白候选必须规范为null并合并count'
    for selected in ([None],[''],['   '],[None,'']):
        result = get_archive_list(db,column_filters=json.dumps([values('customer',selected)]),page_size=1)
        assert result['total']==3 and len(result['items'])==1,'null及旧空字符串checkbox必须匹配全部空白档案'
    db.query(project.PmsProjectArchive).filter(project.PmsProjectArchive.id==3).update({'customer':' Acme '},synchronize_session=False)
    db.commit()
    found = archive_column_candidates(db,'customer',page_size=1)
    assert found['items']==[{'value':None,'label':'（空白）','count':2}] and found['hasMore'],'空白组仍须在完整范围合并后分页'
    result = get_archive_list(db,column_filters=json.dumps([values('customer',[None,'Acme'])]))
    assert result['total']==3,'空白与非空checkbox是并集，非空文本去首尾空白'
    query = apply_archive_column_filters(db.query(project.PmsProjectArchive),[values('customer',[''])])
    sql = str(query.statement.compile(dialect=dialect,compile_kwargs={'render_postcompile':True}))
    assert 'customer IS NULL' in sql and 'trim(' in sql,'MSSQL空白checkbox必须编译为空值或trim空字符串'
    print('GREEN blank candidates/filter: null normalization, merged counts, legacy empty values, MSSQL compile')
    # Input predicates fit the 2000 budget; candidate projection/paging pushes
    # the final statement over it and must fail before any execution.
    filters = [{'field':'project_code','operator':'reference','value':list(range(1,1001)),'schemaVersion':2}]
    columns = [values('quantity',list(range(1000)))]
    with patch.object(Query,'all',side_effect=AssertionError('最终预算超限不得执行SQL')):
        try:
            archive_column_candidates(db,'project_name',filters=filters,column_filters=columns)
            raise AssertionError('派生投影后的最终候选参数预算仍必须执行')
        except HTTPException as error:
            assert error.status_code==422 and '候选' in error.detail,'应由最终候选预算而非提前条件预算拒绝'
    print('GREEN final candidate budget: derived projection and paging included; over 2000 rejected')
print('archive column query passed: scoped candidates, before paging, null/zero, invalid closed')
