"""Read-only SQLite source; backup, upgrade and restore occur only in new copies."""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from sqlalchemy import create_engine
from app.services.governance_rehearsal import _readonly, fingerprint
from app.services.form_draft_migration import upgrade_form_drafts, verify_form_draft_structure, REVISION


def _copy(source, target):
    if target.exists(): raise FileExistsError('演练文件已存在，禁止覆盖')
    with closing(_readonly(source)) as original, closing(sqlite3.connect(target)) as copied:
        original.backup(copied)
        if copied.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('数据库备份完整性检查失败')
    target.chmod(0o600)


def rehearse(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file(): raise RuntimeError('只读源数据库不存在')
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    before = fingerprint(source)
    backup, upgraded, restored = (output/name for name in ('before.db','upgraded.db','restored.db'))
    _copy(source, backup); _copy(backup, upgraded)
    engine = create_engine('sqlite:///' + str(upgraded))
    try:
        upgrade_form_drafts(engine)
        with engine.connect() as connection:verify_form_draft_structure(connection)
        after = fingerprint(upgraded)
        preserved = {k:v for k,v in before.items() if k != 'pms_database_revision'}
        if any(after.get(k) != value for k,value in preserved.items()):
            raise RuntimeError('升级改变了历史表结构或数据，禁止实际升级')
        if set(after)-set(before) != {'pms_form_draft'}:
            raise RuntimeError('升级增加了范围外表结构')
    finally: engine.dispose()
    _copy(backup, restored)
    if fingerprint(source) != before or fingerprint(restored) != before:
        raise RuntimeError('恢复副本或只读源库核对失败')
    result = {'source_unchanged':True,'upgrade_copy_verified':True,'restore_copy_verified':True,
              'revision':REVISION,'tables_preserved':len(preserved),
              'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest()}
    (output/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
