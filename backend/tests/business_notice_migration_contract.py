"""Bounded notification DDL and no implicit grants, using disposable databases."""
import unittest
from unittest.mock import patch
from sqlalchemy import inspect, select
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import mssql
import archive_policy_upgrade_contract as old
from app.models.business_notice import BusinessNotice, BusinessNoticeMail
from app.models.database_revision import PmsDatabaseRevision
from app.models.rbac import SysMenu, SysRoleMenu
from app.services import business_notice_migration as migration
from app.services.database_revision import check_database_ready, DatabaseUpgradeRequired

class NoticeMigration(unittest.TestCase):
    def setUp(self):
        old.PolicyUpgrade.setUp(self)
        self.migration.upgrade_archive_policy(self.engine)
        with self.engine.begin() as c:
            BusinessNoticeMail.__table__.drop(c);BusinessNotice.__table__.drop(c)
        self.migration=migration
    tearDown=old.PolicyUpgrade.tearDown

    def test_bounded_upgrade_repeat_and_read_only_startup(self):
        with self.assertRaises(DatabaseUpgradeRequired):check_database_ready(self.engine)
        self.assertFalse(inspect(self.engine).has_table('pms_business_notice'))
        migration.upgrade_business_notices(self.engine)
        migration.upgrade_business_notices(self.engine)
        check_database_ready(self.engine)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(select(PmsDatabaseRevision.revision)).scalar(),migration.REVISION)
            self.assertEqual(len(c.execute(select(SysMenu).where(SysMenu.permission_code.in_(migration.PERMISSIONS))).all()),2)
            self.assertEqual(c.execute(select(SysRoleMenu)).all(),[])
            self.assertEqual(c.execute(select(BusinessNotice)).all(),[])

    def test_partial_structure_is_rejected_without_adopting_it(self):
        with self.engine.begin() as c:BusinessNotice.__table__.create(c)
        with self.assertRaisesRegex(RuntimeError,'部分|已有'):migration.upgrade_business_notices(self.engine)
        self.assertFalse(inspect(self.engine).has_table('pms_business_notice_mail'))
        with self.engine.connect() as c:self.assertEqual(c.execute(select(PmsDatabaseRevision.revision)).scalar(),migration.PREVIOUS)

    def test_failure_rolls_back_ddl_and_permissions(self):
        with patch.object(migration,'verify_business_notice_structure',side_effect=RuntimeError('verify failed')):
            with self.assertRaisesRegex(RuntimeError,'verify failed'):migration.upgrade_business_notices(self.engine)
        self.assertFalse(inspect(self.engine).has_table('pms_business_notice'))
        with self.engine.connect() as c:
            self.assertEqual(c.execute(select(SysMenu).where(SysMenu.permission_code.in_(migration.PERMISSIONS))).all(),[])
            self.assertEqual(c.execute(select(PmsDatabaseRevision.revision)).scalar(),migration.PREVIOUS)

    def test_target_marker_cannot_mask_missing_index_or_permission(self):
        migration.upgrade_business_notices(self.engine)
        with self.engine.begin() as c:c.exec_driver_sql('DROP INDEX idx_business_notice_personal')
        with self.assertRaises(DatabaseUpgradeRequired):check_database_ready(self.engine)
        with self.assertRaises(RuntimeError):migration.upgrade_business_notices(self.engine)

    def test_conflicting_permission_and_old_revision_fail_without_write(self):
        with self.engine.begin() as c:c.execute(SysMenu.__table__.insert().values(menu_name='冲突',menu_type='C',permission_code=migration.PERMISSIONS[0]))
        with self.assertRaises(RuntimeError):migration.upgrade_business_notices(self.engine)
        self.assertFalse(inspect(self.engine).has_table('pms_business_notice'))
        with self.engine.begin() as c:c.execute(PmsDatabaseRevision.__table__.update().values(revision='upgrading'))
        with self.assertRaises(RuntimeError):migration.upgrade_business_notices(self.engine)

    def test_cli_requires_explicit_current_bounded_mode(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('notice_upgrade_cli','backend/scripts/upgrade_database.py')
        cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
        with patch.object(cli,'validate_runtime_config'),patch.object(cli,'engine',self.engine):
            for flags in ({},{'archive_policy_only':True}):
                with self.assertRaises(RuntimeError):cli.upgrade_database(**flags)
            cli.upgrade_database(business_notices_only=True)
        check_database_ready(self.engine)

    def test_fresh_explicit_install_and_worker_defaults(self):
        import os, sys, subprocess, tempfile, sqlite3
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            filename=Path(folder)/'fresh.db'
            env={key:os.environ[key] for key in ('PATH','PYTHONPATH','PYTHONDONTWRITEBYTECODE') if key in os.environ}
            env.update(PMS_CONFIG_FILE=str(Path(folder)/'empty.env'),PMS_ENV='development',DB_DIALECT='sqlite',
                       SQLITE_DB_PATH=str(filename),SECRET_KEY='isolated-notice-fixture-secret-32-characters')
            result=subprocess.run([sys.executable,'backend/scripts/upgrade_database.py'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            with sqlite3.connect(filename) as db:
                self.assertEqual(db.execute('SELECT revision FROM pms_database_revision').fetchone()[0],migration.REVISION)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM sys_role_menu r JOIN sys_menu m ON m.id=r.menu_id WHERE m.permission_code LIKE 'project:archive:notification:%'").fetchone()[0],0)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM pms_business_notice').fetchone()[0],0)
            from app.core.config import Settings
            self.assertFalse(Settings(_env_file=None).PMS_BUSINESS_NOTICE_MAIL_WORKER_ENABLED)

    def test_mssql_ddl_unicode_keys_and_role_template_exclusions(self):
        from app.services.role_templates import MANUAL_ONLY_PERMISSIONS, permission_ids_for_template
        from sqlalchemy.orm import Session
        for table in (BusinessNotice.__table__,BusinessNoticeMail.__table__):
            sql=str(CreateTable(table).compile(dialect=mssql.dialect()))
            self.assertIn('NVARCHAR',sql);self.assertIn('FOREIGN KEY',sql);self.assertIn('UNIQUE',sql)
            for index in table.indexes:self.assertIn('CREATE INDEX',str(CreateIndex(index).compile(dialect=mssql.dialect())))
        self.assertTrue(set(migration.PERMISSIONS).issubset(MANUAL_ONLY_PERMISSIONS))
        migration.upgrade_business_notices(self.engine)
        with Session(self.engine) as db:
            target={n.id for n in db.query(SysMenu).filter(SysMenu.permission_code.in_(migration.PERMISSIONS))}
            self.assertFalse(target & permission_ids_for_template(db,'admin'))

if __name__=='__main__':unittest.main()
