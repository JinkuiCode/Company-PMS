"""Revision 02 backup/recovery rehearsal; opens the source strictly read-only."""
import hashlib,json
from pathlib import Path
from contextlib import closing
from sqlalchemy import create_engine
from app.services.form_draft_rehearsal import _copy
from app.services.governance_rehearsal import _readonly,fingerprint
from app.services.form_draft_management_migration import upgrade_draft_management,REVISION,PERMISSION
from app.services.database_revision import check_database_ready

def _rows(path,table):
    with closing(_readonly(path)) as connection:
        connection.row_factory=__import__('sqlite3').Row
        return [dict(row) for row in connection.execute('SELECT * FROM '+table+' ORDER BY id')]

def rehearse(source,output):
    source,output=Path(source).resolve(),Path(output).resolve()
    if not source.is_file():raise RuntimeError('只读源库不存在')
    output.mkdir(mode=0o700,parents=False,exist_ok=False)
    before=fingerprint(source)
    backup,upgraded,restored=(output/name for name in ('before.db','upgraded.db','restored.db'))
    _copy(source,backup);_copy(backup,upgraded)
    engine=create_engine('sqlite:///'+str(upgraded))
    try:
        upgrade_draft_management(engine);check_database_ready(engine)
        after=fingerprint(upgraded)
        expected_tables=set(before)|{'pms_form_draft'}
        if set(after)!=expected_tables:raise RuntimeError('升级增加范围外数据表')
        for name,value in before.items():
            if name not in ('pms_database_revision','pms_form_draft','sys_menu') and after.get(name)!=value:
                raise RuntimeError('升级改变历史表：'+name)
        old_menus=_rows(backup,'sys_menu');new_menus=_rows(upgraded,'sys_menu')
        if any(row not in new_menus for row in old_menus):raise RuntimeError('升级改变原权限节点')
        added=[row for row in new_menus if row not in old_menus]
        existing=[row for row in old_menus if row['permission_code']==PERMISSION]
        if len(added)!=(0 if existing else 1) or any(row['permission_code']!=PERMISSION for row in added):
            raise RuntimeError('升级增加范围外权限节点')
        old_drafts=_rows(backup,'pms_form_draft') if 'pms_form_draft' in before else []
        new_drafts={row['id']:row for row in _rows(upgraded,'pms_form_draft')}
        if len(old_drafts)!=len(new_drafts):raise RuntimeError('升级改变草稿条数')
        for row in old_drafts:
            upgraded_row=new_drafts[row['id']]
            if any(upgraded_row.get(key)!=value for key,value in row.items()):
                raise RuntimeError('升级改变历史草稿内容')
    finally:engine.dispose()
    _copy(backup,restored)
    if fingerprint(source)!=before or fingerprint(restored)!=before:raise RuntimeError('恢复副本或只读源库核验失败')
    result={'source_unchanged':True,'upgrade_copy_verified':True,'restore_copy_verified':True,'revision':REVISION,
        'drafts_preserved':len(old_drafts),'original_tables':len(before),
        'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest()}
    (output/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
