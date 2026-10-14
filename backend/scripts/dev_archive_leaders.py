"""Approved developer-only leader maintenance with backup and operation logs."""
import os
from pathlib import Path
import sqlite3
from datetime import datetime
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
database=ROOT/'.runtime/data/pms-dev.db'
os.environ['DB_DIALECT']='sqlite'
os.environ['SQLITE_DB_PATH']=str(database)
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.user import SysUser
from app.models.rbac import SysDept
from app.schemas.rbac import DeptUpdate
from app.services.authorization import build_authorization_context,enforce_permission
from app.services.rbac import update_dept

backup=ROOT/'.runtime/backups'/f'leaders-before-{datetime.now():%Y%m%d-%H%M%S}.db'
backup.parent.mkdir(parents=True,exist_ok=True)
with sqlite3.connect(database) as source,sqlite3.connect(backup) as target:
    source.backup(target)
    assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
os.chmod(backup,0o600)
with Session(engine) as db:
    leader=db.query(SysUser).filter_by(username='A000645',status=1).one()
    operator=db.query(SysUser).filter_by(username='ael',status=1).one()
    enforce_permission(build_authorization_context(db,operator.id),'system:user:edit')
    departments=db.query(SysDept).filter(SysDept.id.in_([1,2,3]),SysDept.status==1).all()
    assert len(departments)==3
    for department in departments:
        if department.leader_id!=leader.id:
            update_dept(db,department.id,DeptUpdate(leader_id=leader.id),operator_id=operator.id)
    print('Leaders updated:',[(department.dept_name,leader.username) for department in departments])
    print('User department assignments unchanged; backup:',backup)
