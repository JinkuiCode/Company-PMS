"""Backup restoration proves old program and old schema can recover together."""
import importlib.util
import sqlite3
import tempfile
import unittest
import os
import subprocess
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
import app.models.init_db
from app.models.user import SysUser
from app.models.database_revision import PmsDatabaseRevision


class FeedbackRestoreContract(unittest.TestCase):
    def test_cli_runs_without_caller_backend_module_path(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/restore_feedback_dev.py'
        env = {**os.environ, 'PYTHONPATH':str(script.parents[1] / '.venv-deps312')}
        result = subprocess.run([sys.executable, str(script), '--help'], env=env, cwd=tempfile.gettempdir(), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_verified_backup_restores_revision_and_preserves_pre_restore_copy(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/restore_feedback_dev.py'
        self.assertTrue(script.exists(), 'missing verified local backup restore entry')
        spec = importlib.util.spec_from_file_location('feedback_restore', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            target, backup = Path(folder)/'current.db', Path(folder)/'backup.db'
            for path, revision in ((target,'2026-10-12-feedback-02'), (backup,'2026-10-12-parameter-secret-01')):
                engine = create_engine('sqlite:///' + str(path))
                Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables if not table.name.startswith('pms_feedback_')])
                with Session(engine) as db:
                    db.add(PmsDatabaseRevision(id=1, revision=revision))
                    db.add(SysUser(username='fixture', real_name='回退验证', password_hash='unused', status=1))
                    db.commit()
                engine.dispose()
            incomplete = Path(folder)/'incomplete.db'
            with sqlite3.connect(incomplete) as db:
                db.execute('CREATE TABLE pms_database_revision(id INTEGER PRIMARY KEY, revision TEXT)')
                db.execute('INSERT INTO pms_database_revision VALUES (1, ?)', ('2026-10-12-parameter-secret-01',))
            with self.assertRaises(ValueError):
                module.restore_verified_backup(target, incomplete)
            with sqlite3.connect(target) as db:
                self.assertEqual(db.execute('SELECT revision FROM pms_database_revision').fetchone()[0], '2026-10-12-feedback-02')
            safety = module.restore_verified_backup(target, backup)
            with sqlite3.connect(target) as db:
                self.assertEqual(db.execute('SELECT revision FROM pms_database_revision').fetchone()[0], '2026-10-12-parameter-secret-01')
                self.assertEqual(db.execute('SELECT real_name FROM sys_user').fetchone()[0], '回退验证')
            with sqlite3.connect(safety) as db:
                self.assertEqual(db.execute('SELECT revision FROM pms_database_revision').fetchone()[0], '2026-10-12-feedback-02')
            with self.assertRaises(ValueError):
                module.restore_verified_backup(target, target)


if __name__ == '__main__':
    unittest.main()
