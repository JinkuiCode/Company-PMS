"""Bounded upgrade and MSSQL metadata checks, without live database access."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects.mssql.base import MSDialect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TMP = tempfile.TemporaryDirectory()
os.environ['DB_DIALECT'] = 'sqlite'
os.environ['SQLITE_DB_PATH'] = str(Path(TMP.name) / 'unused.db')
import app.models.init_db
from app.core.database import Base
from app.models.database_revision import PmsDatabaseRevision
from app.models.rbac import SysMenu, SysRole, SysRoleMenu
from app.services.database_revision import check_database_ready, DatabaseUpgradeRequired
from app.services.governance_migration import (
    upgrade_governance, verify_governance_structure, RELEASE_TABLES, PREVIOUS, REVISION,
)


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
        # Historical target stays governance-01; current startup must reject it.
        with self.assertRaises(DatabaseUpgradeRequired): check_database_ready(self.engine)
        with self.engine.connect() as c:
            verify_governance_structure(c)
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
            with patch('app.services.database_revision.CURRENT_DATABASE_REVISION', REVISION):
                result = rehearse(source, Path(tmp)/'rehearsal')
            self.assertTrue(result['restore_copy_verified'])
            self.assertEqual(fingerprint(source), before)
            self.assertEqual(fingerprint(Path(tmp)/'rehearsal/restored.db'), before)

    def test_current_full_installer_does_not_recreate_deleted_manual_nodes(self):
        from app.models.form_draft import PmsFormDraft
        from app.services.form_draft_management_migration import upgrade_draft_management
        from scripts import upgrade_database as upgrade
        upgrade_governance(self.engine)
        with self.engine.begin() as c:
            c.exec_driver_sql("DELETE FROM sys_menu WHERE permission_code='project:archive:maintain'")
        with self.engine.begin() as c: PmsFormDraft.__table__.drop(c)
        upgrade_draft_management(self.engine)
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


class MssqlGovernanceMetadata(unittest.TestCase):
    """Execute the catalog SELECT against an isolated relational sys fixture.

    Column reflection uses model metadata; the unsupported reflection method is
    the real installed MSSQL dialect method. No SQL Server or business DB is used.
    """
    def setUp(self):
        from app.models.feedback import FeedbackReport
        from app.models.operation_log import SysOperationLog
        self.tables = {t.name: t for t in (
            SysOperationLog.__table__, FeedbackReport.__table__, *RELEASE_TABLES,
        )}
        self.schema_name = "pms'bound-schema"
        self.engine = create_engine('sqlite://')
        self.catalog = self.engine.connect()
        self.catalog.exec_driver_sql("ATTACH DATABASE ':memory:' AS sys")
        for ddl in (
            'CREATE TABLE sys.schemas(schema_id INTEGER, name TEXT)',
            'CREATE TABLE sys.tables(object_id INTEGER, schema_id INTEGER, name TEXT)',
            'CREATE TABLE sys.columns(object_id INTEGER, column_id INTEGER, name TEXT)',
            'CREATE TABLE sys.indexes(object_id INTEGER, index_id INTEGER, is_unique INTEGER, '
            'is_primary_key INTEGER, is_disabled INTEGER, is_hypothetical INTEGER, has_filter INTEGER)',
            'CREATE TABLE sys.index_columns(object_id INTEGER, index_id INTEGER, column_id INTEGER, '
            'key_ordinal INTEGER, is_included_column INTEGER)',
        ):
            self.catalog.exec_driver_sql(ddl)
        self.catalog.execute(text('INSERT INTO sys.schemas VALUES (1, :name)'), {'name': self.schema_name})
        self.object_ids = {}
        for object_id, name in enumerate(self.tables, 1):
            self.object_ids[name] = object_id
            self.catalog.execute(text('INSERT INTO sys.tables VALUES (:id, 1, :name)'),
                                 {'id': object_id, 'name': name})
            for column_id, column in enumerate(self.tables[name].columns, 1):
                self.catalog.execute(text('INSERT INTO sys.columns VALUES (:id, :column, :name)'),
                                     {'id': object_id, 'column': column_id, 'name': column.name})
        self.add_index('pms_release', 1, ['version'])
        self.add_index('pms_release', 2, ['manifest_sha256'])
        self.add_index('pms_release_notice', 1, ['release_id', 'user_id'])
        self.add_index('pms_release_mail', 1, ['notice_id'])
        fixture = self

        class MetadataInspector:
            default_schema_name = fixture.schema_name

            def has_table(self, name):
                return name in fixture.tables

            def get_columns(self, name):
                return [dict(name=c.name, type=c.type, nullable=c.nullable) for c in fixture.tables[name].columns]

            def get_indexes(self, name):
                return [dict(name=i.name, unique=i.unique, column_names=[c.name for c in i.columns])
                        for i in fixture.tables[name].indexes]

            def get_unique_constraints(self, name):
                return MSDialect().get_unique_constraints(None, name)

        self.inspector = MetadataInspector()
        self.queries = []
        self.connection = SimpleNamespace(dialect=MSDialect(), execute=self.read_catalog)

    def tearDown(self):
        self.catalog.close()
        self.engine.dispose()

    def add_index(self, table, index_id, keys, *, included=(), unique=1, primary=0,
                  disabled=0, hypothetical=0, filtered=0):
        object_id = self.object_ids[table]
        self.catalog.execute(text('INSERT INTO sys.indexes VALUES (:obj, :idx, :uq, :pk, :off, :hyp, :filter)'),
            dict(obj=object_id, idx=index_id, uq=unique, pk=primary, off=disabled, hyp=hypothetical, filter=filtered))
        columns = {name: i for i, name in enumerate(self.tables[table].columns.keys(), 1)}
        # Deliberately insert composite keys out of order.
        for ordinal, name in reversed(list(enumerate(keys, 1))):
            self.catalog.execute(text('INSERT INTO sys.index_columns VALUES (:obj, :idx, :col, :ord, 0)'),
                dict(obj=object_id, idx=index_id, col=columns[name], ord=ordinal))
        for name in included:
            self.catalog.execute(text('INSERT INTO sys.index_columns VALUES (:obj, :idx, :col, 0, 1)'),
                dict(obj=object_id, idx=index_id, col=columns[name]))

    def remove_notice_key(self):
        params = {'obj': self.object_ids['pms_release_notice']}
        self.catalog.execute(text('DELETE FROM sys.indexes WHERE object_id=:obj'), params)
        self.catalog.execute(text('DELETE FROM sys.index_columns WHERE object_id=:obj'), params)

    def read_catalog(self, statement, parameters):
        sql = str(statement)
        self.assertTrue(sql.lstrip().upper().startswith('SELECT '), 'verification must be read-only')
        self.assertNotIn(self.schema_name, sql, 'schema must be a bound value')
        self.assertEqual(parameters['schema_name'], self.schema_name)
        self.queries.append((sql, parameters))
        return self.catalog.execute(statement, parameters)

    def verify(self):
        with patch('app.services.governance_migration.inspect', return_value=self.inspector):
            verify_governance_structure(self.connection)

    def test_mssql_verifies_without_unsupported_unique_reflection(self):
        try:
            self.verify()
        except NotImplementedError:
            self.fail('MSSQL verification still calls unsupported unique constraint reflection')
        self.assertEqual({params['table_name'] for _, params in self.queries},
                         {'pms_release', 'pms_release_notice', 'pms_release_mail'})

    def test_mssql_orders_key_columns_and_ignores_included_columns(self):
        self.remove_notice_key()
        self.add_index('pms_release_notice', 9, ['release_id', 'user_id'], included=['id'])
        self.verify()

    def test_mssql_never_combines_keys_from_different_indexes(self):
        self.remove_notice_key()
        self.add_index('pms_release_notice', 3, ['release_id'])
        self.add_index('pms_release_notice', 4, ['user_id'])
        with self.assertRaisesRegex(RuntimeError, '唯一约束不一致：pms_release_notice'):
            self.verify()

    def test_mssql_rejects_non_enforcing_unique_indexes(self):
        for attributes in ({'disabled': 1}, {'hypothetical': 1}, {'filtered': 1},
                           {'unique': 0}, {'primary': 1}):
            with self.subTest(attributes=attributes):
                self.remove_notice_key()
                self.add_index('pms_release_notice', 3, ['release_id', 'user_id'], **attributes)
                with self.assertRaisesRegex(RuntimeError, '唯一约束不一致：pms_release_notice'):
                    self.verify()

    def test_mssql_included_column_does_not_complete_required_key(self):
        self.remove_notice_key()
        self.add_index('pms_release_notice', 3, ['release_id'], included=['user_id'])
        with self.assertRaisesRegex(RuntimeError, '唯一约束不一致：pms_release_notice'):
            self.verify()

    def test_mssql_missing_required_unique_key_is_rejected(self):
        self.catalog.execute(text('DELETE FROM sys.indexes WHERE object_id=:obj AND index_id=1'),
                             {'obj': self.object_ids['pms_release']})
        with self.assertRaisesRegex(RuntimeError, '唯一约束不一致：pms_release'):
            self.verify()

    def test_mssql_catalog_error_is_not_silently_accepted(self):
        self.connection.execute = lambda *args: (_ for _ in ()).throw(RuntimeError('catalog unavailable'))
        with self.assertRaisesRegex(RuntimeError, 'catalog unavailable'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
