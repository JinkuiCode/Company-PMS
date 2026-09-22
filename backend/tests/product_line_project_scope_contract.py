"""Business queries must intersect person/department and explicit line grants."""
import sys
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
import app.models.init_db
from app.models.project import PmsProjectArchive, PmsProject, PmsTask
from app.models.product_line import SysProductLine
from app.models.user import SysUser
from app.services import project
from app.schemas.project import ArchiveCreate, ArchiveUpdate
from app.schemas.product_line import OrganizationOption


class ProjectScope(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.users = [SysUser(username=str(n), real_name=str(n), password_hash='test', dept_id=n) for n in (1, 2)]
        self.lines = [SysProductLine(source_key='kingdee', organization_id=n, organization_code=str(n),
                      organization_name=str(n), display_name=str(n), name_key=str(n)) for n in (100, 200)]
        self.db.add_all([*self.users, *self.lines])
        self.db.flush()
        self.archives = [PmsProjectArchive(project_code=f'A{n}', project_name=f'A{n}', manager_id=self.users[n % 2].id,
                        product_line_id=self.lines[0].id, business_product_line_id=line_id, created_at=datetime(2020, 1, 1))
                         for n, line_id in enumerate((self.lines[0].id, self.lines[1].id, None))]
        self.db.add_all(self.archives)
        self.db.flush()
        self.projects = [PmsProject(project_code=f'A{n}', project_name=f'A{n}', archive_id=archive.id,
                         pm_id=self.users[0].id, dept_id=1) for n, archive in enumerate(self.archives)]
        self.projects.append(PmsProject(project_code='ORPHAN', project_name='ORPHAN', pm_id=self.users[0].id, dept_id=1))
        self.db.add_all(self.projects)
        self.db.flush()
        self.tasks = [PmsTask(project_id=p.id, task_name='test') for p in self.projects]
        self.db.add_all(self.tasks)
        self.db.commit()
        self.ctx = dict(user_id=self.users[0].id, dept_id=1, data_scope=4, product_category_ids=None,
                        product_line_ids=[self.lines[0].id])

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_archive_list_count_options_and_public_field_use_new_binding(self):
        result = project.get_archive_list(self.db, scope_context=self.ctx)
        self.assertEqual(result['total'], 1)
        self.assertEqual([row.id for row in result['items']], [self.archives[0].id])
        self.assertEqual(result['items'][0].product_line_id, self.lines[0].id)
        self.assertEqual([row.id for row in project.get_archive_options(self.db, self.ctx)], [self.archives[0].id])

    def test_detail_and_task_paths_hide_other_lines_and_unassigned_records(self):
        for archive in self.archives[1:]:
            with self.assertRaises(HTTPException) as caught:
                project.ensure_archive_access(self.db, archive.id, self.ctx)
            self.assertEqual(caught.exception.status_code, 404)
        for item in self.projects[1:]:
            with self.assertRaises(HTTPException):
                project.ensure_project_access(self.db, item.id, self.ctx)
            with self.assertRaises(HTTPException):
                project.get_tasks(self.db, item.id, scope_context=self.ctx)

    def test_empty_grants_and_missing_key_are_not_unrestricted(self):
        for ctx in ({}, {**self.ctx, 'product_line_ids': []}, {k: v for k, v in self.ctx.items() if k != 'product_line_ids'}):
            self.assertEqual(project.get_archive_list(self.db, scope_context=ctx)['total'], 0)
            self.assertEqual(project._apply_project_scope(self.db.query(PmsProject), self.db, ctx).count(), 0)

    def test_product_line_cannot_be_hidden_or_made_optional_by_field_rules(self):
        from app.services.field_policy import get_effective_field_policies, MODULE_PROJECT_ARCHIVE
        field = next(item for item in get_effective_field_policies(self.db, MODULE_PROJECT_ARCHIVE)['items']
                     if item['field_key'] == 'product_line_id')
        for key in ('visible', 'editable', 'required', 'visible_locked', 'editable_locked', 'required_locked'):
            self.assertTrue(field[key], key)
        self.assertIsNone(field['enum_code'])

    def test_department_and_line_are_intersected(self):
        ctx = {**self.ctx, 'data_scope': 2, 'dept_id': 2}
        self.assertEqual(project.get_archive_list(self.db, scope_context=ctx)['total'], 0)

    def test_disabled_line_keeps_authorized_history(self):
        self.lines[0].is_enabled = 0
        self.db.commit()
        self.assertEqual(project.get_archive_list(self.db, scope_context=self.ctx)['total'], 1)

    def test_filters_and_public_value_do_not_read_legacy_enum_ids(self):
        ctx = {**self.ctx, 'product_line_ids': [self.lines[1].id]}
        result = project.get_archive_list(self.db, scope_context=ctx, filters=[
            {'field': 'product_line_id', 'operator': 'equals', 'value': self.lines[1].id}])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0].product_line_id, self.lines[1].id)

    def test_create_requires_authorized_line_and_stores_no_legacy_enum_value(self):
        option = OrganizationOption(source_key='kingdee', organization_id=100, code='100', name='100', active=True)
        with patch('app.services.product_line_source.get_organization', return_value=option):
            created = project.create_archive(self.db, ArchiveCreate(project_code='NEW', project_name='新档案',
                        product_line_id=self.lines[0].id), self.users[0].id, scope_context=self.ctx)
        row = self.db.get(PmsProjectArchive, created['id'])
        self.assertEqual(row.business_product_line_id, self.lines[0].id)
        self.assertIsNone(row.product_line_id)
        for line_id in (None, self.lines[1].id):
            with self.assertRaises(HTTPException) as caught:
                project.create_archive(self.db, ArchiveCreate(project_code='DENIED', project_name='拒绝',
                            product_line_id=line_id), self.users[0].id, scope_context=self.ctx)
            self.assertIn(caught.exception.status_code, (404, 422))

    def test_line_disabled_during_source_lookup_blocks_create(self):
        def disable(*args):
            with Session(self.engine) as other:
                other.query(SysProductLine).filter_by(id=self.lines[0].id).update({'is_enabled': 0})
                other.commit()
            return OrganizationOption(organization_id=100, code='100', name='100', active=True)
        with patch('app.services.product_line_source.get_organization', side_effect=disable):
            with self.assertRaises(HTTPException) as caught:
                project.create_archive(self.db, ArchiveCreate(project_code='RACE', project_name='拒绝',
                    product_line_id=self.lines[0].id), self.users[0].id, scope_context=self.ctx)
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(self.db.query(PmsProjectArchive).filter_by(project_code='RACE').count(), 0)

    def test_change_checks_both_lines_and_does_not_overwrite_legacy_value(self):
        with self.assertRaises(HTTPException) as caught:
            project.update_archive(self.db, self.archives[0].id, ArchiveUpdate(product_line_id=self.lines[1].id),
                                   self.users[0].id, scope_context=self.ctx)
        self.assertEqual(caught.exception.status_code, 404)
        self.db.refresh(self.archives[0])
        self.assertEqual(self.archives[0].business_product_line_id, self.lines[0].id)
        option = OrganizationOption(source_key='kingdee', organization_id=200, code='200', name='200', active=True)
        with patch('app.services.product_line_source.get_organization', return_value=option):
            project.update_archive(self.db, self.archives[0].id, ArchiveUpdate(product_line_id=self.lines[1].id),
                self.users[0].id, scope_context={**self.ctx, 'product_line_ids': [r.id for r in self.lines]})
        self.assertEqual(self.archives[0].business_product_line_id, self.lines[1].id)
        self.assertEqual(self.archives[0].product_line_id, self.lines[0].id)

    def test_synchronized_archive_cannot_change_organization(self):
        self.archives[0].erp_synced = 1
        self.db.commit()
        with self.assertRaises(HTTPException) as caught:
            project.update_archive(self.db, self.archives[0].id, ArchiveUpdate(product_line_id=self.lines[1].id),
                self.users[0].id, scope_context={**self.ctx, 'product_line_ids': [r.id for r in self.lines]})
        self.assertEqual(caught.exception.status_code, 409)

    def test_disabled_line_allows_other_edits_but_not_selecting_a_new_line(self):
        self.lines[0].is_enabled = 0
        self.db.commit()
        project.update_archive(self.db, self.archives[0].id, ArchiveUpdate(customer='新客户'),
                               self.users[0].id, scope_context=self.ctx)
        self.assertEqual(self.archives[0].customer, '新客户')
        with self.assertRaises(HTTPException):
            project.create_archive(self.db, ArchiveCreate(project_code='DISABLED', project_name='拒绝',
                        product_line_id=self.lines[0].id), self.users[0].id, scope_context=self.ctx)

    def test_no_legacy_category_authorization_remains_for_other_field_edits(self):
        project.update_archive(self.db, self.archives[0].id, ArchiveUpdate(customer='可修改'),
            self.users[0].id, scope_context={**self.ctx, 'product_category_ids': []})
        self.assertEqual(self.archives[0].customer, '可修改')

    def test_business_validation_uses_organization_binding_not_legacy_enum(self):
        row = self.archives[0]
        row.product_line_id = None
        row.created_at = datetime.now()
        self.db.commit()
        project.validate_archive_for_business_operation(self.db, row)
        row.business_product_line_id = None
        row.product_line_id = self.lines[0].id
        self.db.commit()
        with self.assertRaises(HTTPException):
            project.validate_archive_for_business_operation(self.db, row)


if __name__ == '__main__':
    unittest.main()
