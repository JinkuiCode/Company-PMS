"""Correct only cutoffs created by this approved local upgrade, with a backup."""
from datetime import datetime
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from dev_archive_governance_upgrade import ROOT,DATABASE,DIRECTORY,backup,snapshot,verify_preserved
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.field_policy import SysBusinessFieldPolicy
from app.services.operation_log import record_operation_log,serialize_model
from app.services.field_policy import ARCHIVE_GOVERNANCE_REQUIRED_FIELDS,ARCHIVE_GOVERNANCE_CONDITIONAL_FIELDS

saved=ROOT/'.runtime/backups/archive-governance-before-20261014-120342.db'
prior=snapshot(saved)['sys_business_field_policy']
old={dict(zip(prior['columns'],row))['field_key']:dict(zip(prior['columns'],row)) for row in prior['rows']
     if dict(zip(prior['columns'],row))['module_code']=='project_archive'}
keys=[*ARCHIVE_GOVERNANCE_REQUIRED_FIELDS,*ARCHIVE_GOVERNANCE_CONDITIONAL_FIELDS]
assert all(not old.get(key,{}).get('required_effective_at') for key in keys)
before=snapshot(DATABASE)
saved_now=DIRECTORY/f'archive-governance-clock-before-{datetime.now():%Y%m%d-%H%M%S}.db'
backup(DATABASE,saved_now)
with Session(engine) as db:
    rows=db.query(SysBusinessFieldPolicy).filter(SysBusinessFieldPolicy.module_code=='project_archive',SysBusinessFieldPolicy.field_key.in_(keys)).all()
    assert len(rows)==7
    assert len({row.updated_at for row in rows})==1
    assert all(row.required_effective_at==datetime(2026,10,14,12,3,42,607439) for row in rows)
    for row in rows:
        previous=serialize_model(row)
        row.required_effective_at=row.updated_at
        db.flush()
        record_operation_log(db,module='字段规则',action='update',entity_type='sys_business_field_policy',
            entity_id='project_archive',entity_name=row.field_key,operator_id=1,
            summary='开发机档案治理升级：对齐必输规则和数据库创建时间',before_data=previous,after_data=serialize_model(row))
    db.commit()
verify_preserved(before,snapshot(DATABASE))
print('7 newly introduced cutoffs aligned to their original database update time; all business data preserved.')
print('Backup:',saved_now)
