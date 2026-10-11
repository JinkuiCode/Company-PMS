"""Query v2 for the two server-paged system lists; temporary SQLite only."""
import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEMP = tempfile.TemporaryDirectory()
os.environ['DB_DIALECT'] = 'sqlite'
os.environ['SQLITE_DB_PATH'] = str(Path(TEMP.name) / 'unused.db')

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, create_mock_engine
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Query, Session
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
import app.models.init_db
from app.models.erp_task import ErpSyncTask
from app.models.operation_log import SysOperationLog
from app.models.project import PmsProjectArchive
from app.models.user import SysUser
from app.api import operation_logs, sync_tasks
from app.services import erp_queue, operation_log
from app.services.authorization import get_current_user_context


def condition(field, operator, value=None, end=None, version=2):
    return dict(schemaVersion=version, field=field, operator=operator, value=value, valueEnd=end)


def values(field, *selected):
    return dict(field=field, mode='values', values=list(selected))


class SystemListQueryContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = SysUser(username='fallback-user', real_name='', password_hash='test-only', status=1)
        self.db.add(self.user)
        self.db.flush()
        self.ctx = dict(user_id=self.user.id, data_scope=1, product_line_ids=[1],
                        permissions=['system:operation-log:view', 'system:sync:view'])
        self.visible = PmsProjectArchive(project_code='VISIBLE', project_name='Visible',
            manager_id=self.user.id, business_product_line_id=1, is_enabled=1)
        self.other_line = PmsProjectArchive(project_code='HIDDEN-LINE', project_name='Hidden line',
            manager_id=self.user.id, business_product_line_id=2, is_enabled=1)
        self.other_person = PmsProjectArchive(project_code='HIDDEN-PERSON', project_name='Hidden person',
            manager_id=999, business_product_line_id=1, is_enabled=1)
        self.db.add_all([self.visible, self.other_line, self.other_person])
        self.db.flush()
        for i, (code, status, attempts, message) in enumerate([
            ('Pump%_', 'queued', 0, 'literal%_'), ('Pump', 'success', 1, 'done'),
            ('X-Pump', 'failed', 2, None), ('Empty', 'review', 3, ''),
        ]):
            self.db.add(ErpSyncTask(archive_id=self.visible.id, project_code=code,
                project_name=code, status=status, attempts=attempts, message=message,
                operator_id=self.user.id if i < 3 else None,
                created_at=datetime.datetime(2026, 10, 10 if i < 2 else 11, 12),
                started_at=datetime.datetime(2026, 10, 10, 8) if i == 0 else None))
            self.db.add(SysOperationLog(module='项目档案' if i < 3 else '认证',
                action=['create', 'update', 'delete', 'login'][i], entity_type='test',
                entity_name=code, operator_name='Tester' if i < 3 else None,
                status='success' if i < 2 else 'failed', summary=message or '',
                request_path='/api/test', created_at=datetime.datetime(2026, 10, 10 if i < 2 else 11, 12)))
        for archive in [self.other_line, self.other_person]:
            self.db.add(ErpSyncTask(archive_id=archive.id, project_code=archive.project_code,
                project_name=archive.project_name, status='queued', attempts=99))
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(operation_logs.router)
        self.app.include_router(sync_tasks.router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user_context] = lambda: self.ctx
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def get(self, path, *, filters=None, columns=None, **params):
        if filters is not None:
            params['filters'] = json.dumps(filters)
        if columns is not None:
            params['column_filters'] = json.dumps(columns)
        response = self.client.get('/api/' + path, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_capability_survives_operation_log_response_model(self):
        for path in ['operation-logs', 'sync-tasks']:
            with self.subTest(path=path):
                result = self.get(path)
                self.assertEqual(result.get('query_version'), 2)

    def test_operation_log_filters_before_count_and_page(self):
        result = self.get('operation-logs', filters=[condition('module', 'reference', ['项目档案'])],
            columns=[values('status', 'success')], page=2, page_size=1)
        self.assertEqual(result['total'], 2)
        self.assertEqual([item['action'] for item in result['items']], ['create'])

    def test_operation_log_enum_text_uses_display_labels(self):
        for field, operator, needle, expected in [
            ('action', 'contains', '编辑', ['update']), ('status', 'endsWith', '败', ['login', 'delete']),
            ('action', 'notContains', '登录', ['delete', 'update', 'create']),
        ]:
            with self.subTest(field=field, operator=operator):
                result = self.get('operation-logs', filters=[condition(field, operator, needle)])
                self.assertEqual([item['action'] for item in result['items']], expected)
        self.assertEqual(self.get('operation-logs', filters=[condition('action', 'contains', 'update')])['total'], 0)

    def test_operation_log_summary_path_and_legacy_conditions(self):
        result = self.get('operation-logs', filters=[condition('summary', 'contains', '%_'),
            condition('request_path', 'startsWith', '/api/')])
        self.assertEqual(result['total'], 1)
        legacy = self.get('operation-logs', filters=[condition('entity_name', 'contains', 'Pump', version=1)],
            module='项目档案', status='success')
        self.assertEqual(legacy['total'], 2)

    def test_sync_numeric_zero_empty_and_dates(self):
        result = self.get('sync-tasks', filters=[condition('attempts', 'equals', 0)])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['project_code'], 'Pump%_')
        self.assertEqual(self.get('sync-tasks', filters=[condition('attempts', 'isEmpty')])['total'], 0)
        self.assertEqual(self.get('sync-tasks', filters=[condition('message', 'isEmpty')])['total'], 2)
        self.assertEqual(self.get('sync-tasks', filters=[condition('message', 'notContains', 'done')])['total'], 1)
        self.assertEqual(self.get('sync-tasks', filters=[condition('created_at', 'between', '2026-10-10', '2026-10-10')])['total'], 2)
        self.assertEqual(self.get('sync-tasks', columns=[values('created_at', '2026-10-10')])['total'], 2)
        self.assertEqual(self.get('sync-tasks', columns=[values('started_at', None)])['total'], 3)
        self.assertEqual(self.get('sync-tasks', columns=[values('message', None)])['total'], 2)

    def test_sync_filter_count_page_labels_and_join_fallback(self):
        result = self.get('sync-tasks', filters=[condition('project_code', 'endsWith', 'Pump')],
            columns=[dict(field='attempts', mode='condition', condition=condition('attempts', 'greaterOrEqual', 1))],
            page=2, page_size=1)
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['items'][0]['project_code'], 'Pump')
        self.assertEqual(self.get('sync-tasks', filters=[condition('status', 'contains', '成功')])['total'], 1)
        self.assertEqual(self.get('sync-tasks', filters=[condition('status', 'reference', ['queued', 'success'])])['total'], 2)
        self.assertEqual(self.get('sync-tasks', filters=[condition('operator_name', 'equals', 'fallback-user')])['total'], 3)

    def test_candidates_exclude_own_column_not_base_or_other_columns(self):
        result = self.get('sync-tasks/column-values', field='status',
            filters=[condition('project_code', 'startsWith', 'Pump')],
            columns=[values('status', 'queued'), values('attempts', 1)])
        self.assertEqual(result['items'], [dict(value='success', label='同步成功', count=1)])
        result = self.get('operation-logs/column-values', field='action',
            filters=[condition('module', 'equals', '项目档案')],
            columns=[values('action', 'create'), values('status', 'success')], keyword='编辑')
        self.assertEqual(result['items'], [dict(value='update', label='编辑', count=1)])

    def test_candidate_day_counts_null_and_numeric_values(self):
        result = self.get('sync-tasks/column-values', field='created_at')
        self.assertEqual(result['items'], [dict(value='2026-10-10', label='2026-10-10', count=2),
                                         dict(value='2026-10-11', label='2026-10-11', count=2)])
        result = self.get('sync-tasks/column-values', field='started_at')
        self.assertEqual(result['items'][0]['value'], None)
        self.assertEqual(result['items'][0]['count'], 3)
        self.assertEqual(self.get('sync-tasks/column-values', field='attempts')['items'][0]['value'], 0)

    def test_candidate_paging_is_full_dataset_capped_and_search_is_literal(self):
        for i in range(105):
            self.db.add(SysOperationLog(module='Bulk', action='update', entity_type='test',
                entity_name=f'Bulk-{i:03}', status='success', summary='bulk'))
        self.db.commit()
        first = self.get('operation-logs/column-values', field='entity_name', module='Bulk', page_size=100)
        second = self.get('operation-logs/column-values', field='entity_name', module='Bulk', page=2, page_size=100)
        self.assertEqual(len(first['items']), 100)
        self.assertTrue(first['hasMore'])
        self.assertEqual(len(second['items']), 5)
        self.assertFalse(second['hasMore'])
        self.assertEqual(self.get('sync-tasks/column-values', field='project_code', keyword='%_')['items'][0]['value'], 'Pump%_')
        self.assertEqual(self.client.get('/api/sync-tasks/column-values', params={'field': 'status', 'page_size': 101}).status_code, 422)

    def test_candidates_and_lists_preserve_person_product_line_scope(self):
        result = self.get('sync-tasks/column-values', field='project_code')
        self.assertEqual(len(result['items']), 4)
        self.assertFalse(any(item['value'].startswith('HIDDEN') for item in result['items']))
        self.ctx['product_line_ids'] = []
        self.assertEqual(self.get('sync-tasks')['total'], 0)
        self.assertEqual(self.get('sync-tasks/column-values', field='project_code')['items'], [])

    def test_candidates_use_same_permission_as_lists(self):
        self.ctx['permissions'] = []
        for path in ['operation-logs', 'sync-tasks', 'operation-logs/column-values', 'sync-tasks/column-values']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get('/api/' + path, params={'field': 'status'}).status_code, 403)

    def test_invalid_filters_fail_closed_in_lists_and_candidates(self):
        invalid_conditions = [condition('before_data', 'contains', 'x'), condition('password', 'equals', 'x'),
            condition('attempts', 'equals', True), condition('attempts', 'equals', None),
            condition('attempts', 'between', 2, 0), condition('status', 'reference', []),
            condition('status', 'reference', [True]), condition('project_code', 'reference', ['Pump']),
            condition('created_at', 'equals', '2026-02-30'), condition('message', 'equals', 'x', version=999)]
        invalid_columns = [values('password', 'x'), values('attempts', True), values('status', 0),
            values('attempts', '0'), dict(field='message', mode='invalid'),
            dict(field='status', mode='condition', condition=condition('message', 'contains', 'x')),
            dict(field='status', mode='condition', condition=condition('status', 'equals', 'success', version=1))]
        for path in ['sync-tasks', 'sync-tasks/column-values']:
            for item in invalid_conditions:
                with self.subTest(path=path, condition=item):
                    response = self.client.get('/api/' + path, params={'field': 'status', 'filters': json.dumps([item])})
                    self.assertEqual(response.status_code, 422, response.text)
            for item in invalid_columns:
                with self.subTest(path=path, column=item):
                    response = self.client.get('/api/' + path, params={'field': 'status', 'column_filters': json.dumps([item])})
                    self.assertEqual(response.status_code, 422, response.text)
        for path in ['operation-logs', 'operation-logs/column-values']:
            response = self.client.get('/api/' + path, params={'field': 'status', 'filters': '[invalid'})
            self.assertEqual(response.status_code, 422)

    def test_sensitive_candidate_fields_rejected(self):
        for field in ['before_data', 'after_data', 'diff_data', 'user_agent', 'error_msg', 'history']:
            for path in ['operation-logs/column-values', 'sync-tasks/column-values']:
                self.assertEqual(self.client.get('/api/' + path, params={'field': field}).status_code, 422)

    def test_numeric_zero_and_null_column_values_are_distinct(self):
        from app.services.system_list_query import apply_system_list_query
        first = self.db.query(SysOperationLog).order_by(SysOperationLog.id).first()
        first.operator_id = 0
        self.db.commit()
        columns = {'operator_id': (SysOperationLog.operator_id, 'number')}
        query = self.db.query(SysOperationLog)
        self.assertEqual(apply_system_list_query(query, columns, column_filters=[values('operator_id', 0)]).count(), 1)
        self.assertEqual(apply_system_list_query(query, columns, column_filters=[values('operator_id', None)]).count(), 3)
        self.assertEqual(apply_system_list_query(query, columns, column_filters=[values('operator_id')]).count(), 0)

    def test_mssql_bindings_wildcards_and_candidate_grouping(self):
        from app.services.system_list_query import apply_system_list_query, system_column_values
        columns = erp_queue.task_list_columns()
        query = erp_queue._task_list_query(self.db, scope_context=self.ctx)
        filtered = apply_system_list_query(query, columns, [condition('message', 'contains', "[AB]%_/'; DROP TABLE test --")])
        compiled = filtered.statement.compile(dialect=mssql.dialect())
        self.assertNotIn('DROP TABLE', str(compiled))
        self.assertTrue(any('/[ab]/%/_//' in str(value) for value in compiled.params.values()))
        statements = []
        def capture(query):
            statements.append(query.statement.compile(dialect=mssql.pyodbc.dialect(paramstyle='qmark'),
                compile_kwargs={'render_postcompile': True}))
            return []
        with patch.object(Query, 'all', autospec=True, side_effect=capture):
            system_column_values(query, columns, 'operator_name')
            with patch.object(self.db, 'get_bind', return_value=create_mock_engine('mssql+pyodbc://', lambda *a, **k: None)):
                system_column_values(query, columns, 'created_at')
            system_column_values(query, columns, 'status', keyword='成功', labels={'status': erp_queue.STATUS_LABELS})
        # Repeated grouping expressions must not contain different ODBC parameter slots.
        self.assertNotIn('', statements[0].params.values())
        self.assertIn('CAST(erp_sync_task.created_at AS DATE)', str(statements[1]))
        self.assertIn('ROW_NUMBER()', str(statements[1]))
        self.assertIn('AS NVARCHAR(1024)', str(statements[2]))

    def test_payload_limits_and_shapes_reject_without_server_errors(self):
        malformed = [dict(schemaVersion=2, field=[], operator='equals', value='x'),
                     condition('status', ['equals'], 'success'), condition('status', 'equals', 'success', version=True)]
        for item in malformed:
            response = self.client.get('/api/sync-tasks', params={'filters': json.dumps([item])})
            self.assertEqual(response.status_code, 422)
        for payload in ['{}', 'null', '[null]', '0']:
            response = self.client.get('/api/sync-tasks', params={'column_filters': payload})
            self.assertEqual(response.status_code, 422)
        for columns in [[values('status', 'queued'), values('status', 'success')],
                        [values('message', *['value'] * 1001)]]:
            self.assertEqual(self.client.get('/api/sync-tasks', params={'column_filters': json.dumps(columns)}).status_code, 422)
        self.assertEqual(self.client.get('/api/sync-tasks', params={'filters': json.dumps([
            condition('status', 'reference', ['queued'] * 900), condition('status', 'reference', ['success'] * 900)])}).status_code, 422)

    def test_candidates_preserve_legacy_base_and_unknown_historical_enum_labels(self):
        result = self.get('sync-tasks/column-values', field='status', base_keyword='Pump', operator='fallback-user',
            start='2026-10-10T00:00:00', end='2026-10-10T23:59:59')
        self.assertEqual({item['value'] for item in result['items']}, {'queued', 'success'})
        result = self.get('operation-logs/column-values', field='action', base_keyword='Pump', module='项目档案')
        self.assertEqual({item['value'] for item in result['items']}, {'create', 'update', 'delete'})
        self.db.add(SysOperationLog(module='History', action='legacy_action', entity_type='test', summary='historical'))
        self.db.commit()
        result = self.get('operation-logs/column-values', field='action', module='History', keyword='legacy')
        self.assertEqual(result['items'], [dict(value='legacy_action', label='legacy_action', count=1)])

    def test_large_numeric_column_selection_uses_bounded_sql_membership(self):
        with TestClient(self.app, raise_server_exceptions=False) as client:
            response = client.get('/api/sync-tasks', params={'column_filters': json.dumps([values('attempts', *range(1000))])})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['total'], 4)

    def test_archive_task_list_does_not_claim_v2_while_ignoring_conditions(self):
        result = self.get(f'sync-tasks/archive/{self.visible.id}', filters=[condition('attempts', 'equals', 0)])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result.get('query_version'), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
