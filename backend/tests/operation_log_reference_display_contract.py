"""Reference display regression tests; only a disposable in-memory database."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_TEMP = tempfile.TemporaryDirectory()
os.environ.update(PMS_CONFIG_FILE='/dev/null', DB_DIALECT='sqlite',
                  SQLITE_DB_PATH=str(Path(_TEMP.name) / 'unused.db'))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
import app.models.init_db
from app.models.user import SysUser
from app.models.product_line import SysProductLine
from app.services.operation_log import record_operation_log, get_operation_logs, MASK_VALUE
from app.services.document_history import _project_items


class ReferenceLogDisplay(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = SysUser(id=17, username='owner', real_name='杨志刚', password_hash='fixture', status=0)
        self.line = SysProductLine(id=1, source_key='kingdee', organization_id=100,
            organization_code='001', organization_name='组织甲', display_name='8吋Bench',
            name_key='bench', is_enabled=0)
        self.db.add_all([self.user, self.line]); self.db.commit()

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def log(self, before=None, after=None, *, legacy=True, entity='pms_project_archive', action='update'):
        row = record_operation_log(self.db, module='项目档案', action=action,
            entity_type=entity, entity_id='1', before_data=before or {}, after_data=after or {})
        self.db.commit()
        if legacy:
            row.diff_items_data = None; self.db.commit()
        return row

    def views(self, row):
        audit = next(i for i in get_operation_logs(self.db)['items'] if i['id'] == row.id)['diff_items']
        document = _project_items(self.db, row, {'manager_id', 'product_line_id', 'quantity'})
        return audit, document

    def test_legacy_reference_names_are_marked_current_in_both_views_without_storage_changes(self):
        row = self.log(after={'manager_id': 17, 'product_line_id': 1, 'business_product_line_id': 1})
        raw = tuple(getattr(row, k) for k in ('before_data', 'after_data', 'diff_data', 'diff_items_data'))
        for items in self.views(row):
            fields = {i['field_key']: i for i in items}
            self.assertEqual(fields['manager_id']['after_display'], '杨志刚（owner）')
            for key in ('product_line_id', 'business_product_line_id'):
                self.assertEqual(fields[key]['after_display'], '8吋Bench')
                self.assertEqual(fields[key]['field_label'], '产品线')
                self.assertEqual(fields[key]['before_display'], '-')
        self.db.expire(row)
        self.assertEqual(raw, tuple(getattr(row, k) for k in ('before_data', 'after_data', 'diff_data', 'diff_items_data')))
        self.assertFalse(self.db.dirty)

    def test_saved_numeric_side_is_repaired_and_real_event_name_is_preserved(self):
        row = self.log({'manager_id': 17}, {'manager_id': '17'}, legacy=False)
        snapshot = json.loads(row.diff_items_data)
        snapshot[0].update(before_display='操作时姓名', after_display='17')
        row.diff_items_data = json.dumps(snapshot, ensure_ascii=False); self.db.commit()
        self.user.real_name = '后来改名'; self.db.commit()
        for items in self.views(row):
            self.assertEqual(items[0]['before_display'], '操作时姓名')
            self.assertEqual(items[0]['after_display'], '后来改名（owner）')

    def test_new_event_snapshot_remains_authoritative_after_rename(self):
        row = self.log(after={'manager_id': 17, 'business_product_line_id': 1}, legacy=False)
        self.user.real_name = '后来改名'; self.line.display_name = '新产品线'; self.db.commit()
        for items in self.views(row):
            fields = {i['field_key']: i for i in items}
            self.assertEqual(fields['manager_id']['after_display'], '杨志刚（owner）')
            self.assertEqual(fields['business_product_line_id']['after_display'], '8吋Bench')

    def test_missing_references_are_explicit_without_claiming_they_were_deleted(self):
        row = self.log(after={'manager_id': 999, 'business_product_line_id': 999})
        for items in self.views(row):
            fields = {i['field_key']: i for i in items}
            self.assertEqual(fields['manager_id']['after_display'], '关联人员不存在（ID：999）')
            self.assertEqual(fields['business_product_line_id']['after_display'], '关联产品线不存在')

    def test_saved_product_line_field_label_drops_id_even_when_event_name_is_preserved(self):
        row = self.log(after={'business_product_line_id': 1}, legacy=False)
        saved = json.loads(row.diff_items_data)
        saved[0].update(field_label='组织产品线归属ID', after_display='当时的产品线')
        row.diff_items_data = json.dumps(saved, ensure_ascii=False); self.db.commit()
        for items in self.views(row):
            self.assertEqual(items[0]['field_label'], '产品线')
            self.assertEqual(items[0]['after_display'], '当时的产品线')
        self.assertEqual(json.loads(row.diff_items_data)[0]['field_label'], '组织产品线归属ID')

    def test_masked_null_and_ordinary_numeric_values_are_not_reference_names(self):
        row = self.log({'manager_id': 17}, {'manager_id': None, 'quantity': 17})
        for items in self.views(row):
            fields = {i['field_key']: i for i in items}
            self.assertEqual(fields['manager_id']['after_display'], '-')
            self.assertEqual(fields['quantity']['after_display'], '17')
        row = self.log(after={'manager_id': MASK_VALUE})
        for items in self.views(row): self.assertEqual(items[0]['after_display'], MASK_VALUE)

    def test_malformed_reference_does_not_crash_or_resolve_to_another_person(self):
        for value in (True, -17, 17.0, '17.0', 'abc', 10**30):
            with self.subTest(value=value):
                row = self.log(after={'manager_id': value})
                for items in self.views(row):
                    self.assertEqual(items[0]['after_display'], '无法识别的关联值')

    def test_nested_values_do_not_gain_a_reference_name(self):
        row = self.log(after={'manager_id': {'id': 17}})
        for items in self.views(row):
            self.assertTrue(all('杨志刚' not in i['after_display'] for i in items))

    def test_other_entity_same_field_name_does_not_gain_archive_reference_mapping(self):
        row = self.log(after={'manager_id': 17}, entity='unknown_resource')
        for items in self.views(row): self.assertEqual(items[0]['after_display'], '17')

    def test_legacy_approval_submission_uses_the_same_current_name_rule(self):
        row = self.log(after={'differences_json': json.dumps([{
            'field_key': 'manager_id', 'before': None, 'after': 17,
            'before_display': '-', 'after_display': '17'}])},
            entity='pms_archive_change', action='submit')
        for items in self.views(row):
            self.assertEqual(items[0]['after_display'], '杨志刚（owner）')

    def test_hidden_reference_is_not_in_document_projection(self):
        row = self.log(after={'manager_id': 17})
        self.assertEqual(_project_items(self.db, row, {'quantity'}), [])

    def test_complete_event_snapshots_do_not_query_current_reference_tables(self):
        from sqlalchemy import event
        row = self.log(after={'manager_id': 17, 'business_product_line_id': 1}, legacy=False)
        statements = []
        def capture(conn, cursor, statement, parameters, context, many):
            if 'FROM sys_user ' in statement or 'FROM sys_product_line ' in statement:
                statements.append(statement)
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            self.views(row)
            self.assertEqual(statements, [])
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)


if __name__ == '__main__':
    unittest.main()
