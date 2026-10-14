"""Development-only online backup, upgrade rehearsal and bounded apply."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
os.environ['DB_DIALECT']='sqlite'
os.environ['SQLITE_DB_PATH']=str(ROOT/'.runtime/data/pms-dev.db')
from sqlalchemy import create_engine
from app.services.archive_governance_migration import upgrade_archive_governance,REVISION,PREVIOUS,FIRST_REVISION

DATABASE=ROOT/'.runtime/data/pms-dev.db'
DIRECTORY=ROOT/'.runtime/backups'
POLICIES={'archive_category','machine_model','quantity','quantity_unit','manager_id','equipment_series','serial_no','plan_start_date','plan_end_date'}

def connect(path):return sqlite3.connect(f'file:{path}?mode=ro',uri=True)
def digest_rows(rows):
    return hashlib.sha256(json.dumps(sorted(rows,key=repr),ensure_ascii=False,default=str).encode()).hexdigest()
def backup(source,target):
    with connect(source) as original,sqlite3.connect(target) as copy:
        original.backup(copy)
        assert copy.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    os.chmod(target,0o600)
def snapshot(path):
    with connect(path) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        result={}
        for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            columns=[row[1] for row in db.execute(f'PRAGMA table_info("{table}")')]
            result[table]={'columns':columns,'rows':db.execute(f'SELECT * FROM "{table}"').fetchall()}
        return result
def verify_preserved(before,after):
    for table,original in before.items():
        if table=='pms_database_revision':continue
        current=after[table]
        removed={'plan_start_date','plan_end_date'} if table=='pms_project_archive' else set()
        columns=[key for key in original['columns'] if key not in removed]
        expected=set(columns)|({'governance_legacy'} if table=='pms_project_archive' else set())
        assert expected==set(current['columns']),f'Unexpected schema change: {table}'
        def filtered(data):
            rows=[]
            for values in data['rows']:
                row=dict(zip(data['columns'],values))
                source_revision=before['pms_database_revision']['rows'][0][1]
                if source_revision==PREVIOUS and table=='sys_business_field_policy' and row['module_code']=='project_archive' and row['field_key'] in POLICIES:continue
                if table in ('sys_dict','sys_dict_item','sys_operation_log'):
                    ids={item[original['columns'].index('id')] for item in original['rows']}
                    if row['id'] not in ids:continue
                rows.append(tuple(row[key] for key in columns))
            return rows
        assert digest_rows(filtered(original))==digest_rows(filtered(current)),f'Unexpected data change: {table}'
    assert after['pms_archive_change']['rows']==[]
    assert len(after['pms_project_archive']['rows'])==len(before['pms_project_archive']['rows'])
    marker_index=after['pms_project_archive']['columns'].index('governance_legacy')
    assert all(row[marker_index]==1 for row in after['pms_project_archive']['rows'])

def upgrade(path):
    engine=create_engine(f'sqlite:///{path}')
    try:upgrade_archive_governance(engine)
    finally:engine.dispose()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    saved=DIRECTORY/f'archive-governance-before-{stamp}.db'
    backup(DATABASE,saved);before=snapshot(saved)
    assert before['pms_database_revision']['rows'][0][1] in (PREVIOUS,FIRST_REVISION),'Unexpected starting revision'
    rehearsal=DIRECTORY/f'archive-governance-rehearsal-{stamp}.db';backup(saved,rehearsal)
    upgrade(rehearsal);verify_preserved(before,snapshot(rehearsal))
    restored=DIRECTORY/f'archive-governance-restored-{stamp}.db';backup(saved,restored)
    assert snapshot(restored)==before,'Restore rehearsal failed'
    report={'backup':str(saved),'sha256':hashlib.sha256(saved.read_bytes()).hexdigest(),'archives':len(before['pms_project_archive']['rows']),
            'rehearsal':'passed','restore':'passed','target':REVISION,'applied':False}
    if args.apply:
        # Caller must stop only the development backend before this mode.
        try:
            upgrade(DATABASE);verify_preserved(before,snapshot(DATABASE));report['applied']=True
        except Exception:
            with connect(saved) as original,sqlite3.connect(DATABASE) as target:original.backup(target)
            assert snapshot(DATABASE)==before
            raise
    report_path=DIRECTORY/f'archive-governance-{stamp}.json'
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2));os.chmod(report_path,0o600)
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
