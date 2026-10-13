"""Existing menu-level view permission must satisfy same-module action dependencies."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
from app.models.rbac import SysMenu, SysRole, SysRoleMenu, SysUserRole
from app.models.user import SysUser
from app.schemas.rbac import RoleCreate, RoleUpdate
from app.services.rbac import normalize_role_menu_ids, create_role, update_role, get_role_menu_ids, RECOVERY_PERMISSIONS

class MenuViewContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([
            SysMenu(id=10, menu_name='问题提报', menu_type='C', permission_code='feedback:view', status=1),
            SysMenu(id=11, parent_id=10, menu_name='新增', menu_type='B', permission_code='feedback:add', status=1),
            SysMenu(id=12, parent_id=10, menu_name='补充', menu_type='B', permission_code='feedback:supplement', status=1),
            SysMenu(id=13, parent_id=10, menu_name='处理', menu_type='B', permission_code='feedback:handle', status=1),
            SysMenu(id=14, parent_id=10, menu_name='重试', menu_type='B', permission_code='feedback:notification:retry', status=1),
            SysMenu(id=20, menu_name='旧模块', menu_type='C', permission_code='project:archive:list', status=1),
            SysMenu(id=21, parent_id=20, menu_name='查看', menu_type='B', permission_code='project:archive:view', status=1),
            SysMenu(id=22, parent_id=20, menu_name='编辑', menu_type='B', permission_code='project:archive:edit', status=1),
        ])
        self.db.commit()
    def tearDown(self):
        self.db.close(); self.engine.dispose()
    def test_create_supplement_add_only_existing_parent_view(self):
        self.assertEqual(normalize_role_menu_ids(self.db,[11,12]),[10,11,12])
    def test_old_button_view_remains_supported(self):
        self.assertEqual(normalize_role_menu_ids(self.db,[22]),[20,21,22])
    def test_view_only_never_grants_actions(self):
        self.assertEqual(normalize_role_menu_ids(self.db,[10]),[10])
    def test_nested_retry_requires_explicit_selection(self):
        self.assertEqual(normalize_role_menu_ids(self.db,[14]),[10,14])
    def test_disabled_parent_view_is_rejected(self):
        self.db.get(SysMenu,10).status=0;self.db.commit()
        with self.assertRaises(HTTPException): normalize_role_menu_ids(self.db,[11])
    def test_wrong_module_parent_view_is_rejected(self):
        self.db.get(SysMenu,10).permission_code='unrelated:view';self.db.commit()
        with self.assertRaises(HTTPException): normalize_role_menu_ids(self.db,[11])
    def test_create_and_update_persist_only_explicit_feedback_actions(self):
        self.db.add(SysRole(id=50, role_name='恢复管理员', role_code='fixture_recovery', status=1))
        self.db.add(SysUser(id=50, username='fixture_admin', real_name='恢复管理员', password_hash='fixture-only', status=1))
        self.db.add(SysUserRole(user_id=50, role_id=50))
        for index, code in enumerate(sorted(RECOVERY_PERMISSIONS), 100):
            self.db.add(SysMenu(id=index, menu_name=code, menu_type='B', permission_code=code, status=1))
            self.db.add(SysRoleMenu(role_id=50, menu_id=index))
        self.db.commit()
        result=create_role(self.db,RoleCreate(role_name='提报人',role_code='fixture_submitter',menu_ids=[11,12]))
        self.assertEqual(get_role_menu_ids(self.db,result['id']),[10,11,12])
        update_role(self.db,result['id'],RoleUpdate(menu_ids=[10]))
        self.assertEqual(get_role_menu_ids(self.db,result['id']),[10])

if __name__=='__main__': unittest.main()
