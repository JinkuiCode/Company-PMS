import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from app.services.authorization import enforce_permission
from app.services.dashboard import get_dashboard_stats
import product_line_project_scope_contract as scope_fixture


class DashboardScope(unittest.TestCase):
    setUp = scope_fixture.ProjectScope.setUp
    tearDown = scope_fixture.ProjectScope.tearDown

    def prepare(self):
        for index, item in enumerate(self.projects):
            item.end_date = date.today() + timedelta(days=3)
            item.status = 1
            self.tasks[index].progress = (index + 1) * 10
        self.db.commit()

    def test_all_sections_share_line_scope(self):
        self.prepare()
        result = get_dashboard_stats(self.db, self.ctx)
        self.assertEqual(result['total_projects'], 1)
        self.assertEqual(result['total_tasks'], 1)
        self.assertEqual(result['avg_progress'], 10.0)
        self.assertEqual(result['status_distribution'],
                         {'ongoing': 1, 'finished': 0, 'paused': 0})
        self.assertEqual(result['dept_distribution'],
                         [{'dept_name': '部门1', 'count': 1}])
        expected = {self.projects[0].id}
        for field in ('nearing_deadline', 'recent_projects'):
            self.assertEqual({row['id'] for row in result[field]}, expected)

    def test_empty_scope_never_reveals_projects(self):
        self.prepare()
        contexts = [None, {},
                    {**self.ctx, 'product_line_ids': []},
                    {**self.ctx, 'product_line_ids': [], 'role_codes': ['admin']},
                    {**self.ctx, 'data_scope': 2, 'dept_id': None},
                    {**self.ctx, 'data_scope': 3, 'dept_id': None},
                    {**self.ctx, 'data_scope': 2, 'dept_id': 2}]
        for context in contexts:
            with self.subTest(context=context):
                result = get_dashboard_stats(self.db, context)
                self.assertEqual(result['total_projects'], 0)
                self.assertEqual(result['total_tasks'], 0)
                self.assertEqual(result['avg_progress'], 0.0)
                self.assertEqual(result['dept_distribution'], [])
                self.assertEqual(result['nearing_deadline'], [])
                self.assertEqual(result['recent_projects'], [])

    def test_person_and_department_intersect_with_lines(self):
        self.prepare()
        self.projects[0].pm_id = self.users[1].id
        self.projects[0].dept_id = 2
        self.db.commit()
        for changes in ({'data_scope': 1}, {'data_scope': 2, 'dept_id': 1},
                        {'data_scope': 3, 'dept_id': 1}):
            result = get_dashboard_stats(self.db, {**self.ctx, **changes})
            self.assertEqual(result['total_projects'], 0)
        self.assertEqual(get_dashboard_stats(self.db, self.ctx)['total_projects'], 1)

    def test_revocable_all_data_grant_does_not_grant_action(self):
        self.prepare()
        context = {**self.ctx, 'dept_id': None, 'data_scope': 2,
                   'product_line_ids': [], 'permissions': ['business:data:all']}
        self.assertEqual(get_dashboard_stats(self.db, context)['total_projects'], 4)
        with self.assertRaises(HTTPException) as error:
            enforce_permission(context, 'dashboard:view')
        self.assertEqual(error.exception.status_code, 403)
        context['permissions'] = []
        self.assertEqual(get_dashboard_stats(self.db, context)['total_projects'], 0)


class DashboardApiScope(unittest.TestCase):
    tearDown = scope_fixture.ProjectScope.tearDown

    def setUp(self):
        from unittest.mock import patch
        from sqlalchemy import create_engine
        from sqlalchemy.pool import StaticPool
        # Only adapt the fixture's SQLite transport for FastAPI's worker thread.
        with patch.object(scope_fixture, 'create_engine', lambda *args: create_engine(
                'sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)):
            scope_fixture.ProjectScope.setUp(self)

    def test_actual_route_reloads_grants_and_user_status_per_request(self):
        from fastapi import FastAPI, APIRouter
        from fastapi.testclient import TestClient
        from app.core.database import get_db
        from app.core.security import user_access_token
        from app.models.rbac import SysRole, SysMenu, SysRoleMenu, SysUserRole
        from app.models.product_line import SysRoleProductLine
        from main import app as real_app

        role = SysRole(role_code='dashboard-fixture', role_name='首页测试', data_scope=4, status=1)
        menu = SysMenu(menu_name='首页查看', menu_type='B', permission_code='dashboard:view', status=1)
        self.db.add_all([role, menu]); self.db.flush()
        self.db.add_all([SysUserRole(user_id=self.users[0].id, role_id=role.id),
                         SysRoleMenu(role_id=role.id, menu_id=menu.id),
                         SysRoleProductLine(role_id=role.id, product_line_id=self.lines[0].id)])
        self.db.commit()
        app = FastAPI()
        route = next(route for route in real_app.routes if route.path == '/api/dashboard/stats')
        app.include_router(APIRouter(routes=[route]))
        app.dependency_overrides[get_db] = lambda: self.db
        # Only the database is isolated; use a synthetic JWT with real authentication/authorization.
        token = user_access_token(self.users[0], 'oa')
        with TestClient(app) as client:
            client.headers['Authorization'] = f'Bearer {token}'
            result = client.get('/api/dashboard/stats')
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['total_projects'], 1)
            self.db.query(SysRoleProductLine).filter_by(role_id=role.id).delete(); self.db.commit()
            result = client.get('/api/dashboard/stats')
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['total_projects'], 0)
            all_data = SysMenu(menu_name='全部业务数据', menu_type='B', permission_code='business:data:all', status=1)
            self.db.add(all_data); self.db.flush()
            self.db.add(SysRoleMenu(role_id=role.id, menu_id=all_data.id)); self.db.commit()
            self.assertEqual(client.get('/api/dashboard/stats').json()['total_projects'], 4)
            self.db.query(SysRoleMenu).filter_by(role_id=role.id, menu_id=all_data.id).delete(); self.db.commit()
            self.assertEqual(client.get('/api/dashboard/stats').json()['total_projects'], 0)
            self.db.add(SysRoleMenu(role_id=role.id, menu_id=all_data.id))
            self.db.query(SysRoleMenu).filter_by(role_id=role.id, menu_id=menu.id).delete(); self.db.commit()
            self.assertEqual(client.get('/api/dashboard/stats').status_code, 403)
            self.db.add(SysRoleMenu(role_id=role.id, menu_id=menu.id))
            self.users[0].status = 0; self.db.commit()
            self.assertEqual(client.get('/api/dashboard/stats').status_code, 403)


if __name__ == '__main__':
    unittest.main()
