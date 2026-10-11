"""Unified archive predicates execute before paging and within the existing scope."""
import os, sys, tempfile, datetime, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DB_DIALECT'] = 'sqlite'
os.environ['SQLITE_DB_PATH'] = str(Path(tempfile.mkdtemp()) / 'query.db')
from fastapi import HTTPException
from sqlalchemy.dialects import mssql
from app.core.database import Base, engine, SessionLocal
from app.models import project, rbac
from app.services.project import get_archive_list
from app.services.list_query import apply_archive_list_query
Base.metadata.create_all(engine)

def c(field, operator, value=None, end=None, version=2):
    return dict(field=field, operator=operator, value=value, valueEnd=end, schemaVersion=version)

with SessionLocal() as db:
    for i, (name, qty, line) in enumerate([('Pump%_',0,1),('Pump',10,2),('X-Pump',20,1),(None,None,None),('',30,2)]):
        db.add(project.PmsProjectArchive(project_code=f'A-{i}',project_name=name,quantity=qty,business_product_line_id=line,is_enabled=1,
            plan_start_date=datetime.datetime(2026,10,10,12) if i<3 else None))
    db.commit()
    def ids(*conditions, **kwargs):
        return [r.project_code for r in get_archive_list(db,filters=json.dumps(conditions),**kwargs)['items']]
    assert ids(c('project_name','startsWith','Pump')) == ['A-1','A-0']
    assert ids(c('project_name','endsWith','Pump')) == ['A-2','A-1']
    assert ids(c('project_name','contains','%_')) == ['A-0']
    assert ids(c('project_name','notContains','Pump')) == [], '否定匹配不自动包含NULL或空字符串'
    assert ids(c('project_name','notEquals','Pump')) == ['A-2','A-0']
    assert ids(c('project_name','notEquals','Pump',version=1)) == ['A-4','A-3','A-2','A-0']
    assert ids(c('project_name','isEmpty')) == ['A-4','A-3']
    assert ids(c('quantity','isEmpty')) == ['A-3']
    assert ids(c('quantity','equals',0)) == ['A-0']
    assert ids(c('quantity','greaterOrEqual',10),c('quantity','lessOrEqual',20)) == ['A-2','A-1']
    assert ids(c('product_line_id','in',[1,2])) == ['A-4','A-2','A-1','A-0']
    assert ids(c('product_line_id','notIn',[1])) == ['A-4','A-1']
    assert ids(c('plan_start_date','lessOrEqual','2026-10-10')) == ['A-2','A-1','A-0']
    assert ids(c('plan_start_date','greaterThan','2026-10-10')) == []
    assert ids(c('plan_start_date','between','2026-10-10','2026-10-10')) == ['A-2','A-1','A-0']
    assert ids(c('product_line_id','in',[1,2]),page=2,page_size=2) == ['A-1','A-0']
    assert ids(c('quantity','notEmpty'),scope_context={'permissions':[],'data_scope':1,'user_id':999,'product_line_ids':[]}) == []
    invalid = [c('password','equals','x'),c('quantity','between',20,10),c('plan_start_date','equals','2026-02-30'),
        c('quantity','equals',True),c('quantity','equals','nan'),c('project_name','equals',['x']),c('product_line_id','in',[]),
        c('product_line_id','in',[True]),c('customer','in',['x']),c('quantity','equals',None),c('quantity','equals',1,version=999)]
    for item in invalid:
        try:
            ids(item)
            raise AssertionError(f'非法条件未拒绝: {item}')
        except HTTPException as exc:
            assert exc.status_code == 422
    statement = apply_archive_list_query(db.query(project.PmsProjectArchive),[c('project_name','notContains',"x'; DROP TABLE x --")]).statement
    compiled = statement.compile(dialect=mssql.dialect())
    assert 'DROP TABLE' not in str(compiled), '值只能作为绑定参数'
    brackets = apply_archive_list_query(db.query(project.PmsProjectArchive),[c('project_name','contains','[AB]%_/')]).statement.compile(dialect=mssql.dialect())
    assert '/[ab]/%/_//' in brackets.params.values(), 'SQL Server方括号和通配符必须按字面匹配'
print('unified archive query passed: typed predicates, old/new null semantics, date boundaries, pagination, scope, MSSQL bindings')
