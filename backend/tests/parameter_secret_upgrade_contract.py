"""Scoped additive migration, failure rollback, downgrade compatibility."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from scripts import upgrade_database as upgrade
from app.services.database_revision import CURRENT_DATABASE_REVISION, check_database_ready

OLD = "2026-10-11-business-export-01"
NEW = "2026-10-12-parameter-secret-01"


class ParameterSecretUpgradeContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        with self.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE sys_parameter (code VARCHAR(64) PRIMARY KEY, secret_hash VARCHAR(256), value_text TEXT, version INTEGER NOT NULL, updated_at DATETIME)")
            connection.exec_driver_sql("INSERT INTO sys_parameter VALUES ('user.initial_password', 'synthetic-legacy-hash', NULL, 4, NULL)")
            connection.exec_driver_sql("CREATE TABLE pms_database_revision (id INTEGER PRIMARY KEY, revision VARCHAR(64))")
            connection.execute(text("INSERT INTO pms_database_revision VALUES (1, :revision)"), {"revision": OLD})
            connection.exec_driver_sql("CREATE TABLE unrelated (value TEXT)")
            connection.exec_driver_sql("INSERT INTO unrelated VALUES ('preserved')")

    def tearDown(self):
        self.engine.dispose()

    def run_upgrade(self, rollback=False):
        self.assertTrue(hasattr(upgrade, "upgrade_parameter_secret_only"), "Missing independent parameter-secret migration")
        # Exercise the old release's bounded entry; the current binary rejects this mode.
        with patch.object(upgrade, "CURRENT_DATABASE_REVISION", NEW), patch('app.services.database_revision.CURRENT_DATABASE_REVISION', NEW), patch('app.services.governance_migration.verify_governance_structure'), patch.object(upgrade, "engine", self.engine), patch.object(upgrade, "validate_runtime_config"), patch.object(upgrade, "init_db", side_effect=AssertionError("No historical init")):
            upgrade.upgrade_database(parameter_secret_only=not rollback, parameter_secret_rollback=rollback)

    def revision(self):
        with self.engine.connect() as connection:
            return connection.exec_driver_sql("SELECT revision FROM pms_database_revision").scalar_one()

    def test_revision_is_independently_bumped(self):
        self.assertEqual(CURRENT_DATABASE_REVISION, '2026-10-15-governance-01')

    def test_latest_release_rejects_historical_export_mode_without_changes(self):
        with patch.object(upgrade, "engine", self.engine), patch.object(upgrade, "validate_runtime_config"):
            with self.assertRaises(RuntimeError):
                upgrade.upgrade_database(business_export_only=True)
        self.assertEqual(self.revision(), OLD)
        self.assertNotIn("secret_ciphertext", {column["name"] for column in inspect(self.engine).get_columns("sys_parameter")})

    def test_idempotent_upgrade_preserves_hash_versions_values_and_unrelated_data(self):
        for _ in range(2):
            self.run_upgrade()
            self.assertEqual(self.revision(), NEW)
        with self.engine.connect() as connection:
            self.assertEqual(tuple(connection.exec_driver_sql("SELECT secret_hash, value_text, version, secret_ciphertext FROM sys_parameter").one()), ("synthetic-legacy-hash", None, 4, None))
            self.assertEqual(connection.exec_driver_sql("SELECT value FROM unrelated").scalar_one(), "preserved")

    def test_wrong_revision_is_rejected_before_schema_mutation(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql("UPDATE pms_database_revision SET revision='wrong'")
        with self.assertRaises(RuntimeError):
            self.run_upgrade()
        self.assertNotIn("secret_ciphertext", {column["name"] for column in inspect(self.engine).get_columns("sys_parameter")})
        self.assertEqual(self.revision(), "wrong")

    def test_failed_marker_write_rolls_back_column_and_version(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TRIGGER deny_revision BEFORE UPDATE ON pms_database_revision BEGIN SELECT RAISE(ABORT, 'fixture'); END")
        with self.assertRaises(IntegrityError):
            self.run_upgrade()
        self.assertNotIn("secret_ciphertext", {column["name"] for column in inspect(self.engine).get_columns("sys_parameter")})
        self.assertEqual(self.revision(), OLD)

    def test_rollback_retains_ciphertext_and_hash_for_old_binary_then_reupgrade(self):
        self.run_upgrade()
        with self.engine.begin() as connection:
            connection.exec_driver_sql("UPDATE sys_parameter SET secret_ciphertext='synthetic-encrypted-envelope'")
        self.run_upgrade(rollback=True)
        self.assertEqual(self.revision(), OLD)
        with self.engine.connect() as connection:
            self.assertEqual(tuple(connection.exec_driver_sql("SELECT secret_hash, secret_ciphertext FROM sys_parameter").one()), ("synthetic-legacy-hash", "synthetic-encrypted-envelope"))
        self.run_upgrade()
        self.assertEqual(self.revision(), NEW)

    def test_current_marker_cannot_bypass_missing_column_and_incompatible_column_rejected(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql(f"UPDATE pms_database_revision SET revision='{NEW}'")
        with self.assertRaises(RuntimeError):
            self.run_upgrade()
        with self.engine.begin() as connection:
            connection.exec_driver_sql(f"UPDATE pms_database_revision SET revision='{OLD}'")
            connection.exec_driver_sql("ALTER TABLE sys_parameter ADD secret_ciphertext INTEGER NOT NULL DEFAULT 0")
        with self.assertRaises(RuntimeError):
            self.run_upgrade()
        self.assertEqual(self.revision(), OLD)


if __name__ == "__main__":
    unittest.main()
