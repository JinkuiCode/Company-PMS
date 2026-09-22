"""Historical mappings are explicit, fingerprinted, atomic and never reapplied."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.database import Base
import app.models.init_db
from app.models.database_revision import PmsDatabaseRevision
from app.models.product_line import SysProductLine, SysRoleProductLine
from app.models.project import PmsProjectArchive
from app.models.rbac import SysRole, SysUserRole, SysMenu, SysRoleMenu
from app.models.user import SysUser
from app.models.operation_log import SysOperationLog
from app.services.database_revision import CURRENT_DATABASE_REVISION
from app.services.product_line_assignments import snapshot, inspect_plan, apply_plan


class AssignmentMigration(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.actor = SysUser(username='migration', password_hash='x', real_name='迁移管理员')
        self.role = SysRole(role_code='migration', role_name='迁移管理员', data_scope=4)
        self.line = SysProductLine(source_key='kingdee', organization_id=100, organization_code='100',
            organization_name='组织甲', display_name='产品线甲', name_key='甲')
        self.archive = PmsProjectArchive(project_code='A', project_name='历史档案', product_line_id=1)
        menu = SysMenu(menu_name='迁移', menu_type='B', permission_code='system:product-line:migrate')
        self.db.add_all([self.actor, self.role, self.line, self.archive, menu,
                         PmsDatabaseRevision(id=1, revision=CURRENT_DATABASE_REVISION)])
        self.db.flush()
        self.db.add_all([SysUserRole(user_id=self.actor.id, role_id=self.role.id),
                         SysRoleMenu(role_id=self.role.id, menu_id=menu.id)])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def plan(self):
        state = snapshot(self.db)
        return dict(source_revision=state['source_revision'], source_fingerprint=state['source_fingerprint'],
            lines=[dict(key='kingdee:100', product_line_id=self.line.id, organization_id=100)],
            archives=[dict(archive_id=self.archive.id, project_code='A', legacy_product_line_id=1,
                           target_product_line_key='kingdee:100')],
            roles=[dict(role_id=self.role.id, product_line_keys=['kingdee:100'])])

    def test_snapshot_is_readonly_and_never_matches_equal_legacy_ids(self):
        report = snapshot(self.db)
        self.assertEqual(report['archives'][0]['legacy_product_line_id'], self.line.id)
        self.assertIsNone(report['archives'][0]['business_product_line_id'])
        self.assertEqual(len(report['issues']['未归属档案']), 1)
        self.assertEqual(self.db.query(SysOperationLog).count(), 0)

    def test_dry_run_does_not_write_and_apply_is_audited(self):
        plan = self.plan()
        self.assertTrue(inspect_plan(self.db, plan)['ready'])
        self.assertIsNone(self.archive.business_product_line_id)
        result = apply_plan(self.db, plan, operator_id=self.actor.id)
        self.assertEqual(result['status'], 'applied')
        self.db.refresh(self.archive)
        self.assertEqual(self.archive.business_product_line_id, self.line.id)
        self.assertEqual(self.archive.product_line_id, 1)
        self.assertEqual(self.db.query(SysRoleProductLine).one().product_line_id, self.line.id)
        self.assertEqual(self.db.query(SysOperationLog).count(), 1)

    def test_stale_snapshot_blocks_all_writes(self):
        plan = self.plan()
        self.archive.project_code = 'CHANGED'
        self.db.commit()
        with self.assertRaises(HTTPException):
            apply_plan(self.db, plan, operator_id=self.actor.id)
        self.assertIsNone(self.db.get(PmsProjectArchive, self.archive.id).business_product_line_id)
        self.assertEqual(self.db.query(SysRoleProductLine).count(), 0)

    def test_legacy_role_scope_changes_invalidate_confirmed_snapshot(self):
        self.role.product_category_ids = '1'
        self.db.commit()
        plan = self.plan()
        self.role.product_category_ids = '2'
        self.db.commit()
        self.assertFalse(inspect_plan(self.db, plan)['ready'])
        self.assertEqual(snapshot(self.db)['roles'][0]['product_category_ids'], '2')

    def test_invalid_references_and_duplicate_entries_are_grouped(self):
        for section, entry in [('lines', lambda p: p['lines'][0]), ('archives', lambda p: p['archives'][0]),
                               ('roles', lambda p: dict(role_id=999, product_line_keys=['missing']))]:
            plan = self.plan()
            plan[section].append(entry(plan))
            self.assertFalse(inspect_plan(self.db, plan)['ready'])
            with self.assertRaises(HTTPException):
                apply_plan(self.db, plan, operator_id=self.actor.id)
            self.assertEqual(self.db.query(SysOperationLog).count(), 0)

    def test_empty_role_selection_is_explicit_no_access(self):
        plan = self.plan()
        plan['roles'][0]['product_line_keys'] = []
        apply_plan(self.db, plan, operator_id=self.actor.id)
        self.assertEqual(self.db.query(SysRoleProductLine).count(), 0)

    def test_prepared_archive_plan_preserves_page_configured_role_grants(self):
        from app.services.product_line_assignments import prepare_archive_plan
        self.db.add(SysRoleProductLine(role_id=self.role.id, product_line_id=self.line.id))
        self.db.add(PmsProjectArchive(project_code='UNKNOWN', project_name='', product_line_id=99))
        self.db.commit()
        result = prepare_archive_plan(self.db, [{'legacy_product_line_id': 1, 'organization_id': 100}])
        self.assertTrue(result['ready'])
        self.assertEqual(result['plan']['roles'], [])
        self.assertEqual(len(result['plan']['archives']), 1)
        self.assertEqual(result['unmatched_archives'][0]['project_code'], 'UNKNOWN')
        self.assertEqual(self.db.query(SysOperationLog).count(), 0)
        self.assertIsNone(self.archive.business_product_line_id)
        grant_id = self.db.query(SysRoleProductLine).one().id
        apply_plan(self.db, result['plan'], operator_id=self.actor.id)
        self.assertEqual(self.db.query(SysRoleProductLine).one().id, grant_id)

    def test_prepare_requires_existing_enabled_target_and_unique_source(self):
        from app.services.product_line_assignments import prepare_archive_plan
        for mapping in ([{'legacy_product_line_id': 1, 'organization_id': 999}],
                        [{'legacy_product_line_id': 1, 'organization_id': 100}] * 2):
            with self.assertRaises(HTTPException):
                prepare_archive_plan(self.db, mapping)
        self.line.is_enabled = 0
        self.db.commit()
        with self.assertRaises(HTTPException):
            prepare_archive_plan(self.db, [{'legacy_product_line_id': 1, 'organization_id': 100}])

    def test_prepare_does_not_overwrite_existing_assignment_or_infer_null(self):
        from app.services.product_line_assignments import prepare_archive_plan
        self.archive.business_product_line_id = self.line.id
        self.db.add(PmsProjectArchive(project_code='NO-LINE', project_name='', product_line_id=None))
        self.db.commit()
        result = prepare_archive_plan(self.db, [{'legacy_product_line_id': 1, 'organization_id': 100}])
        self.assertFalse(result['ready'])
        self.assertEqual(result['plan']['archives'], [])
        self.assertEqual(len(result['unmatched_archives']), 1)

    def test_cli_prepare_exports_separate_plan_without_database_writes(self):
        import json
        import tempfile
        from contextlib import nullcontext
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location('prepare_cli', Path(__file__).resolve().parents[1] / 'scripts/migrate_product_line_assignments.py')
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mapping = root / 'mapping.json'
            mapping.write_text(json.dumps([{'legacy_product_line_id': 1, 'organization_id': 100}]))
            with patch.object(module, 'ROOT', root), patch.object(sys, 'argv', ['migration', '--prepare-mapping', str(mapping)]), patch('app.core.database.SessionLocal', return_value=nullcontext(self.db)):
                self.assertEqual(module.main(), 0)
            plan_files = list((root / '.runtime/product-line-migration').glob('*.plan.json'))
            self.assertEqual(len(plan_files), 1)
            plan = json.loads(plan_files[0].read_text())
            self.assertEqual(plan['roles'], [])
            self.assertTrue(inspect_plan(self.db, plan)['ready'])
            self.assertIsNone(self.archive.business_product_line_id)
            self.assertEqual(self.db.query(SysOperationLog).count(), 0)

    def test_repeat_does_not_restore_later_revocation(self):
        plan = self.plan()
        apply_plan(self.db, plan, operator_id=self.actor.id)
        self.db.query(SysRoleProductLine).delete()
        self.db.commit()
        result = apply_plan(self.db, plan, operator_id=self.actor.id)
        self.assertEqual(result['status'], 'already_applied')
        self.assertEqual(self.db.query(SysRoleProductLine).count(), 0)
        self.assertEqual(self.db.query(SysOperationLog).count(), 1)

    def test_late_failure_rolls_back_archive_role_and_log(self):
        plan = self.plan()
        with patch('app.services.product_line_assignments.record_operation_log', side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):
                apply_plan(self.db, plan, operator_id=self.actor.id)
        self.assertIsNone(self.db.get(PmsProjectArchive, self.archive.id).business_product_line_id)
        self.assertEqual(self.db.query(SysRoleProductLine).count(), 0)
        self.assertEqual(self.db.query(SysOperationLog).count(), 0)

    def test_no_admin_bypass(self):
        plan = self.plan()
        self.db.query(SysRoleMenu).delete()
        self.db.commit()
        with self.assertRaises(HTTPException) as caught:
            apply_plan(self.db, plan, operator_id=self.actor.id)
        self.assertEqual(caught.exception.status_code, 403)

    def test_existing_assignment_cannot_be_overwritten(self):
        self.archive.business_product_line_id = self.line.id
        self.db.commit()
        result = inspect_plan(self.db, self.plan())
        self.assertFalse(result['ready'])
        self.assertTrue(any('已有组织归属' in item for item in result['errors']))

    def test_duplicate_codes_and_organization_mismatch_block_apply(self):
        plan = self.plan()
        plan['lines'][0]['organization_id'] = 200
        self.assertFalse(inspect_plan(self.db, plan)['ready'])
        plan = self.plan()
        plan['archives'].append({**plan['archives'][0], 'archive_id': 999, 'project_code': 'a'})
        self.assertIn('项目编码重复', inspect_plan(self.db, plan)['errors'])

    def test_preupgrade_readonly_snapshot_and_chinese_report(self):
        from sqlalchemy import text
        from importlib.util import spec_from_file_location, module_from_spec
        old_engine = create_engine('sqlite://')
        try:
            with old_engine.begin() as connection:
                connection.execute(text('CREATE TABLE pms_project_archive (id INTEGER PRIMARY KEY, project_code TEXT, project_name TEXT, product_line_id INT)'))
                connection.execute(text("INSERT INTO pms_project_archive VALUES (1, 'OLD', '历史', 1)"))
            with Session(old_engine) as db:
                state = snapshot(db)
            self.assertIsNone(state['archives'][0]['business_product_line_id'])
            self.assertEqual(state['lines'], [])
            spec = spec_from_file_location('assignment_cli', Path(__file__).resolve().parents[1] / 'scripts/migrate_product_line_assignments.py')
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            report = module.markdown_report(state)
            self.assertIn('| 档案编号 | 项目编码 | 项目名称 | 历史产品线枚举值 |', report)
            self.assertIn('未归属档案（1 条）', report)
        finally:
            old_engine.dispose()


if __name__ == '__main__':
    unittest.main()
