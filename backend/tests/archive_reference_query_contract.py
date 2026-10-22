"""Reference identities and label predicates keep scope and SQL pagination."""
import os, sys, tempfile, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['DB_DIALECT']='sqlite'
os.environ['SQLITE_DB_PATH']=str(Path(tempfile.mkdtemp())/'references.db')
from fastapi import HTTPException
from sqlalchemy.dialects import mssql
from app.core.database import Base, engine, SessionLocal
from app.models import project, rbac, dict as dictionaries
from app.services.project import get_archive_list
from app.services.list_query import apply_archive_list_query
Base.metadata.create_all(engine)
def c(field,operator,value):return dict(field=field,operator=operator,value=value,valueEnd=None,schemaVersion=2)
with SessionLocal() as db:
    from app.services.archive_code_unique import lock_codes
    lock_codes(db.connection())
    db.add_all([project.PmsProjectArchive(id=i,project_code=code,project_name=name,business_product_line_id=line,is_enabled=enabled,archive_category=1)
        for i,code,name,line,enabled in [(1,'A','同名',1,1),(2,'B','同名',1,0),(3,'C','另名',2,1)]])
    definition=dictionaries.SysDict(dict_code='equipment_series',dict_name='设备系列')
    db.add(definition);db.flush()
    db.add(dictionaries.SysDictItem(dict_id=definition.id,item_value='1',item_label='槽式系列',status=0))
    db.get(project.PmsProjectArchive,2).equipment_series=1
    db.commit()
    def result(*conditions,**kwargs):return get_archive_list(db,filters=json.dumps(conditions),enabled=None,**kwargs)
    assert [r.id for r in result(c('project_name','reference',[2]))['items']]==[2], '同名不能串选，禁用档案仍可查询'
    assert [r.id for r in result(c('project_code','reference',[1,2]),page=2,page_size=1)['items']]==[1]
    assert result(c('project_name','reference',[3]),scope_context={'permissions':[],'data_scope':1,'user_id':99,'product_line_ids':[]})['total']==0
    assert result(c('project_code','in',['A','B']))['total']==2
    assert [r.id for r in result(c('equipment_series','contains','槽式'))['items']]==[2], '停用枚举按名称过滤历史数据'
    assert result(c('equipment_series','contains','不存在'))['total']==0
    assert result(c('equipment_series','reference',[1]))['total']==1
    db.get(project.PmsProjectArchive,1).erp_sync_status='success'
    db.get(project.PmsProjectArchive,2).erp_sync_status='failed'
    db.commit()
    assert result(c('erp_sync_status','contains','同步成功'))['total']==1
    assert result(c('erp_sync_status','contains','同步失败'))['total']==1
    for condition in [c('project_name','reference',[]),c('project_name','reference',['2']),c('project_name','reference',[True]),c('customer','reference',[1]),c('project_code','in',[1])]:
        try:result(condition);raise AssertionError('invalid condition accepted')
        except HTTPException as exc:assert exc.status_code==422
    sql=apply_archive_list_query(db.query(project.PmsProjectArchive),[c('project_name','reference',[1,2])]).statement.compile(dialect=mssql.dialect())
    assert 1 in [v for values in sql.params.values() for v in (values if isinstance(values,list) else [values])]
    from app.models.user import SysUser
    db.add_all([SysUser(username=f'budget-{i}',real_name=f'人员{i}',password_hash='test-only',dept_id=88,status=1) for i in range(600)])
    db.commit()
    try:
        result(c('project_code','reference',list(range(1,1001))),c('project_name','reference',list(range(1,601))),
            scope_context={'permissions':[],'data_scope':2,'dept_id':88,'user_id':1,'product_line_ids':[1]})
        raise AssertionError('筛选与部门权限叠加后的参数超限未拒绝')
    except HTTPException as exc:
        assert exc.status_code==422
    db.add_all([SysUser(username=f'position-{i}',real_name=f'人员{i}',password_hash='test-only',dept_id=89,status=1) for i in range(900)])
    db.commit()
    repeated=[c('project_code','reference',list(range(1,1001)))] + [c('erp_sync_status','reference',['success']) for _ in range(49)]
    assert len(json.dumps(repeated,ensure_ascii=False))<12000
    try:
        result(*repeated,scope_context={'permissions':[],'data_scope':2,'dept_id':89,'user_id':1,'product_line_ids':[1]})
        raise AssertionError('pyodbc重复参数绑定位置超限未拒绝')
    except HTTPException as exc:
        assert exc.status_code==422
print('archive reference passed: identities, disabled records, labels, scope, pagination and bound parameters')
