"""Role landing-page selection, validation and additive upgrade."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.database import Base
from app.models.rbac import SysRole, SysMenu, SysRoleMenu
from app.models.user import SysUser
from app.models.operation_log import SysOperationLog
from app.models.rbac import SysUserRole
from app.schemas.rbac import RoleUpdate
from app.services.rbac import update_role, RECOVERY_PERMISSIONS

assert hasattr(SysRole, 'home_menu_id'), 'role home menu must be persisted'
from app.services.role_home import resolve_home_path, validate_role_home, upgrade_role_home

engine = create_engine('sqlite://')
Base.metadata.create_all(engine)
with Session(engine) as db:
    a = SysMenu(id=1, menu_name='档案', menu_type='C', path='/project/archive', permission_code='project:archive:view', status=1, visible=1, sort=1)
    b = SysMenu(id=2, menu_name='进度', menu_type='C', path='/project/list', permission_code='project:list:view', status=1, visible=1, sort=2)
    r1 = SysRole(id=1, role_name='一', role_code='one', home_menu_id=1, home_priority=10, status=1)
    r2 = SysRole(id=2, role_name='二', role_code='two', home_menu_id=2, home_priority=20, status=1)
    db.add_all([a,b,r1,r2]); db.flush()
    db.add_all([SysRoleMenu(role_id=1,menu_id=1),SysRoleMenu(role_id=2,menu_id=2)]);db.commit()
    perms={'project:archive:view','project:list:view'}
    assert resolve_home_path(db,[r1,r2],perms)=='/project/list'
    r1.home_priority=20
    assert resolve_home_path(db,[r2,r1],perms)=='/project/archive'
    r1.status=0
    assert resolve_home_path(db,[r1,r2],perms)=='/project/list'
    b.status=0
    assert resolve_home_path(db,[r1,r2],perms)=='/403'
    r1.status=1
    assert resolve_home_path(db,[r1,r2],perms)=='/project/archive'
    assert resolve_home_path(db,[r1],set())=='/403'
    validate_role_home(db,1,[1])
    for home,ids in [(2,[1]),(99,[1])]:
        try: validate_role_home(db,home,ids)
        except HTTPException as error: assert error.status_code==422
        else: raise AssertionError('invalid home must be rejected')
    a.path='https://example.com'
    assert resolve_home_path(db,[r1],perms)=='/403'
    a.path='/project/archive'
    b.status=1
    # Preserve the real recovery guard while exercising the normal role-save service.
    admin = SysUser(username='recovery', real_name='recovery', password_hash='test', status=1)
    recovery = SysRole(id=100,role_name='recovery',role_code='recovery',status=1)
    db.add_all([admin,recovery]);db.flush()
    for i, code in enumerate(sorted(RECOVERY_PERMISSIONS), 100):
        db.add(SysMenu(id=i,menu_name=code,menu_type='B',permission_code=code,status=1))
        db.add(SysRoleMenu(role_id=100,menu_id=i))
    db.add(SysUserRole(user_id=admin.id,role_id=100));db.commit()
    update_role(db,1,RoleUpdate(home_menu_id=2,home_priority=50,menu_ids=[1,2]),operator_id=admin.id)
    db.refresh(r1)
    assert (r1.home_menu_id,r1.home_priority)==(2,50)
    log=db.query(SysOperationLog).order_by(SysOperationLog.id.desc()).first()
    assert log and 'home_menu_id' in str(log.diff_data)
    try:
        update_role(db,1,RoleUpdate(home_menu_id=99,home_priority=60),operator_id=admin.id)
    except HTTPException as error: assert error.status_code==422
    else: raise AssertionError('invalid configured home must fail')
    db.refresh(r1)
    assert (r1.home_menu_id,r1.home_priority)==(2,50)
    update_role(db,1,RoleUpdate(menu_ids=[1]),operator_id=admin.id)
    db.refresh(r1)
    assert r1.home_menu_id is None
    assert resolve_home_path(db,[r1],perms)=='/project/archive'

    # Fallback follows directory order before each page's sibling order.
    db.add_all([SysMenu(id=10,menu_name='第一组',menu_type='M',sort=0),
                SysMenu(id=20,menu_name='第二组',menu_type='M',sort=1)])
    a.parent_id=10; a.sort=9
    b.parent_id=20; b.sort=0
    db.add_all([SysRoleMenu(role_id=1,menu_id=i) for i in [2,10,20]])
    r1.home_menu_id=None
    db.commit()
    assert resolve_home_path(db,[r1],perms)=='/project/archive'

old=create_engine('sqlite://')
with old.begin() as c:
    c.execute(text('CREATE TABLE sys_role (id INTEGER PRIMARY KEY, role_name TEXT)'))
    c.execute(text("INSERT INTO sys_role VALUES (1,'original')"))
upgrade_role_home(old);upgrade_role_home(old)
assert {'home_menu_id','home_priority'} <= {c['name'] for c in inspect(old).get_columns('sys_role')}
with old.connect() as c: assert c.execute(text('SELECT role_name,home_menu_id,home_priority FROM sys_role')).one()==('original',None,0)
print('role home contract passed')
