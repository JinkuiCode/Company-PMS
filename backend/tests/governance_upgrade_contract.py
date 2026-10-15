"""Bounded governance upgrade, using isolated SQLite databases only."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TMP = tempfile.TemporaryDirectory()
os.environ['DB_DIALECT'] = 'sqlite'
os.environ['SQLITE_DB_PATH'] = str(Path(TMP.name) / 'unused.db')
import app.models.init_db
from app.core.database import Base
from app.models.database_revision import PmsDatabaseRevision
from app.models.rbac import SysMenu, SysRole, SysRoleMenu
from app.services.database_revision import check_database_ready, DatabaseUpgradeRequired
from app.services.governance_migration import upgrade_governance, PREVIOUS, REVISION


class GovernanceUpgrade(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as c:
            from app.services.governance_migration import RELEASE_TABLES
            for table in reversed(RELEASE_TABLES): table.drop(c)
            c.exec_driver_sql('ALTER TABLE pms_feedback_report DROP COLUMN runtime_version')
            c.exec_driver_sql('DROP INDEX idx_operation_log_root')
            for name in ('root_entity_type', 'root_entity_id', 'diff_items_data'):
                c.exec_driver_sql(f'ALTER TABLE sys_operation_log DROP COLUMN {name}')
            c.execute(PmsDatabaseRevision.__table__.insert().values(id=1, revision=PREVIOUS))
            c.execute(SysMenu.__table__.insert().values(id=22, menu_name='档案', menu_type='C', path='/project/archive', permission_code='project:archive:list'))
            c.execute(SysMenu.__table__.insert().values(id=16, menu_name='日志', menu_type='C', path='/system/operation-log', permission_code='system:operation-log:list'))
            c.execute(SysRole.__table__.insert().values(id=1, role_name='管理员', role_code='admin'))
            c.execute(SysRoleMenu.__table__.insert().values(role_id=1, menu_id=22))
            c.exec_driver_sql("INSERT INTO sys_operation_log(module,action,entity_type,entity_id,status,summary,before_data) VALUES ('project','update','archive','1','success','历史记录','{\"name\":\"旧值\"}')")

    def tearDown(self):
        self.engine.dispose()

    def test_additive_upgrade_preserves_history_and_grants_nobody(self):
        upgrade_governance(self.engine)
        check_database_ready(self.engine)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT revision FROM pms_database_revision')).scalar(), REVISION)
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM sys_role_menu')).scalar(), 1)
            self.assertEqual(c.execute(text('SELECT before_data FROM sys_operation_log')).scalar(), '{"name":"旧值"}')
            self.assertIsNone(c.execute(text('SELECT diff_items_data FROM sys_operation_log')).scalar())
            self.assertEqual(c.execute(text("SELECT COUNT(*) FROM sys_menu WHERE permission_code='project:archive:maintain'")).scalar(), 1)

    def test_repeated_upgrade_does_not_recreate_revoked_permission(self):
        upgrade_governance(self.engine)
        with self.engine.begin() as c:
            c.exec_driver_sql("DELETE FROM sys_menu WHERE permission_code='project:archive:maintain'")
        upgrade_governance(self.engine)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT COUNT(*) FROM sys_menu WHERE permission_code='project:archive:maintain'")).scalar(), 0)
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM sys_role_menu')).scalar(), 1)

    def test_failure_rolls_back_columns_index_permission_and_revision(self):
        with patch('app.services.governance_migration.verify_governance_structure', side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                upgrade_governance(self.engine)
        self.assertNotIn('diff_items_data', {x['name'] for x in inspect(self.engine).get_columns('sys_operation_log')})
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT revision FROM pms_database_revision')).scalar(), PREVIOUS)
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM sys_menu')).scalar(), 2)

    def test_wrong_revision_and_fake_current_fail_closed(self):
        with self.engine.begin() as c:
            c.exec_driver_sql("UPDATE pms_database_revision SET revision='unknown'")
        with self.assertRaises(RuntimeError):
            upgrade_governance(self.engine)
        with self.engine.begin() as c:
            c.execute(PmsDatabaseRevision.__table__.update().values(revision=REVISION))
        with self.assertRaises(DatabaseUpgradeRequired):
            check_database_ready(self.engine)

    def test_startup_refuses_old_schema_before_initialization(self):
        import app.models.init_db as initializer
        with patch.object(initializer, 'engine', self.engine), patch.object(initializer.Base.metadata, 'create_all') as create:
            with self.assertRaises(RuntimeError):
                initializer.init_db()
            create.assert_not_called()

    def test_role_templates_never_implicitly_include_manual_maintenance(self):
        from sqlalchemy.orm import Session
        from app.services.role_templates import permission_ids_for_template
        upgrade_governance(self.engine)
        with Session(self.engine) as db:
            node = db.query(SysMenu).filter_by(permission_code='project:archive:maintain').one()
            for role in ('admin', 'business_admin', 'operator'):
                self.assertNotIn(node.id, permission_ids_for_template(db, role))

    def test_rehearsal_restores_original_schema_and_history_without_touching_source(self):
        from app.services.governance_rehearsal import rehearse, fingerprint
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'source.db'
            import sqlite3
            with self.engine.connect() as c, sqlite3.connect(source) as target:
                c.connection.driver_connection.backup(target)
            before = fingerprint(source)
            result = rehearse(source, Path(tmp)/'rehearsal')
            self.assertTrue(result['restore_copy_verified'])
            self.assertEqual(fingerprint(source), before)
            self.assertEqual(fingerprint(Path(tmp)/'rehearsal/restored.db'), before)

    def test_current_full_installer_does_not_recreate_deleted_manual_nodes(self):
        from scripts import upgrade_database as upgrade
        upgrade_governance(self.engine)
        with self.engine.begin() as c:
            c.exec_driver_sql("DELETE FROM sys_menu WHERE permission_code='project:archive:maintain'")
        with patch.object(upgrade, 'engine', self.engine), patch.object(upgrade, 'validate_runtime_config'), patch.object(upgrade, 'init_db') as initializer:
            upgrade.upgrade_database()
            initializer.assert_not_called()
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT COUNT(*) FROM sys_menu WHERE permission_code='project:archive:maintain'")).scalar(), 0)

    def test_mssql_2017_tables_and_indexes_compile_without_sqlite_only_features(self):
        from sqlalchemy.dialects import mssql
        from sqlalchemy.schema import CreateTable, CreateIndex
        from app.services.governance_migration import RELEASE_TABLES
        for table in RELEASE_TABLES:
            ddl = str(CreateTable(table).compile(dialect=mssql.dialect()))
            self.assertIn('CREATE TABLE', ddl)
            self.assertNotIn('NVARCHAR(None)', ddl)
            for index in table.indexes:
                self.assertIn('CREATE', str(CreateIndex(index).compile(dialect=mssql.dialect())))


if __name__ == '__main__':
    unittest.main()
