"""Archive expansion: independent line, dated requirements and atomic saves."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.database import Base
import app.models.init_db
from app.models.project import PmsProjectArchive
from app.models.user import SysUser
from app.models.dict import SysDict, SysDictItem
from app.models.erp_task import ErpSyncTask
from app.models.field_policy import SysBusinessFieldPolicy
from app.schemas.project import ArchiveCreate, ArchiveUpdate, ArchiveResponse
from app.services import project
from app.services.enum_registry import initialize_enum_definitions, count_enum_references

FIELDS = {'product_line_id', 'contract_signed_date', 'contract_ship_date',
          'actual_ship_date', 'warranty_end_date', 'address_province', 'address_city',
          'address_detail', 'project_contact', 'contact_phone'}
DATES = dict(contract_signed_date='2026-09-20', contract_ship_date='2026-12-01')


class ArchiveBusinessFields(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        initialize_enum_definitions(self.db)
        self.user = SysUser(username='fields-test', real_name='测试人', password_hash='x', status=1)
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def upgrade(self):
        from app.services.archive_business_migration import upgrade_archive_business_fields
        upgrade_archive_business_fields(self.engine)

    def create(self, **kwargs):
        return project.create_archive(self.db, ArchiveCreate(
            project_code=kwargs.pop('project_code', 'NEW'), project_name='测试', **kwargs), self.user.id)['id']

    def test_model_schema_contract(self):
        self.assertTrue(FIELDS <= set(PmsProjectArchive.__table__.columns.keys()))
        for schema in (ArchiveCreate, ArchiveUpdate, ArchiveResponse):
            self.assertTrue(FIELDS <= set(schema.model_fields))

    def test_local_changes_preserve_sync_tasks_and_failures(self):
        archive_id = self.create()
        archive = self.db.get(PmsProjectArchive, archive_id)
        task = self.db.query(ErpSyncTask).one()
        for status in ('queued', 'failed'):
            task.status = status
            archive.erp_sync_status = status
            archive.erp_error_msg = '保留原失败原因' if status == 'failed' else None
            self.db.commit()
            result = project.update_archive(self.db, archive_id, ArchiveUpdate(
                customer=status, project_code=' NEW ', project_name=' 测试 '), self.user.id)
            self.assertEqual(self.db.query(ErpSyncTask).count(), 1)
            self.assertFalse(result.get('sync_queued', True))
            self.db.refresh(task)
            self.db.refresh(archive)
            self.assertEqual(task.status, status)
            self.assertEqual(archive.erp_sync_status, status)
            self.assertEqual(archive.erp_error_msg, '保留原失败原因' if status == 'failed' else None)

    def test_only_changed_mapping_fields_enqueue_after_create(self):
        archive_id = self.create()
        self.assertEqual(self.db.query(ErpSyncTask).count(), 1)
        for fields in ({'project_name': '修改名称'}, {'project_code': 'NEW-2'}):
            count = self.db.query(ErpSyncTask).count()
            result = project.update_archive(self.db, archive_id, ArchiveUpdate(**fields), self.user.id)
            self.assertTrue(result.get('sync_queued', False))
            self.assertEqual(self.db.query(ErpSyncTask).count(), count + 1)

    def test_required_dates_new_records_only_and_reset_preserves_cutoff(self):
        old = PmsProjectArchive(project_code='OLD', project_name='历史', created_at=datetime.now()-timedelta(days=1))
        self.db.add(old)
        self.db.commit()
        self.upgrade()
        with self.assertRaises(HTTPException) as caught:
            self.create()
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual({x['field_key'] for x in caught.exception.detail['fields']}, set(DATES))
        self.assertEqual(self.db.query(ErpSyncTask).count(), 0)
        project.update_archive(self.db, old.id, ArchiveUpdate(customer='历史允许维护'), self.user.id)
        created = self.create(**DATES)
        with self.assertRaises(HTTPException):
            project.update_archive(self.db, created, ArchiveUpdate(contract_ship_date=None), self.user.id)
        self.db.expire_all()
        self.assertIsNotNone(self.db.get(PmsProjectArchive, created).contract_ship_date)
        from app.services.field_policy import reset_field_policies
        cutoff = self.db.query(SysBusinessFieldPolicy).filter_by(field_key='contract_ship_date').one().required_effective_at
        reset_field_policies(self.db, 'project_archive', operator_id=self.user.id)
        self.assertEqual(self.db.query(SysBusinessFieldPolicy).filter_by(field_key='contract_ship_date').one().required_effective_at, cutoff)
        project.update_archive(self.db, old.id, ArchiveUpdate(customer='再次维护'), self.user.id)

    def test_roundtrip_default_manager_line_and_audit(self):
        self.upgrade()
        archive_id = self.create(**DATES, product_line_id=2, product_category=1,
            address_province='32', address_city='3205', address_detail='详细地址1号',
            project_contact='张三', contact_phone='+86 013800000000', warranty_end_date='2028-12-01')
        archive = self.db.get(PmsProjectArchive, archive_id)
        self.assertEqual(archive.manager_id, self.user.id)
        self.assertEqual(archive.product_line_id, 2)
        self.assertEqual(archive.product_category, 1)
        self.assertEqual(count_enum_references(self.db, 'product_line', '2'), 1)
        item = project.get_archive_list(self.db)['items'][0]
        self.assertEqual(item.contact_phone, '+86 013800000000')
        self.assertEqual(item.warranty_end_date.isoformat(), '2028-12-01')
        project.update_archive(self.db, archive_id, ArchiveUpdate(manager_id=None), self.user.id)
        project.update_archive(self.db, archive_id, ArchiveUpdate(project_contact='李四'), self.user.id)
        self.db.refresh(archive)
        self.assertIsNone(archive.manager_id)
        from app.models.operation_log import SysOperationLog
        logs = self.db.query(SysOperationLog).filter_by(entity_id=str(archive_id)).all()
        self.assertTrue(any('project_contact' in str(log.diff_data) for log in logs))

    def test_invalid_address_and_enum_reject_without_partial_write(self):
        self.upgrade()
        for fields in ({'address_province': '32'}, {'address_province': '32', 'address_city': '1101', 'address_detail': 'x'}, {'product_line_id': 9999}):
            with self.assertRaises(HTTPException):
                self.create(**DATES, **fields)
        self.assertEqual(self.db.query(PmsProjectArchive).count(), 0)
        archive_id = self.create(**DATES)
        with self.assertRaises(HTTPException):
            project.update_archive(self.db, archive_id, ArchiveUpdate(customer='不可部分保存', address_detail='不完整'), self.user.id)
        self.db.expire_all()
        self.assertIsNone(self.db.get(PmsProjectArchive, archive_id).customer)

    def test_upgrade_repeat_does_not_consume_new_line_as_old_category(self):
        self.upgrade()
        initialize_enum_definitions(self.db)
        archive_id = self.create(**DATES, product_line_id=2, product_category=4)
        definition = self.db.query(SysDict).filter_by(dict_code='product_line').one()
        value = self.db.query(SysDictItem).filter_by(dict_id=definition.id, item_value='2').one()
        value.item_label = '保留自定义产品线'
        self.db.commit()
        from app.services.project_archive_semantic_migration import upgrade_project_archive_semantics
        upgrade_project_archive_semantics(self.engine)
        self.upgrade()
        initialize_enum_definitions(self.db)
        self.db.expire_all()
        self.assertEqual(self.db.get(PmsProjectArchive, archive_id).product_category, 4)
        self.assertEqual(self.db.get(SysDictItem, value.id).item_label, '保留自定义产品线')

    def test_upgrade_old_table_and_metadata(self):
        engine = create_engine('sqlite://')
        try:
            SysBusinessFieldPolicy.__table__.create(engine)
            with engine.begin() as connection:
                connection.execute(text('CREATE TABLE pms_project_archive (id INT, project_code NVARCHAR(32))'))
                connection.execute(text("INSERT INTO pms_project_archive VALUES (1, 'HISTORY')"))
            from app.services.archive_business_migration import upgrade_archive_business_fields
            for _ in range(2):
                upgrade_archive_business_fields(engine)
            self.assertTrue(FIELDS <= {column['name'] for column in inspect(engine).get_columns('pms_project_archive')})
            with engine.connect() as connection:
                self.assertIsNone(connection.execute(text('SELECT contract_signed_date FROM pms_project_archive')).scalar())
                self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM sys_business_field_policy')).scalar(), 2)
        finally:
            engine.dispose()
        from app.services.field_catalog import build_field_catalog
        fields = {item['field_code']: item for item in build_field_catalog() if item['module'] == 'project_archive'}
        self.assertTrue(FIELDS <= set(fields))
        self.assertEqual(fields['product_line_id']['enum_code'], 'product_line')
        self.assertEqual(fields['product_line_id']['field_name'], '产品线')
        self.assertEqual(fields['contract_ship_date']['group'], '合同与交付')
        self.assertEqual(fields['contract_ship_date']['field_name'], '合同出货日期')
        from app.services.list_query import archive_columns
        self.assertTrue(FIELDS <= set(archive_columns()))

    def test_disabled_line_retains_history_and_references_protect_deletion(self):
        self.upgrade()
        archive_id = self.create(**DATES, product_line_id=2)
        definition = self.db.query(SysDict).filter_by(dict_code='product_line').one()
        item = self.db.query(SysDictItem).filter_by(dict_id=definition.id, item_value='2').one()
        from app.services.dict import delete_dict_item, update_dict_item
        from app.schemas.dict import DictItemUpdate
        with self.assertRaises(HTTPException) as caught:
            delete_dict_item(self.db, item.id)
        self.assertEqual(caught.exception.status_code, 409)
        update_dict_item(self.db, item.id, DictItemUpdate(status=0), operator_id=self.user.id)
        with self.assertRaises(HTTPException):
            self.create(project_code='DISABLED', **DATES, product_line_id=2)
        project.update_archive(self.db, archive_id, ArchiveUpdate(product_line_id=2, customer='历史继续维护'), self.user.id)
        self.assertEqual(self.db.get(PmsProjectArchive, archive_id).product_line_id, 2)

    def test_new_field_filters_and_pagination(self):
        self.upgrade()
        self.create(project_code='LINE-1', **DATES, product_line_id=1)
        second = self.create(project_code='LINE-2', **DATES, product_line_id=2)
        result = project.get_archive_list(self.db, page_size=1, filters=[
            {'field': 'product_line_id', 'operator': 'equals', 'value': 2},
            {'field': 'contract_ship_date', 'operator': 'equals', 'value': '2026-12-01'},
        ])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0].id, second)

    def test_unchanged_readonly_dates_allow_other_updates(self):
        self.upgrade()
        archive_id = self.create(**DATES, actual_ship_date='2026-12-02', warranty_end_date='2027-12-02')
        for key in ('actual_ship_date', 'warranty_end_date'):
            self.db.add(SysBusinessFieldPolicy(module_code='project_archive', field_key=key,
                visible=True, editable=False, required=False, list_available=True))
        self.db.commit()
        project.update_archive(self.db, archive_id, ArchiveUpdate(customer='只修改客户',
            actual_ship_date='2026-12-02', warranty_end_date='2027-12-02'), self.user.id)
        self.assertEqual(self.db.get(PmsProjectArchive, archive_id).customer, '只修改客户')
        with self.assertRaises(HTTPException):
            project.update_archive(self.db, archive_id, ArchiveUpdate(actual_ship_date='2026-12-03'), self.user.id)


if __name__ == '__main__':
    unittest.main()
