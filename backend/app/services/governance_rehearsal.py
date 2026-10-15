"""Read-only SQLite source, isolated upgrade and restoration rehearsal copies."""
import hashlib
import json
import sqlite3
from pathlib import Path
from urllib.parse import quote
from sqlalchemy import create_engine
from app.services.governance_migration import upgrade_governance
from app.services.database_revision import check_database_ready


def _readonly(path):
    return sqlite3.connect('file:' + quote(str(Path(path).resolve()), safe='/') + '?mode=ro', uri=True)


def _copy(source, target):
    if target.exists(): raise RuntimeError('演练文件已存在，禁止覆盖')
    with _readonly(source) as original, sqlite3.connect(target) as copied:
        original.backup(copied)
        if copied.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise RuntimeError('数据库备份完整性检查失败')
    target.chmod(0o600)


def fingerprint(path):
    result = {}
    with _readonly(path) as db:
        for name, ddl in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            quoted = '"' + name.replace('"', '""') + '"'
            rows = sorted(json.dumps(row, ensure_ascii=False, default=str) for row in db.execute(f'SELECT * FROM {quoted}'))
            result[name] = {'rows': len(rows), 'sha256': hashlib.sha256((ddl+'\n'+'\n'.join(rows)).encode()).hexdigest()}
    return result


def rehearse(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file(): raise RuntimeError('只读源数据库不存在')
    # Never overwrite source or an existing rehearsal/backup folder.
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    before = fingerprint(source)
    backup, upgraded, restored = (output/name for name in ('before.db', 'upgraded.db', 'restored.db'))
    _copy(source, backup); _copy(backup, upgraded)
    engine = create_engine('sqlite:///' + str(upgraded))
    try:
        upgrade_governance(engine); check_database_ready(engine)
    finally: engine.dispose()
    _copy(backup, restored)
    if fingerprint(restored) != before or fingerprint(source) != before:
        raise RuntimeError('恢复副本或源库核对失败，禁止正式升级')
    result = {'source_unchanged': True, 'upgrade_copy_verified': True, 'restore_copy_verified': True,
              'tables': before, 'backup_sha256': hashlib.sha256(backup.read_bytes()).hexdigest()}
    (output/'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
