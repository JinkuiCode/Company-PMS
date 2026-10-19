"""Feedback person labels, isolated logs and current document authorization only."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import operation_log_reference_display_contract as fixture
from app.models.user import SysUser
from app.services.operation_log import MASK_VALUE, get_operation_logs
from app.services.document_history import _project_items, get_document_history


class FeedbackPersonLabels(unittest.TestCase):
    tearDown = fixture.ReferenceLogDisplay.tearDown

    def setUp(self):
        fixture.ReferenceLogDisplay.setUp(self)
        self.other = SysUser(id=18, username='handler', real_name='处理人乙',
                             password_hash='fixture', status=1)
        self.db.add(self.other)
        self.db.commit()

    def log(self, before=None, after=None, *, legacy=True, entity='pms_feedback_report'):
        return fixture.ReferenceLogDisplay.log(self, before, after, legacy=legacy, entity=entity)

    def views(self, row):
        audit = next(item for item in get_operation_logs(self.db)['items'] if item['id'] == row.id)['diff_items']
        return audit, _project_items(self.db, row, {'author_id', 'handler_id', 'version', 'module_id'})

    def test_legacy_people_resolve_in_both_views_without_changing_storage(self):
        row = self.log({'handler_id': 17}, {'handler_id': 18, 'author_id': 17, 'version': 18})
        raw = tuple(getattr(row, key) for key in ('before_data', 'after_data', 'diff_data', 'diff_items_data'))
        for items in self.views(row):
            fields = {item['field_key']: item for item in items}
            self.assertEqual(fields['handler_id']['before_display'], '杨志刚（owner）')
            self.assertEqual(fields['handler_id']['after_display'], '处理人乙（handler）')
            self.assertEqual(fields['author_id']['after_display'], '杨志刚（owner）')
            self.assertEqual(fields['version']['after_display'], '18')
            self.assertEqual(fields['handler_id']['before_name_source'], 'current')
            self.assertEqual(fields['handler_id']['after_name_source'], 'current')
            self.assertEqual(fields['author_id']['after_name_source'], 'current')
        self.db.expire(row)
        self.assertEqual(raw, tuple(getattr(row, key) for key in ('before_data', 'after_data', 'diff_data', 'diff_items_data')))
        self.assertFalse(self.db.dirty)

    def test_new_event_names_survive_later_rename(self):
        row = self.log(after={'author_id': 17, 'handler_id': 18}, legacy=False)
        self.user.real_name = '后来姓名甲'
        self.other.real_name = '后来姓名乙'
        self.db.commit()
        for items in self.views(row):
            fields = {item['field_key']: item for item in items}
            self.assertEqual(fields['author_id']['after_display'], '杨志刚（owner）')
            self.assertEqual(fields['handler_id']['after_display'], '处理人乙（handler）')
            self.assertEqual(fields['author_id']['after_name_source'], 'snapshot')
            self.assertEqual(fields['handler_id']['after_name_source'], 'snapshot')

    def test_numeric_saved_side_is_repaired_but_event_name_is_preserved(self):
        row = self.log({'handler_id': 17}, {'handler_id': 18}, legacy=False)
        data = json.loads(row.diff_items_data)
        data[0].update(before_display='操作时处理人甲', after_display='18')
        row.diff_items_data = json.dumps(data, ensure_ascii=False)
        self.db.commit()
        for items in self.views(row):
            self.assertEqual(items[0]['before_display'], '操作时处理人甲')
            self.assertEqual(items[0]['after_display'], '处理人乙（handler）')
            self.assertEqual(items[0]['before_name_source'], 'snapshot')
            self.assertEqual(items[0]['after_name_source'], 'current')

    def test_missing_null_masked_and_malformed_people_do_not_leak_or_guess(self):
        for value, expected in ((999, '关联人员不存在（ID：999）'),
                                (None, '-'), (MASK_VALUE, MASK_VALUE),
                                (True, '无法识别的关联值'), ('18.0', '无法识别的关联值'),
                                (10**30, '无法识别的关联值')):
            with self.subTest(value=value):
                row = self.log({'handler_id': 17}, {'handler_id': value})
                for items in self.views(row):
                    self.assertEqual(items[0]['after_display'], expected)

    def test_entity_and_field_whitelist_and_field_projection_are_preserved(self):
        row = self.log(after={'handler_id': 18}, entity='unknown_resource')
        for items in self.views(row):
            self.assertEqual(items[0]['after_display'], '18')
        row = self.log(after={'handler_id': 18, 'version': 18})
        self.assertEqual([item['field_key'] for item in _project_items(self.db, row, {'version'})], ['version'])

    def test_current_report_access_is_checked_before_any_history_is_returned(self):
        from app.models.feedback import FeedbackReport
        from fastapi import HTTPException
        report = FeedbackReport(id=1, report_no='FIXTURE-ONLY', submission_id='fixture',
            type_id=1, module_id=1, category_id=1, impact_id=1,
            title='fixture', description='fixture', expected_result='fixture', author_id=18)
        self.db.add(report)
        self.db.commit()
        self.log(after={'handler_id': 17})
        with self.assertRaises(HTTPException) as denied:
            get_document_history(self.db, 'feedback', 1,
                                 {'user_id': 17, 'permissions': ['feedback:view']})
        self.assertEqual(denied.exception.status_code, 404)
        result = get_document_history(self.db, 'feedback', 1,
                                      {'user_id': 18, 'permissions': ['feedback:view']})
        self.assertEqual(result['items'][0]['diff_items'][0]['after_display'], '杨志刚（owner）')


if __name__ == '__main__':
    unittest.main()
