"""Business XLSX exports: scope, submitted query, safe labels and full rows."""
import importlib.util
import io
import json
import sys
import unittest
import zipfile
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import app.models.init_db
from app.core.database import Base, get_db
from app.models.project import PmsProjectArchive, PmsProject, PmsTask, PmsProjectSheetDetail
from app.models.rbac import SysDept
from app.models.user import SysUser
from app.models.product_line import SysProductLine
from app.models.operation_log import SysOperationLog
from app.services.authorization import get_current_user_context
from app.services.enum_registry import initialize_enum_definitions


def condition(field, operator, value=None, **extra):
    return dict(schemaVersion=2, field=field, operator=operator, value=value, **extra)


def workbook_rows(content):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        root = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        assert not root.findall('.//s:f', ns), 'formula injection'
        rows = []
        for row in root.findall('.//s:sheetData/s:row', ns):
            values = {}
            for cell in row:
                column = ''.join(c for c in cell.attrib['r'] if c.isalpha())
                values[column] = ''.join(cell.itertext())
            rows.append(values)
        return rows


class BusinessExportContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add_all([SysUser(id=1, username='fixture', real_name='张三', password_hash='never-export', dept_id=1),
                         SysUser(id=2, username='other', real_name='李四', password_hash='never-export', dept_id=2),
                         SysDept(id=1, dept_name='研发部'), SysDept(id=2, dept_name='外部部'),
                         SysProductLine(id=1, display_name='产线一', source_key='fixture', organization_id=1, organization_code='1', organization_name='组织一', name_key='line1'),
                         SysProductLine(id=2, display_name='产线二', source_key='fixture', organization_id=2, organization_code='2', organization_name='组织二', name_key='line2')])
        self.db.flush()
        initialize_enum_definitions(self.db)
        for i in range(1, 22):
            self.db.add(PmsProjectArchive(id=i, project_code=f'A{i:02}', project_name='=1+1' if i == 1 else f'项目{i}',
                        manager_id=1 if i <= 20 else 2, business_product_line_id=1 if i <= 20 else 2,
                        status=1, is_enabled=1, customer='客户', plan_start_date=datetime(2026, 10, 11, 23, 59)))
            self.db.add(PmsProject(id=i, archive_id=i, project_code=f'P{i:02}', project_name=f'项目{i}',
                        dept_id=1 if i <= 20 else 2, pm_id=1 if i <= 20 else 2, status=1,
                        budget=i, start_date=date(2026, 10, 11)))
            self.db.add(PmsProjectSheetDetail(project_id=i, detail_data=json.dumps({'po_date': '2025-03-01'}), updated_by=1))
        self.db.flush()
        for i in range(1, 22):
            self.db.add(PmsTask(id=i, project_id=1 if i <= 20 else 21, task_name=f'任务{i:02}',
                        assignee_id=1, progress=i, status=1, start_date=date(2026, 10, 11), sort=i))
        self.db.commit()
        self.context = {'user_id': 1, 'dept_id': 1, 'data_scope': 2, 'product_line_ids': [1],
                        'permissions': ['project:archive:view', 'project:archive:export', 'project:list:view', 'project:list:export']}
        app = FastAPI()
        from app.api.projects import router
        app.include_router(router)
        if importlib.util.find_spec('app.api.business_exports'):
            from app.api.business_exports import router as export_router
            app.include_router(export_router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user_context] = lambda: self.context
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def export(self, route='/api/projects/export', **kwargs):
        return self.client.post(route, json={'columns': ['project_code', 'project_name'], **kwargs})

    def test_full_project_export_dynamic_values_labels_and_sort(self):
        response = self.export(columns=['pm_name', 'status', 'budget', 'sheet:order_year'], sort=[{'colId': 'budget', 'sort': 'asc'}])
        self.assertEqual(response.status_code, 200, response.text)
        rows = workbook_rows(response.content)
        self.assertEqual(len(rows), 21)
        self.assertEqual(rows[0], {'A': '负责人', 'B': '节点', 'C': '预算', 'D': '订单年份'})
        self.assertEqual(rows[1], {'A': '张三', 'B': '进行中', 'C': '1', 'D': '2025'})
        self.assertEqual(rows[-1]['C'], '20')
        self.assertIn('attachment;', response.headers['content-disposition'])
        log = self.db.query(SysOperationLog).filter_by(action='export').one()
        self.assertEqual(json.loads(log.after_data)['row_count'], 20)
        self.assertNotIn('never-export', str(log.after_data))

    def test_project_query_projection_keeps_export_display_sources(self):
        columns = ['project_code', 'sheet:project_code', 'project_name', 'sheet:project_name']
        for payload in (
            {'filters': [condition('project_code', 'contains', 'A01')]},
            {'column_filters': [{'field': 'project_code', 'mode': 'values', 'values': ['A01']}]},
            {'column_filters': [{'field': 'project_code', 'mode': 'condition',
                                 'condition': condition('project_code', 'contains', 'A01')}]},
        ):
            with self.subTest(payload=payload):
                response = self.export(columns=columns, **payload)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(workbook_rows(response.content)[1:],
                                 [{'A': 'P01', 'B': 'A01', 'C': '项目1', 'D': '=1+1'}])

    def test_project_sort_uses_each_display_column_source(self):
        self.db.get(PmsProjectArchive, 1).project_code = 'Z01'
        self.db.commit()
        for field, first in [('project_code', 'P01'), ('sheet:project_code', 'P02')]:
            response = self.export(columns=['project_code', 'sheet:project_code'],
                                   sort=[{'colId': field, 'sort': 'asc'}])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(workbook_rows(response.content)[1]['A'], first)

    def test_queryv2_columns_intersect_and_aggregates_not_recomputed(self):
        response = self.export(filters=[condition('budget', 'greaterOrEqual', 10)],
                               column_filters=[{'field': 'budget', 'mode': 'values', 'values': [10, 18]}],
                               sort=[{'colId': 'budget', 'sort': 'desc'}], columns=['budget', 'total_progress'])
        self.assertEqual(response.status_code, 200, response.text)
        rows = workbook_rows(response.content)
        self.assertEqual([r['A'] for r in rows[1:]], ['18', '10'])
        response = self.export(column_filters=[{'field': 'budget', 'mode': 'values', 'values': []}])
        self.assertEqual(len(workbook_rows(response.content)), 1)

    def test_archive_reuses_scope_date_query_and_excel_literal(self):
        response = self.export('/api/projects/archives/export', columns=['project_name', 'manager_name', 'status', 'product_line_id'],
                               filters=[condition('project_code', 'reference', [1, 21])],
                               column_filters=[{'field': 'plan_start_date', 'mode': 'values', 'values': ['2026-10-11']}])
        self.assertEqual(response.status_code, 200, response.text)
        rows = workbook_rows(response.content)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['A'], '=1+1')
        self.assertEqual((rows[1]['B'], rows[1]['D']), ('张三', '产线一'))
        self.assertNotIn('never-export', str(rows))

    def test_task_export_complete_and_project_scope_checked(self):
        response = self.export('/api/projects/1/tasks/export', columns=['task_name', 'assignee_name', 'status'],
                               filters=[condition('assignee_name', 'reference', ['张三'])])
        self.assertEqual(response.status_code, 200, response.text)
        rows = workbook_rows(response.content)
        self.assertEqual(len(rows), 21)
        self.assertEqual(rows[1]['B'], '张三')
        self.assertEqual(self.export('/api/projects/21/tasks/export', columns=['task_name']).status_code, 404)

    def test_permissions_view_and_export_both_required_live(self):
        for route, prefix in [('/api/projects/export', 'project:list'), ('/api/projects/1/tasks/export', 'project:list'),
                              ('/api/projects/archives/export', 'project:archive')]:
            for permissions in ([], [prefix + ':view'], [prefix + ':export']):
                self.context['permissions'] = permissions
                response = self.export(route, columns=['task_name'] if '/tasks/' in route else ['project_code'])
                self.assertEqual(response.status_code, 403, response.text)

    def test_unknown_fields_pagination_bad_conditions_fail_not_silently_dropped(self):
        invalid = [dict(columns=['password_hash']), dict(columns=['sheet:password']), dict(parameters={'page': 2}),
                   dict(filters=[condition('budget', 'in', [1, 2])]), dict(sort=[{'colId': 'password_hash', 'sort': 'asc'}]),
                   dict(column_filters=[{'field': 'budget', 'mode': 'values', 'values': [True]}]),
                   dict(column_filters=[{'field': 'budget', 'mode': 'values', 'values': [1]}, {'field': 'budget', 'mode': 'values', 'values': [2]}])]
        for payload in invalid:
            response = self.export(**payload)
            self.assertEqual(response.status_code, 422, str(payload))
        response = self.export('/api/projects/archives/export', columns=['erp_error_msg'])
        self.assertEqual(response.status_code, 422)

    def test_no_business_scope_yields_no_rows(self):
        self.context['product_line_ids'] = []
        response = self.export()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(workbook_rows(response.content)), 1)

    def test_chunked_export_no_row_cap_and_global_sort(self):
        from app.services import business_export, project
        with patch.object(business_export, 'BATCH_SIZE', 3), patch.object(project, 'get_project_list', wraps=project.get_project_list) as fetch:
            response = self.export(columns=['budget', 'sheet:order_year'], sort=[{'colId': 'budget', 'sort': 'desc'}])
        self.assertEqual(response.status_code, 200)
        self.assertEqual([int(r['A']) for r in workbook_rows(response.content)[1:]], list(range(20, 0, -1)))
        self.assertGreater(fetch.call_count, 6)
        self.assertTrue(all(call.kwargs.get('page_size') == 3 for call in fetch.call_args_list))
        with patch.object(business_export, 'BATCH_SIZE', 3), patch.object(project, 'get_tasks', wraps=project.get_tasks) as fetch:
            response = self.export('/api/projects/1/tasks/export', columns=['progress'], sort=[{'colId': 'progress', 'sort': 'desc'}])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(workbook_rows(response.content)), 21)
        self.assertGreater(fetch.call_count, 6)
        self.assertTrue(all(call.kwargs.get('page_size') == 3 for call in fetch.call_args_list))

    def _concurrent_batch_export(self, kind, mutation):
        from app.services import project
        self.context['permissions'].append('business:data:all')
        if kind == 'project':
            model, service, route, column = PmsProject, 'get_project_list', '/api/projects/export', 'budget'
            def new_row(i):
                return model(id=i, archive_id=1, project_code=f'P{i:05}', project_name=f'项目{i}',
                             dept_id=1, pm_id=1, status=1, budget=i)
        elif kind == 'archive':
            model, service, route, column = PmsProjectArchive, 'get_archive_list', '/api/projects/archives/export', 'project_code'
            def new_row(i):
                return model(id=i, project_code=f'A{i:05}', project_name=f'档案{i}', manager_id=1,
                             business_product_line_id=1, status=1, is_enabled=1)
        else:
            model, service, route, column = PmsTask, 'get_tasks', '/api/projects/1/tasks/export', 'task_name'
            self.db.get(PmsTask, 21).project_id = 1
            def new_row(i):
                return model(id=i, project_id=1, task_name=f'任务{i:05}', assignee_id=1, status=1, progress=0, sort=i % 7)
        self.db.add_all(new_row(i) for i in range(22, 601))
        self.db.commit()
        expected = {str(int(row.budget)) if kind == 'project' else str(getattr(row, column))
                    for row in self.db.query(model).all()}
        original = getattr(project, service)
        calls = 0
        def reader(*args, **kwargs):
            nonlocal calls
            result = original(*args, **kwargs)
            items = result if kind == 'task' else result['items']
            calls += 1
            if calls == 1:
                if mutation == 'delete':
                    self.db.delete(self.db.get(model, items[0].id))
                else:
                    self.db.add(new_row(601))
                self.db.commit()
            return result
        with patch.object(project, service, side_effect=reader):
            response = self.export(route, columns=[column])
        self.assertEqual(response.status_code, 200, response.text)
        values = [row['A'] for row in workbook_rows(response.content)[1:]]
        self.assertEqual(len(values), 600)
        self.assertEqual(len(set(values)), 600)
        self.assertEqual(set(values), expected)

    def test_project_cursor_survives_delete_from_first_batch(self):
        self._concurrent_batch_export('project', 'delete')

    def test_archive_cursor_survives_delete_from_first_batch(self):
        self._concurrent_batch_export('archive', 'delete')

    def test_task_cursor_survives_delete_from_first_batch(self):
        self._concurrent_batch_export('task', 'delete')

    def test_project_cursor_excludes_later_insert(self):
        self._concurrent_batch_export('project', 'insert')

    def test_archive_cursor_excludes_later_insert(self):
        self._concurrent_batch_export('archive', 'insert')

    def test_task_cursor_excludes_later_insert(self):
        self._concurrent_batch_export('task', 'insert')

    def test_task_default_sort_and_id_order_survives_internal_batching(self):
        from app.services import business_export, project
        for task in self.db.query(PmsTask).filter_by(project_id=1):
            task.sort = (21 - task.id) // 2
        self.db.commit()
        expected = [row.task_name for row in project.get_tasks(self.db, 1, scope_context=self.context)]
        with patch.object(business_export, 'BATCH_SIZE', 3):
            response = self.export('/api/projects/1/tasks/export', columns=['task_name'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['A'] for row in workbook_rows(response.content)[1:]], expected)
        for payload in ({'columns': ['id']}, {'filters': [condition('id', 'equals', 1)]},
                        {'column_filters': [{'field': 'id', 'mode': 'values', 'values': [1]}]},
                        {'sort': [{'colId': 'id', 'sort': 'asc'}]}, {'columns': ['_source_id']}):
            response = self.export('/api/projects/1/tasks/export', **{'columns': ['task_name'], **payload})
            self.assertEqual(response.status_code, 422)

    def test_project_and_archive_default_order_matches_list_services(self):
        from app.services import business_export, project
        self.db.get(PmsProjectArchive, 1).project_code = 'Z01'
        self.db.commit()
        for kind, route, service in (
            ('project', '/api/projects/export', project.get_project_list),
            ('archive', '/api/projects/archives/export', project.get_archive_list),
        ):
            with self.subTest(kind=kind):
                expected = [row.project_code for row in service(self.db, page_size=50, scope_context=self.context)['items']]
                with patch.object(business_export, 'BATCH_SIZE', 3):
                    response = self.export(route, columns=['project_code'])
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row['A'] for row in workbook_rows(response.content)[1:]], expected)

    def test_export_cursor_queries_compile_to_mssql_top_without_offset(self):
        from sqlalchemy import event
        from sqlalchemy.dialects import mssql
        from app.services import project
        statements = []
        def capture(state):
            statement = state.statement
            if statement._limit_clause is not None and statement._order_by_clauses:
                statements.append(str(statement.compile(dialect=mssql.dialect(), compile_kwargs={'literal_binds': True})))
        event.listen(self.db, 'do_orm_execute', capture)
        try:
            common = dict(scope_context=self.context, export_scan=True, before_id=21, upper_id=21, page_size=3)
            project.get_project_list(self.db, **common)
            project.get_archive_list(self.db, **common)
            project.get_tasks(self.db, 1, **common)
        finally:
            event.remove(self.db, 'do_orm_execute', capture)
        self.assertEqual(len(statements), 3)
        for statement in statements:
            self.assertIn('TOP 3', statement)
            self.assertIn('.id < 21', statement)
            self.assertIn('.id <= 21', statement)
            self.assertIn('.id DESC', statement)
            self.assertNotIn('OFFSET', statement)

    def test_internal_cursor_id_not_allowed_in_any_public_export_field(self):
        for route, columns in [('/api/projects/export', ['project_code']),
                               ('/api/projects/archives/export', ['project_code']),
                               ('/api/projects/1/tasks/export', ['task_name'])]:
            for field in ('id', '_source_id'):
                for payload in ({'columns': [field]}, {'filters': [condition(field, 'equals', 1)]},
                                {'column_filters': [{'field': field, 'mode': 'values', 'values': [1]}]},
                                {'sort': [{'colId': field, 'sort': 'asc'}]}):
                    with self.subTest(route=route, field=field, payload=payload):
                        self.assertEqual(self.export(route, **{'columns': columns, **payload}).status_code, 422)

    def test_more_than_twenty_thousand_rows_with_bounded_reader(self):
        from app.services import project
        size = 20001
        def reader(db, *, page_size, before_id=None, upper_id=None, **kwargs):
            ceiling = min(before_id - 1 if before_id is not None else size, upper_id or size)
            items = [SimpleNamespace(id=i, model_dump=lambda i=i: {'id': i, 'project_code': f'P{i:05}', 'budget': i - 1})
                     for i in range(ceiling, max(ceiling - page_size, 0), -1)]
            return {'items': items, 'total': size}
        with patch.object(project, 'get_project_list', side_effect=reader) as fetch:
            response = self.export(columns=['budget'], sort=[{'colId': 'budget', 'sort': 'desc'}])
        self.assertEqual(response.status_code, 200)
        rows = workbook_rows(response.content)
        self.assertEqual(len(rows), size + 1)
        self.assertEqual((rows[1]['A'], rows[-1]['A']), ('20000', '0'))
        self.assertTrue(all(call.kwargs['page_size'] <= 500 for call in fetch.call_args_list))

    def test_dynamic_policy_and_empty_scope_still_validate_query(self):
        from app.models.field_policy import SysBusinessFieldPolicy
        self.db.add(SysBusinessFieldPolicy(module_code='project_progress', field_key='order_year', visible=False, list_available=False))
        self.db.commit()
        self.assertEqual(self.export(columns=['sheet:order_year']).status_code, 422)
        self.assertEqual(self.export(filters=[condition('order_year', 'equals', 2025)]).status_code, 422)
        self.context['product_line_ids'] = []
        self.assertEqual(self.export(filters=[condition('does_not_exist', 'equals', 'x')]).status_code, 422)

    def test_invalid_label_query_is_422_not_server_error(self):
        response = self.export(filters=[condition('status', 'contains', True)])
        self.assertEqual(response.status_code, 422)

    def test_archive_computed_sync_state_query_and_sort(self):
        archive = self.db.get(PmsProjectArchive, 1)
        archive.erp_synced = 1
        archive.erp_sync_status = None
        self.db.commit()
        response = self.export('/api/projects/archives/export', columns=['project_code', 'erp_sync_state'],
                               filters=[condition('erp_sync_state', 'contains', '成功')],
                               sort=[{'colId': 'erp_sync_state', 'sort': 'asc'}])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(workbook_rows(response.content)[1], {'A': 'A01', 'B': '同步成功'})

    def test_archive_policy_hidden_product_line_does_not_crash(self):
        from app.services import project
        metadata = project.get_archive_field_metadata(self.db)
        metadata['items'] = [{**item, 'visible': False} if item['field_key'] == 'product_line_id' else item
                             for item in metadata['items']]
        with patch.object(project, 'get_archive_field_metadata', return_value=metadata):
            response = self.export('/api/projects/archives/export', columns=['project_code'])
            self.assertEqual(response.status_code, 200)
            response = self.export('/api/projects/archives/export', columns=['product_line_id'])
            self.assertEqual(response.status_code, 422)

    def test_current_and_historical_sync_policy_labels(self):
        for id_, value in enumerate(('auto', 'manual', 'conditional'), 1):
            self.db.get(PmsProjectArchive, id_).erp_sync_policy = value
        self.db.commit()
        response = self.export('/api/projects/archives/export', columns=['erp_sync_policy'],
                               filters=[condition('project_code', 'reference', [1, 2, 3])],
                               sort=[{'colId': 'project_code', 'sort': 'asc'}])
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['A'] for row in workbook_rows(response.content)[1:]], ['自动同步', '仅手动同步', '条件同步'])

    def test_archive_unknown_query_properties_fail_closed(self):
        response = self.export('/api/projects/archives/export', columns=['project_code'],
                               filters=[condition('project_code', 'contains', 'A', ignored='must-not-drop')])
        self.assertEqual(response.status_code, 422)

        response = self.export('/api/projects/archives/export', columns=['project_code'],
                               column_filters=[{'field': 'project_code', 'mode': 'values', 'values': ['A01'], 'ignored': 1}])
        self.assertEqual(response.status_code, 422)

    def test_project_sort_null_order_matches_grid_default(self):
        self.db.get(PmsProject, 1).budget = None
        self.db.commit()
        response = self.export(columns=['project_code', 'budget'], sort=[{'colId': 'budget', 'sort': 'asc'}])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(workbook_rows(response.content)[1]['A'], 'P01')
        response = self.export(columns=['project_code', 'budget'], sort=[{'colId': 'budget', 'sort': 'desc'}])
        self.assertEqual(workbook_rows(response.content)[-1]['A'], 'P01')

    def test_archive_sort_contract_computed_sync_state_and_text_literals(self):
        prefixes = ['=1+1', '+1+1', '-1+1', '@SUM(A1:A2)']
        for id_, prefix in enumerate(prefixes, 1):
            archive = self.db.get(PmsProjectArchive, id_)
            archive.project_name = prefix
            archive.erp_sync_status = 'success' if id_ == 1 else None
        self.db.commit()
        response = self.export('/api/projects/archives/export', parameters={'enabled': 'all'},
                               columns=['project_name', 'erp_sync_state', 'created_by_name'],
                               filters=[condition('project_code', 'reference', [1, 2, 3, 4])],
                               sort=[{'colId': 'project_code', 'sort': 'asc'}])
        self.assertEqual(response.status_code, 200, response.text)
        rows = workbook_rows(response.content)
        self.assertEqual([row['A'] for row in rows[1:]], prefixes)
        self.assertEqual(rows[1]['B'], '同步成功')
        self.assertEqual(rows[2]['B'], '未同步')


if __name__ == '__main__':
    unittest.main()
