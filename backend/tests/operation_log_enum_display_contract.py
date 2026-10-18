"""Enum display regressions using an isolated in-memory database only."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_TEMP = tempfile.TemporaryDirectory()
os.environ['PMS_CONFIG_FILE'] = '/dev/null'
os.environ['DB_DIALECT'] = 'sqlite'
os.environ['SQLITE_DB_PATH'] = str(Path(_TEMP.name) / 'unused.db')
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
import app.models.init_db
from app.models.dict import SysDict, SysDictItem
from app.models.operation_log import SysOperationLog
from app.services.operation_log import record_operation_log, get_operation_logs, build_operation_log_diff_items
from app.services.document_history import _project_items


class EnumLogDisplay(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.machine = self.option('archive_machine_model', '9001', '历史机型', enabled=False)
        self.option('archive_machine_model', '9002', '新机型')
        self.option('feedback_issue_category', '1', '功能异常')
        self.option('feedback_request_category', '1', '新增功能')

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def option(self, code, value, label, enabled=True):
        definition = self.db.query(SysDict).filter_by(dict_code=code).first()
        if definition is None:
            definition = SysDict(dict_code=code, dict_name=code)
            self.db.add(definition)
            self.db.flush()
        item = SysDictItem(dict_id=definition.id, item_value=value, item_label=label, status=int(enabled))
        self.db.add(item)
        self.db.flush()
        return item

    def log(self, before=None, after=None, **kwargs):
        row = record_operation_log(self.db, module='隔离测试', action='update',
            entity_type=kwargs.pop('entity_type', 'pms_project_archive'), entity_id='1',
            before_data=before or {}, after_data=after or {}, **kwargs)
        self.db.commit()
        return row

    def views(self, row, allowed=None):
        audit = next(item for item in get_operation_logs(self.db)['items'] if item['id'] == row.id)['diff_items']
        document = _project_items(self.db, row, allowed or {'machine_model'})
        return audit, document

    def test_legacy_logs_read_disabled_database_enum_in_both_views_without_rewriting(self):
        row = self.log({'machine_model': 9001}, {'machine_model': 9002})
        row.diff_items_data = None
        self.db.commit()
        raw = (row.before_data, row.after_data, row.diff_data, row.diff_items_data)
        for items in self.views(row):
            self.assertEqual(items[0]['before_display'], '历史机型')
            self.assertEqual(items[0]['after_display'], '新机型')
        self.db.expire(row)
        self.assertEqual((row.before_data, row.after_data, row.diff_data, row.diff_items_data), raw)

    def test_numeric_saved_snapshot_is_repaired_but_chinese_event_label_is_preserved(self):
        row = self.log({'machine_model': 9001}, {'machine_model': 9002})
        snapshot = json.loads(row.diff_items_data)
        snapshot[0].update(before_display='操作时旧名称', after_display='9002')
        row.diff_items_data = json.dumps(snapshot, ensure_ascii=False)
        self.machine.item_label = '后来改名'
        self.db.commit()
        for items in self.views(row):
            self.assertEqual(items[0]['before_display'], '操作时旧名称')
            self.assertEqual(items[0]['after_display'], '新机型')
        self.assertEqual(json.loads(row.diff_items_data)[0]['after_display'], '9002')

    def test_new_log_stores_chinese_snapshot_and_keeps_it_after_enum_rename(self):
        row = self.log({'machine_model': None}, {'machine_model': 9001})
        self.assertEqual(json.loads(row.diff_items_data)[0]['after_display'], '历史机型')
        self.machine.item_label = '后来改名'
        self.db.commit()
        for items in self.views(row):
            self.assertEqual(items[0]['after_display'], '历史机型')

    def test_unknown_enum_is_explicit_and_ordinary_numbers_stay_numbers(self):
        row = self.log(after={'machine_model': 9999, 'quantity': 9999})
        for items in self.views(row, {'machine_model', 'quantity'}):
            by_key = {item['field_key']: item for item in items}
            self.assertEqual(by_key['machine_model']['after_display'], '未识别选项（编码：9999）')
            self.assertEqual(by_key['quantity']['after_display'], '9999')
            self.assertEqual(by_key['machine_model']['before_display'], '-')

    def test_multi_select_lists_and_legacy_comma_values_are_mapped_per_item(self):
        for value in ([1, 2], '1,2'):
            with self.subTest(value=value):
                item = build_operation_log_diff_items({'product_category_ids': {'before': [], 'after': value}},
                    entity_type='sys_role', db=self.db)[0]
                self.assertEqual(item['before_display'], '-')
                self.assertEqual(item['after_display'], 'Bench、光伏')

    def test_system_enum_codes_are_displayed_without_changing_permission_semantics(self):
        cases = [('sys_role', 'data_scope', 4, '全部'),
                 ('pms_project_archive', 'is_enabled', 0, '禁用'),
                 ('pms_project_archive', 'erp_sync_status', 'success', '同步成功')]
        for entity, field, value, label in cases:
            with self.subTest(field=field):
                item = build_operation_log_diff_items({field: {'before': None, 'after': value}},
                    entity_type=entity, db=self.db)[0]
                self.assertEqual(item['after_display'], label)

    def test_current_sync_protocol_states_and_policies_have_business_labels(self):
        statuses = {'queued': '等待同步', 'running': '同步中', 'pending': '同步中',
                    'review': '待核查', 'historical': '金蝶历史档案', 'superseded': '已被新版本替代'}
        for value, label in statuses.items():
            with self.subTest(value=value):
                row = self.log(after={'erp_sync_status': value})
                for items in self.views(row, {'erp_sync_status'}):
                    self.assertEqual(items[0]['after_display'], label)
        for value, label in {'auto': '自动同步', 'manual': '仅手动同步', 'conditional': '条件同步'}.items():
            with self.subTest(value=value):
                row = self.log(after={'erp_sync_policy': value})
                row.diff_items_data = None
                self.db.commit()
                for items in self.views(row, {'erp_sync_policy'}):
                    self.assertEqual(items[0]['after_display'], label)

    def test_release_and_feedback_mail_protocol_states_have_chinese_labels(self):
        cases = [('pms_release_mail', 'accepted', '服务器已接受'),
                 ('pms_release_mail', 'unknown', '结果未知'),
                 ('pms_release_mail', 'pending', '待投递'),
                 ('pms_feedback_notification', 'sent', '已发送'),
                 ('pms_feedback_notification', 'waiting', '待配置')]
        for entity, value, label in cases:
            with self.subTest(entity=entity, value=value):
                row = self.log(after={'status': value}, entity_type=entity)
                self.assertEqual(get_operation_logs(self.db)['items'][0]['diff_items'][0]['after_display'], label)

    def test_deleted_configurable_seed_is_not_falsely_resolved_using_initial_defaults(self):
        self.option('product_category', '1', '现有类别')
        row = self.log(after={'product_category': 2})
        row.diff_items_data = None
        self.db.commit()
        for items in self.views(row, {'product_category'}):
            self.assertEqual(items[0]['after_display'], '未识别选项（编码：2）')

    def test_feedback_category_uses_each_side_event_type_even_when_code_is_identical(self):
        row = self.log({'type_id': 1, 'category_id': 1}, {'type_id': 2, 'category_id': 1},
                       entity_type='pms_feedback_report')
        # Same category ID needs different meanings before and after a type change.
        self.assertIn('category_id', {item['field_key'] for item in json.loads(row.diff_items_data)})
        for items in self.views(row, {'type_id', 'category_id'}):
            by_key = {item['field_key']: item for item in items}
            self.assertEqual(by_key['category_id']['before_display'], '功能异常')
            self.assertEqual(by_key['category_id']['after_display'], '新增功能')

    def test_legacy_feedback_category_uses_full_snapshots_when_type_is_unchanged(self):
        row = self.log({'type_id': 2, 'category_id': None}, {'type_id': 2, 'category_id': 1},
                       entity_type='pms_feedback_report')
        row.diff_items_data = None
        self.db.commit()
        for items in self.views(row, {'type_id', 'category_id'}):
            self.assertEqual(items[0]['after_display'], '新增功能')

    def test_legacy_category_without_type_is_unknown_instead_of_guessing(self):
        row = self.log(after={'category_id': 1}, entity_type='pms_feedback_report')
        row.diff_items_data = None
        self.db.commit()
        for items in self.views(row, {'category_id'}):
            self.assertEqual(items[0]['after_display'], '未识别选项（编码：1）')

    def test_archive_approval_numeric_snapshot_uses_archive_field_semantics(self):
        item = dict(field_key='machine_model', field_label='机型', before=9001, after=9002,
                    before_display='9001', after_display='9002')
        row = self.log(after={'differences_json': json.dumps([item])},
                       entity_type='pms_archive_change')
        row.action = 'submit'
        row.diff_items_data = json.dumps([item])
        self.db.commit()
        for items in self.views(row):
            self.assertEqual(items[0]['before_display'], '历史机型')
            self.assertEqual(items[0]['after_display'], '新机型')

    def test_hidden_fields_and_masking_remain_in_force(self):
        row = self.log(after={'machine_model': 9001, 'password': 'secret-fixture'})
        self.assertEqual(_project_items(self.db, row, set()), [])
        self.assertNotIn('secret-fixture', json.dumps(get_operation_logs(self.db), ensure_ascii=False))

    def test_all_catalog_enum_bindings_use_registered_labels(self):
        from app.services.operation_log import _enum_label_maps, ENTITY_CATALOG_MODULES
        from app.services.field_catalog import build_field_catalog
        for metadata in build_field_catalog():
            code = metadata['enum_code']
            if not code:
                continue
            labels = _enum_label_maps(self.db).get(code, {})
            if not labels:
                self.option(code, '991', '隔离登记选项')
                labels = _enum_label_maps(self.db)[code]
            value, label = next(iter(labels.items()))
            entities = [entity for entity, module in ENTITY_CATALOG_MODULES.items() if module == metadata['module']]
            self.assertTrue(entities, metadata)
            for entity in entities:
                field = metadata['field_code']
                with self.subTest(entity=entity, field=field):
                    item = build_operation_log_diff_items({field: {'before': None,
                        'after': [int(value)] if field == 'product_category_ids' else int(value)}},
                        entity_type=entity, db=self.db)[0]
                    self.assertEqual(item['after_display'], label)


if __name__ == '__main__':
    unittest.main()
