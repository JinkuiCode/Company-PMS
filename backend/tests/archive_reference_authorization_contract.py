"""Reference candidates and results use live RBAC and intersected data scope."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DB_DIALECT'] = 'sqlite'
os.environ['SQLITE_DB_PATH'] = str(Path(tempfile.mkdtemp()) / 'reference-access.db')

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.database import Base, engine, SessionLocal, get_db
import app.models.init_db
from app.api.projects import router
from app.core.security import user_access_token
from app.models.user import SysUser
from app.models.rbac import SysRole, SysUserRole, SysMenu, SysRoleMenu
from app.models.product_line import SysProductLine, SysRoleProductLine
from app.models.project import PmsProjectArchive
from app.services.project import get_archive_list

Base.metadata.create_all(engine)

def condition(field, operator, value):
    return dict(field=field, operator=operator, value=value, schemaVersion=2)

with SessionLocal() as db:
    users = [SysUser(username=f'fixture-{i}', real_name=f'人员{i}', password_hash='test-only',
                     dept_id=dept, must_change_password=False)
             for i, dept in enumerate((11, 11, 22))]
    lines = [SysProductLine(source_key='fixture', organization_id=i, organization_code=str(i),
                            organization_name=f'组织{i}', display_name=f'产品线{i}', name_key=f'line-{i}')
             for i in (1, 2)]
    role = SysRole(role_code='reference-fixture', role_name='引用查询测试', data_scope=2)
    permission = SysMenu(menu_name='档案查看', permission_code='project:archive:view', menu_type='B')
    db.add_all([*users, *lines, role, permission])
    db.flush()
    archives = [PmsProjectArchive(project_code=f'REF-{i}', project_name='同名档案',
                                  manager_id=users[manager].id, business_product_line_id=line,
                                  is_enabled=enabled)
                for i, (manager, line, enabled) in enumerate([
                    (0, lines[0].id, 1), (1, lines[0].id, 0),
                    (2, lines[0].id, 1), (0, lines[1].id, 1), (0, None, 1)])]
    db.add_all(archives)
    db.add_all([SysUserRole(user_id=users[0].id, role_id=role.id),
                SysRoleMenu(role_id=role.id, menu_id=permission.id),
                SysRoleProductLine(role_id=role.id, product_line_id=lines[0].id)])
    db.commit()
    archive_ids = [a.id for a in archives]
    context = dict(permissions=['project:archive:view'], user_id=users[0].id, dept_id=11,
                   product_line_ids=[lines[0].id], data_scope=2)
    reference = condition('project_name', 'reference', archive_ids)
    for field in ('project_code', 'project_name'):
        actual = get_archive_list(db, enabled=None, filters=[{**reference, 'field': field}], scope_context=context)
        assert {a.id for a in actual['items']} == set(archive_ids[:2]), '部门与产品线必须取交集'
    own = get_archive_list(db, enabled=None, filters=[reference], scope_context={**context, 'data_scope': 1})
    assert [a.id for a in own['items']] == archive_ids[:1], '本人范围不能因引用扩大'
    role_id = role.id
    line_id = lines[0].id
    # A synthetic session for isolated fixtures, never an existing account token.
    token = user_access_token(users[0], 'oa')

app = FastAPI()
app.include_router(router)

def test_db():
    with SessionLocal() as db:
        yield db

app.dependency_overrides[get_db] = test_db
params = [dict(enabled='all', keyword='REF'),
          dict(enabled='all', filters=json.dumps([reference]))]
with TestClient(app) as client:
    client.headers['Authorization'] = f'Bearer {token}'
    for query in params:
        response = client.get('/api/projects/archives/list', params=query)
        assert response.status_code == 200, response.text
        assert {a['id'] for a in response.json()['items']} == set(archive_ids[:2])
    with SessionLocal() as db:
        db.query(SysRoleProductLine).filter_by(role_id=role_id).delete()
        db.commit()
    for query in params:
        response = client.get('/api/projects/archives/list', params=query)
        assert response.status_code == 200 and response.json()['total'] == 0, '撤销产品线后立即收紧候选与结果'
    with SessionLocal() as db:
        db.add(SysRoleProductLine(role_id=role_id, product_line_id=line_id))
        db.query(SysRoleMenu).filter_by(role_id=role_id).delete()
        db.commit()
    for query in params:
        assert client.get('/api/projects/archives/list', params=query).status_code == 403, '撤销页面权限后原会话也必须拒绝'

print('archive reference authorization passed: person/department + line intersection, live session revocation')
