"""The production export upgrade must not replay historical initialization."""
import importlib
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.database_revision import PmsDatabaseRevision
from app.models.rbac import SysMenu, SysRole, SysRoleMenu
from app.services import database_revision


OLD = "2026-10-09-archive-02"
# This contract exercises the historical export-only release, not the latest schema.
CURRENT_DATABASE_REVISION = "2026-10-11-business-export-01"
CODES = ("project:archive:export", "project:list:export")


class ExportUpgradeContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        for model in (SysRole, SysMenu, SysRoleMenu, PmsDatabaseRevision):
            model.__table__.create(self.engine)
        with Session(self.engine) as db:
            db.add_all([
                SysRole(id=1, role_name="Admin", role_code="admin", status=1, data_scope=1),
                SysRole(id=2, role_name="Operator", role_code="operator", status=1, data_scope=2),
                SysMenu(id=21, parent_id=2, menu_name="Progress", menu_type="C", path="/project/list", permission_code="project:list"),
                SysMenu(id=22, parent_id=2, menu_name="Archive", menu_type="C", path="/project/archive", permission_code="project:archive:list"),
                SysMenu(id=90, menu_name="All data", menu_type="B", permission_code="business:data:all", status=0),
                PmsDatabaseRevision(id=1, revision=OLD),
            ])
            db.commit()
            db.add(SysRoleMenu(role_id=2, menu_id=21))
            db.commit()

    def tearDown(self):
        self.engine.dispose()

    def upgrade(self):
        module = importlib.import_module("scripts.upgrade_database")
        self.assertIn("business_export_only", module.upgrade_database.__annotations__, "Missing scoped upgrade mode")
        with patch.object(module, "CURRENT_DATABASE_REVISION", CURRENT_DATABASE_REVISION), patch.object(database_revision, "CURRENT_DATABASE_REVISION", CURRENT_DATABASE_REVISION), patch('app.services.governance_migration.verify_governance_structure'), patch('app.services.form_draft_migration.verify_form_draft_structure'), patch.object(module, "engine", self.engine), patch.object(module, "validate_runtime_config"), patch.object(module, "init_db", side_effect=AssertionError("Historical init must not run")):
            module.upgrade_database(business_export_only=True)

    def snapshot(self, model):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(select(model.__table__).order_by(model.id)).mappings()]

    def test_only_two_nodes_and_enabled_admin_grants_change(self):
        old_roles = self.snapshot(SysRole)
        old_menus = self.snapshot(SysMenu)
        self.upgrade()
        self.assertEqual(self.snapshot(SysRole), old_roles)
        current = self.snapshot(SysMenu)
        self.assertEqual(current[:3], old_menus)
        self.assertEqual({row["permission_code"] for row in current[3:]}, set(CODES))
        grants = self.snapshot(SysRoleMenu)
        self.assertEqual(len(grants), 3)
        self.assertEqual({row["role_id"] for row in grants[1:]}, {1})
        self.assertEqual(self.snapshot(PmsDatabaseRevision)[0]["revision"], CURRENT_DATABASE_REVISION)

    def test_disabled_admin_does_not_receive_new_grants(self):
        with self.engine.begin() as connection:
            connection.execute(SysRole.__table__.update().where(SysRole.id == 1).values(status=0))
        self.upgrade()
        self.assertEqual(len(self.snapshot(SysRoleMenu)), 1)

    def test_existing_disabled_node_and_revoked_grant_are_preserved(self):
        with Session(self.engine) as db:
            db.add(SysMenu(id=301, parent_id=22, menu_name="Customized", menu_type="B", permission_code=CODES[0], status=0))
            db.commit()
        before = self.snapshot(SysMenu)
        self.upgrade()
        self.assertEqual(self.snapshot(SysMenu)[:4], before)
        grants = self.snapshot(SysRoleMenu)
        self.assertFalse(any(row["menu_id"] == 301 for row in grants))
        before_again = (self.snapshot(SysMenu), grants)
        self.upgrade()
        self.assertEqual((self.snapshot(SysMenu), self.snapshot(SysRoleMenu)), before_again)

    def test_wrong_revision_rolls_back_without_any_menu_change(self):
        with self.engine.begin() as connection:
            connection.execute(PmsDatabaseRevision.__table__.update().values(revision="unexpected"))
        before = self.snapshot(SysMenu)
        with self.assertRaises(RuntimeError):
            self.upgrade()
        self.assertEqual(self.snapshot(SysMenu), before)
        self.assertEqual(self.snapshot(PmsDatabaseRevision)[0]["revision"], "unexpected")

    def test_conflicting_second_node_rolls_back_first_node_and_revision(self):
        with Session(self.engine) as db:
            db.add(SysMenu(id=302, parent_id=11, menu_name="Wrong", menu_type="B", permission_code=CODES[1]))
            db.commit()
        before = self.snapshot(SysMenu)
        with self.assertRaises(RuntimeError):
            self.upgrade()
        self.assertEqual(self.snapshot(SysMenu), before)
        self.assertEqual(self.snapshot(PmsDatabaseRevision)[0]["revision"], OLD)

    def missing_dependency(self, model, id_):
        with self.engine.begin() as connection:
            connection.execute(model.__table__.delete().where(model.id == id_))
        before = self.snapshot(SysMenu)
        with self.assertRaises(RuntimeError):
            self.upgrade()
        self.assertEqual(self.snapshot(SysMenu), before)
        self.assertEqual(self.snapshot(PmsDatabaseRevision)[0]["revision"], OLD)

    def test_missing_admin_fails_without_bootstrap(self):
        self.missing_dependency(SysRole, 1)

    def test_missing_parent_fails_without_bootstrap(self):
        self.missing_dependency(SysMenu, 22)

    def test_current_marker_with_missing_nodes_cannot_skip_upgrade(self):
        with self.engine.begin() as connection:
            connection.execute(PmsDatabaseRevision.__table__.update().values(revision=CURRENT_DATABASE_REVISION))
        before = self.snapshot(SysMenu)
        with self.assertRaises(RuntimeError):
            self.upgrade()
        self.assertEqual(self.snapshot(SysMenu), before)

    def test_grant_failure_rolls_back_nodes_and_version_together(self):
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TRIGGER deny_grant BEFORE INSERT ON sys_role_menu BEGIN SELECT RAISE(ABORT, 'fixture'); END"))
        before = self.snapshot(SysMenu)
        with self.assertRaises(IntegrityError):
            self.upgrade()
        self.assertEqual(self.snapshot(SysMenu), before)
        self.assertEqual(self.snapshot(PmsDatabaseRevision)[0]["revision"], OLD)


if __name__ == "__main__":
    unittest.main()
