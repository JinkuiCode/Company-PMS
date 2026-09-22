import sys
import unittest
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session
from app.core.database import Base
import app.models.init_db
from app.models.product_line import SysProductLine, SysRoleProductLine
from app.models.project import PmsProjectArchive
from app.models.rbac import SysRole
from app.models.operation_log import SysOperationLog
from app.schemas.product_line import OrganizationOption, ProductLineCreate, ProductLineUpdate
from app.services.product_line import create_product_line, update_product_line, delete_product_line
from app.services.product_line_migration import upgrade_product_lines


class ProductLines(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        @event.listens_for(self.engine, 'connect')
        def foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create(self, org=200292, name='Bench'):
        option = OrganizationOption(source_key='kingdee', organization_id=org,
                                    code=str(org), name='原组织名称', active=True)
        return create_product_line(self.db, ProductLineCreate(organization_id=org, display_name=name),
                                   organization=option, operator_id=None)

    def update(self, line, **kwargs):
        return update_product_line(self.db, line.id, ProductLineUpdate(
            expected_updated_at=line.updated_at, **kwargs), operator_id=None)

    def test_rename_does_not_change_binding_or_original_name(self):
        line = self.create()
        changed = self.update(line, display_name='半导体')
        self.assertEqual((changed.organization_id, changed.organization_name), (200292, '原组织名称'))
        self.assertEqual(changed.display_name, '半导体')
        self.assertEqual(self.db.query(SysOperationLog).count(), 2)

    def test_duplicate_organization_and_display_name_are_rejected(self):
        self.create()
        for org, name in ((200292, '另一个'), (250676, ' Bench '), (250676, 'bench')):
            with self.assertRaises(HTTPException) as caught:
                self.create(org, name)
            self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.db.query(SysProductLine).count(), 1)

    def test_organization_option_must_match_and_be_active(self):
        for option in (
            OrganizationOption(source_key='kingdee', organization_id=99, code='99', name='x', active=True),
            OrganizationOption(source_key='kingdee', organization_id=200292, code='a', name='x', active=False),
        ):
            with self.assertRaises(HTTPException):
                create_product_line(self.db, ProductLineCreate(organization_id=200292),
                                    organization=option, operator_id=None)
        self.assertEqual(self.db.query(SysProductLine).count(), 0)

    def test_empty_name_defaults_to_original(self):
        line = self.create(name=None)
        self.assertEqual(line.display_name, '原组织名称')

    def test_catalog_and_log_use_chinese_names(self):
        from app.services.field_catalog import build_field_catalog
        fields = {row['field_code']: row for row in build_field_catalog() if row['module'] == 'product_line'}
        self.assertEqual(fields['organization_name']['field_name'], '金蝶组织名称')
        self.assertEqual(fields['display_name']['field_name'], '产品线名称')
        self.assertFalse(fields['organization_id']['editable'])
        from app.services.operation_log import build_operation_log_diff_items
        items = build_operation_log_diff_items({
            'display_name': {'before': '原名', 'after': '新名'}}, db=self.db, entity_type='sys_product_line')
        self.assertEqual(items[0]['field_label'], '产品线名称')
        role_fields = {row['field_code']: row for row in build_field_catalog() if row['module'] == 'role'}
        self.assertEqual(role_fields['product_line_ids']['field_name'], '授权产品线')

    def test_archive_catalog_explains_new_binding_and_retained_legacy_value(self):
        from app.services.field_catalog import build_field_catalog
        fields = {row['field_code']: row for row in build_field_catalog() if row['module'] == 'project_archive'}
        self.assertEqual(fields['product_line_id']['storage_column'], 'business_product_line_id')
        self.assertIsNone(fields['product_line_id']['enum_code'])
        self.assertEqual(fields['legacy_product_line_id']['storage_column'], 'product_line_id')
        self.assertFalse(fields['legacy_product_line_id']['editable'])

    def test_stale_update_is_rejected_without_an_extra_log(self):
        line = self.create()
        version = line.updated_at
        self.update(line, sort=5)
        with self.assertRaises(HTTPException) as caught:
            update_product_line(self.db, line.id, ProductLineUpdate(
                expected_updated_at=version, display_name='stale'), operator_id=None)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.db.query(SysOperationLog).count(), 2)

    def test_archive_reference_blocks_delete_and_disable_preserves_it(self):
        line = self.create()
        archive = PmsProjectArchive(project_code='A', project_name='A', business_product_line_id=line.id)
        self.db.add(archive)
        self.db.commit()
        with self.assertRaises(HTTPException) as caught:
            delete_product_line(self.db, line.id, operator_id=None)
        self.assertEqual(caught.exception.status_code, 409)
        self.update(line, is_enabled=False)
        self.assertEqual(archive.business_product_line_id, line.id)

    def test_role_reference_blocks_delete(self):
        line = self.create()
        role = SysRole(role_code='test', role_name='测试')
        self.db.add(role)
        self.db.flush()
        self.db.add(SysRoleProductLine(role_id=role.id, product_line_id=line.id))
        self.db.commit()
        with self.assertRaises(HTTPException):
            delete_product_line(self.db, line.id, operator_id=None)

    def test_unreferenced_delete_has_log(self):
        line = self.create()
        delete_product_line(self.db, line.id, operator_id=None)
        self.assertEqual(self.db.query(SysProductLine).count(), 0)
        self.assertEqual(self.db.query(SysOperationLog).count(), 2)

    def test_old_enum_value_is_not_new_assignment(self):
        line = self.create()
        archive = PmsProjectArchive(project_code='OLD', project_name=None, product_line_id=line.id)
        self.db.add(archive)
        self.db.commit()
        self.assertIsNone(archive.business_product_line_id)

    def test_upgrade_is_additive_repeatable_and_preserves_old_value(self):
        other = create_engine('sqlite://')
        with other.begin() as c:
            c.execute(text('CREATE TABLE sys_role (id INTEGER PRIMARY KEY)'))
            c.execute(text('CREATE TABLE sys_user (id INTEGER PRIMARY KEY)'))
            c.execute(text('CREATE TABLE pms_project_archive (id INTEGER PRIMARY KEY, product_line_id INTEGER)'))
            c.execute(text('INSERT INTO pms_project_archive VALUES (1, 7)'))
        for _ in range(2):
            upgrade_product_lines(other)
        with other.connect() as c:
            row = c.execute(text('SELECT product_line_id,business_product_line_id FROM pms_project_archive')).one()
            self.assertEqual(tuple(row), (7, None))
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM sys_role_product_line')).scalar_one(), 0)
        self.assertTrue(inspect(other).get_foreign_keys('pms_project_archive'))
        other.dispose()

    def test_menu_migration_never_replenishes_revoked_permissions_or_line_grants(self):
        from app.services.product_line_migration import initialize_product_line_management
        from app.models.rbac import SysMenu, SysRoleMenu
        role = SysRole(role_code='admin', role_name='管理员')
        self.db.add_all([role, SysMenu(menu_name='系统管理', menu_type='M', parent_id=0)])
        self.db.commit()
        initialize_product_line_management(self.db)
        menus = self.db.query(SysMenu).filter(SysMenu.permission_code.like('system:product-line:%')).all()
        self.assertEqual(len(menus), 6)
        self.assertEqual(self.db.query(SysRoleMenu).filter_by(role_id=role.id).count(), 6)
        self.db.query(SysRoleMenu).filter_by(role_id=role.id).delete()
        self.db.commit()
        initialize_product_line_management(self.db)
        self.assertEqual(self.db.query(SysRoleMenu).filter_by(role_id=role.id).count(), 0)
        self.assertEqual(self.db.query(SysRoleProductLine).count(), 0)


if __name__ == '__main__':
    unittest.main()
