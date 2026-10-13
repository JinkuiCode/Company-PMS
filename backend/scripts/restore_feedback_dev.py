"""Explicit local-only recovery; restore a verified pre-feedback backup, not a marker."""
import argparse
import os
from pathlib import Path
import socket
import sqlite3
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import Base
import app.models.init_db  # Register the old business table contract, without initialization.

PREVIOUS = '2026-10-12-parameter-secret-01'


def inspect_backup(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError('备份不存在或为符号链接')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('数据库完整性校验失败')
        revision = db.execute('SELECT revision FROM pms_database_revision WHERE id=1').fetchone()[0]
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in Base.metadata.sorted_tables:
            if table.name.startswith('pms_feedback_'):
                continue
            columns = {row[1] for row in db.execute('PRAGMA table_info("' + table.name.replace('"', '""') + '")')}
            if not {column.name for column in table.columns}.issubset(columns):
                raise ValueError('备份缺少旧业务表或必需字段：' + table.name)
        counts = {name: db.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for name in tables}
        return revision, counts


def restore_verified_backup(target, backup):
    if Path(target).is_symlink() or Path(backup).is_symlink():
        raise ValueError('不能恢复符号链接数据库')
    target, backup = Path(target).resolve(), Path(backup).resolve()
    if target == backup:
        raise ValueError('不能将数据库自身作为回退备份')
    before = inspect_backup(backup)
    if before[0] != PREVIOUS:
        raise ValueError('备份不是问题提报升级前的版本')
    current = inspect_backup(target)
    if current[0] not in ('2026-10-12-feedback-01', '2026-10-12-feedback-02'):
        raise ValueError('当前数据库不是本批问题提报版本')
    safety = target.with_name(target.name + '.before-restore-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    with sqlite3.connect(target) as source, sqlite3.connect(safety) as destination:
        source.backup(destination)
    os.chmod(safety, 0o600)
    if inspect_backup(safety) != current:
        raise ValueError('回退前安全副本校验失败，未执行回退')
    with sqlite3.connect(backup.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(target) as destination:
        source.backup(destination)
    if inspect_backup(target) != before:
        raise ValueError('恢复后校验不一致，请保留安全副本并停止启动')
    return safety


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='仅用于本机问题提报升级回退；恢复备份之后的数据保留在安全副本中')
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    target = root / '.runtime/data/pms-dev.db'
    if not args.apply:
        raise SystemExit('必须显式指定 --apply，并先停止本机PMS')
    for port in (8000, 5174):
        with socket.socket() as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                raise SystemExit('本机PMS仍在运行，拒绝恢复')
    safety = restore_verified_backup(target, args.backup)
    print('RESTORED: 请切回配套旧程序后启动；回退前安全副本：' + str(safety))
