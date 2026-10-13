"""Isolated feedback migration never replenishes revoked permissions."""
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import Base
import app.models.init_db  # Register existing dependencies without running setup.
from app.models.rbac import SysMenu, SysRole, SysRoleMenu
from app.models.database_revision import PmsDatabaseRevision
from app.models.dict import SysDictItem


class FeedbackUpgradeContract(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.feedback_migration'), 'missing bounded feedback migration')
        self.migration = importlib.import_module('app.services.feedback_migration')
        self.engine = create_engine('sqlite://')
        old_tables = [table for table in Base.metadata.sorted_tables if not table.name.startswith('pms_feedback_')]
        Base.metadata.create_all(self.engine, tables=old_tables)
        self.db = Session(self.engine)
        for code in ('admin', 'business_admin', 'operator', 'custom'):
            self.db.add(SysRole(role_code=code, role_name=code, status=1))
        self.db.add(PmsDatabaseRevision(id=1, revision='2026-10-12-parameter-secret-01'))
        self.db.commit()

    def tearDown(self):
        if hasattr(self, 'db'):
            self.db.close()
            self.engine.dispose()

    def upgrade(self):
        self.db.close()
        self.migration.upgrade_feedback(self.engine)
        self.db = Session(self.engine)

    def test_adds_only_feedback_tables_and_one_time_templates(self):
        before = set(inspect(self.engine).get_table_names())
        self.upgrade()
        self.assertEqual(set(inspect(self.engine).get_table_names()) - before,
                         {'pms_feedback_report', 'pms_feedback_followup', 'pms_feedback_attachment', 'pms_feedback_notification'})
        nodes = self.db.query(SysMenu).filter(SysMenu.permission_code.like('feedback:%')).all()
        self.assertEqual(len(nodes), 6)
        handle = next(node for node in nodes if node.permission_code == 'feedback:handle')
        admin = self.db.query(SysRole).filter_by(role_code='admin').one()
        self.assertIsNotNone(self.db.query(SysRoleMenu).filter_by(role_id=admin.id, menu_id=handle.id).first())
        operator = self.db.query(SysRole).filter_by(role_code='operator').one()
        self.assertIsNone(self.db.query(SysRoleMenu).filter_by(role_id=operator.id, menu_id=handle.id).first())
        self.db.query(SysRoleMenu).filter_by(menu_id=handle.id).delete()
        handle.status = 0
        option = self.db.query(SysDictItem).filter_by(item_label='功能异常').one()
        option.item_label = '业务部门自定义分类'
        handle_id, option_id = handle.id, option.id
        self.db.commit()
        self.upgrade()
        self.assertEqual(self.db.get(SysMenu, handle_id).status, 0)
        self.assertEqual(self.db.query(SysRoleMenu).filter_by(menu_id=handle_id).count(), 0)
        self.assertEqual(self.db.get(SysDictItem, option_id).item_label, '业务部门自定义分类')

    def test_wrong_revision_and_fake_marker_fail_closed(self):
        marker = self.db.get(PmsDatabaseRevision, 1)
        marker.revision = 'wrong'
        self.db.commit()
        with self.assertRaises(RuntimeError):
            self.migration.upgrade_feedback(self.engine)

        self.assertNotIn('pms_feedback_report', inspect(self.engine).get_table_names())
        marker.revision = self.migration.REVISION
        self.db.commit()
        with self.assertRaises(RuntimeError):
            self.migration.upgrade_feedback(self.engine)

    def test_marker_failure_rolls_back_tables_and_permissions(self):
        from sqlalchemy.exc import IntegrityError
        with self.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TRIGGER deny_revision BEFORE UPDATE ON pms_database_revision BEGIN SELECT RAISE(ABORT, 'fixture'); END")
        with self.assertRaises(IntegrityError):
            self.migration.upgrade_feedback(self.engine)
        self.assertFalse(any(name.startswith('pms_feedback_') for name in inspect(self.engine).get_table_names()))
        self.db.expire_all()
        self.assertEqual(self.db.query(SysMenu).filter(SysMenu.permission_code.like('feedback:%')).count(), 0)
        self.assertEqual(self.db.get(PmsDatabaseRevision, 1).revision, self.migration.PREVIOUS)

    def test_current_revision_requires_submission_unique_index(self):
        self.upgrade()
        with self.engine.begin() as connection:
            connection.exec_driver_sql('DROP INDEX uq_feedback_submission')
        with self.assertRaises(RuntimeError):
            self.migration.upgrade_feedback(self.engine)

    def test_initial_feedback_revision_upgrades_submission_identity_without_regrant(self):
        self.upgrade()
        with self.engine.begin() as connection:
            connection.exec_driver_sql('DROP INDEX uq_feedback_submission')
            connection.exec_driver_sql('ALTER TABLE pms_feedback_report DROP COLUMN submission_id')
            connection.exec_driver_sql("UPDATE pms_database_revision SET revision='2026-10-12-feedback-01'")
            connection.exec_driver_sql('DELETE FROM sys_role_menu')
        self.upgrade()
        self.assertEqual(self.db.get(PmsDatabaseRevision, 1).revision, self.migration.REVISION)
        self.assertEqual(self.db.query(SysRoleMenu).count(), 0)
        self.assertIn('submission_id', {column['name'] for column in inspect(self.engine).get_columns('pms_feedback_report')})


if __name__ == '__main__':
    unittest.main()
