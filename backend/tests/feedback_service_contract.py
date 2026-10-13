"""Business behavior, data isolation, optimistic updates and transactional mail."""
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import Base
import app.models.init_db
from app.models.user import SysUser
from app.models.dict import SysDictItem
from app.models.feedback import FeedbackReport, FeedbackFollowup, FeedbackNotification
from app.services.feedback_migration import install_feedback
from app.schemas.feedback import FeedbackCreate, FeedbackHandle, FeedbackSupplement


class FeedbackServiceContract(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.feedback'), 'feedback business service is missing')
        self.service = importlib.import_module('app.services.feedback')
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([SysUser(id=i, username=f'fixture{i}', real_name=f'测试{i}', password_hash='unused', email=f'user{i}@example.invalid', status=1) for i in (1, 2)])
        install_feedback(self.db)
        self.db.commit()
        self.owner = {'user_id': 1, 'permissions': ['feedback:view', 'feedback:add', 'feedback:supplement', 'feedback:export']}
        self.other = {**self.owner, 'user_id': 2}
        self.admin = {**self.other, 'permissions': [*self.other['permissions'], 'feedback:handle']}
        self.payload = FeedbackCreate(submission_id='11111111-1111-4111-8111-111111111111', type_id=1, module_id=1, category_id=1, impact_id=1, title='列表异常', description='查询没有结果', expected_result='显示正确数据', steps='点击查询')

    def tearDown(self):
        if hasattr(self, 'db'):
            self.db.close()
            self.engine.dispose()

    def create(self):
        return self.service.create_report(self.db, self.owner, self.payload)

    def test_lost_response_retry_returns_same_report_without_extra_history_or_notification(self):
        first = self.create()
        second = self.create()
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(self.db.query(FeedbackReport).count(), 1)
        self.assertEqual(self.db.query(FeedbackFollowup).count(), 1)
        self.assertEqual(self.db.query(FeedbackNotification).count(), 1)
        with self.assertRaises(HTTPException) as conflict:
            self.service.create_report(self.db, self.owner, self.payload.model_copy(update={'title':'另一项需求'}))
        self.assertEqual(conflict.exception.status_code, 409)

    def test_owner_scope_includes_detail_query_statistics_and_export(self):
        row = self.create()
        with self.assertRaises(HTTPException) as denied:
            self.service.get_report(self.db, self.other, row['id'])
        self.assertEqual(denied.exception.status_code, 404)
        self.assertEqual(self.service.list_reports(self.db, self.other)['total'], 0)
        self.assertEqual(self.service.list_reports(self.db, self.admin)['total'], 1)
        self.assertEqual(self.service.statistics(self.db, self.other)['total'], 0)
        # A role label or unrelated global business scope never grants feedback access.
        self.other.update(role_codes=['admin'], permissions=[*self.other['permissions'], 'business:data:all'])
        self.assertEqual(self.service.list_reports(self.db, self.other)['total'], 0)

    def test_handling_and_supplement_preserve_history_and_queue(self):
        row = self.create()
        self.assertEqual(row['status_id'], 1)
        handled = self.service.handle_report(self.db, self.admin, row['id'], FeedbackHandle(version=1, status_id=5, outcome_id=1, cause_id=1, opinion='已修复'))
        self.assertEqual((handled['status_id'], handled['version']), (5, 2))
        self.assertEqual(self.db.query(FeedbackFollowup).count(), 2)
        self.assertEqual({n.audience for n in self.db.query(FeedbackNotification)}, {'admins', 'author'})
        self.service.supplement_report(self.db, self.owner, row['id'], FeedbackSupplement(version=2, description='补充验证情况'))
        self.assertEqual(self.db.query(FeedbackFollowup).count(), 3)
        self.assertEqual(self.db.query(FeedbackNotification).count(), 3)

    def test_module_statistics_separate_types_and_completion(self):
        row = self.create()
        self.service.handle_report(self.db, self.admin, row['id'], FeedbackHandle(version=1, status_id=5, outcome_id=1, cause_id=1, opinion='完成'))
        demand = self.payload.model_copy(update={'submission_id':'22222222-2222-4222-8222-222222222222', 'type_id':2, 'title':'新增需求', 'steps':''})
        self.service.create_report(self.db, self.owner, demand)
        module = self.service.statistics(self.db, self.admin)['modules'][0]
        self.assertEqual((module['issues'], module['requests'], module['open'], module['completed']), (1, 1, 1, 1))
        self.assertEqual(self.service.list_reports(self.db, self.owner, status_id=0)['total'], 1)

    def test_stale_updates_do_not_change_data_history_or_mail(self):
        row = self.create()
        self.service.supplement_report(self.db, self.owner, row['id'], FeedbackSupplement(version=1, description='补充'))
        with self.assertRaises(HTTPException) as conflict:
            self.service.handle_report(self.db, self.admin, row['id'], FeedbackHandle(version=1, status_id=2, opinion='排查'))
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertEqual(self.db.query(FeedbackFollowup).count(), 2)
        self.assertEqual(self.db.query(FeedbackNotification).count(), 2)

    def test_disabled_enum_and_wrong_type_category_rejected(self):
        for updates in ({'type_id': 2, 'category_id': 6}, {'module_id': 999}):
            with self.subTest(updates=updates), self.assertRaises(HTTPException):
                self.service.create_report(self.db, self.owner, self.payload.model_copy(update=updates))
        item = self.db.query(SysDictItem).filter_by(item_label='功能异常').one()
        item.status = 0
        self.db.commit()
        with self.assertRaises(HTTPException):
            self.create()
        self.assertEqual(self.db.query(FeedbackReport).count(), 0)
        self.assertEqual(self.db.query(FeedbackNotification).count(), 0)

    def test_query_protocol_filters_before_pagination_and_rejects_bad_fields(self):
        self.create()
        filter_ = [{'schemaVersion': 2, 'field': 'title', 'operator': 'contains', 'value': '没有'}]
        self.assertEqual(self.service.list_reports(self.db, self.owner, filters=filter_)['total'], 0)
        filter_[0]['value'] = '列表'
        self.assertEqual(self.service.list_reports(self.db, self.owner, filters=filter_)['total'], 1)
        self.assertEqual(self.service.list_reports(self.db, self.owner, page_size=500)['query_version'], 2)
        filter_[0]['field'] = 'password_hash'
        with self.assertRaises(HTTPException):
            self.service.list_reports(self.db, self.owner, filters=filter_)

    def test_business_time_and_date_filter_use_china_day_not_utc_day(self):
        from datetime import datetime
        row = self.create()
        report = self.db.get(FeedbackReport, row['id'])
        report.created_at = datetime(2026, 10, 11, 18, 30)
        self.db.commit()
        display = self.service.get_report(self.db, self.owner, row['id'])['created_at']
        self.assertEqual(display, '2026-10-12T02:30:00+08:00')
        filters = [{'schemaVersion':2, 'field':'created_at', 'operator':'equals', 'value':'2026-10-12'}]
        self.assertEqual(self.service.list_reports(self.db, self.owner, filters=filters)['total'], 1)


if __name__ == '__main__':
    unittest.main()
