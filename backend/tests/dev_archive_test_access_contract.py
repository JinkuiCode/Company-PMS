"""Minimum acceptance configuration without broadening existing role templates."""
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
import app.models.init_db
from app.models.user import SysUser
from app.models.rbac import SysDept,SysRole,SysMenu,SysRoleMenu,SysUserRole
from app.models.product_line import SysProductLine
from app.models.operation_log import SysOperationLog
from app.services.authorization import build_authorization_context


class TestAccessContract(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://');Base.metadata.create_all(self.engine);self.db=Session(self.engine)
        self.operator=SysUser(username='ael',real_name='管理员',password_hash='keep-owner',email='owner@example.com',status=1)
        self.head=SysUser(username='A000645',real_name='负责人',password_hash='keep-head',email='head@example.com',status=1)
        self.db.add_all([self.operator,self.head]);self.db.flush()
        department=SysDept(dept_name='信息化',leader_id=self.head.id,status=1)
        self.db.add(department);self.db.flush();self.head.dept_id=department.id
        self.db.add(SysProductLine(source_key='kingdee',organization_id=123,organization_code='123',organization_name='组织',display_name='12吋Bench',name_key='test'))
        original=SysRole(role_code='existing',role_name='原角色',data_scope=4,status=1)
        self.db.add(original);self.db.flush();self.original_id=original.id
        self.db.add(SysUserRole(user_id=self.operator.id,role_id=original.id))
        for code in ('system:user:view','system:user:edit','system:role:view','system:role:edit','system:role:add'):
            menu=SysMenu(menu_name=code,menu_type='C',permission_code=code,status=1)
            self.db.add(menu);self.db.flush();self.db.add(SysRoleMenu(role_id=original.id,menu_id=menu.id))
        parent=SysMenu(menu_name='项目管理',menu_type='M',status=1);self.db.add(parent);self.db.flush()
        page=SysMenu(menu_name='项目档案',menu_type='C',parent_id=parent.id,permission_code='project:archive:list',status=1)
        self.db.add(page);self.db.flush()
        for code in ('project:archive:view','project:archive:edit'):
            self.db.add(SysMenu(menu_name=code,menu_type='B',parent_id=page.id,permission_code=code,status=1))
        self.db.commit()
        self.original_grants=[(row.role_id,row.menu_id) for row in self.db.query(SysRoleMenu)]
    def tearDown(self):self.db.close();self.engine.dispose()
    def test_only_approved_grants_and_department_change_are_written_and_logged(self):
        from scripts.dev_archive_test_access import configure_test_access
        result=configure_test_access(self.db)
        context=build_authorization_context(self.db,self.head.id)
        self.assertEqual(set(context['permissions']),{'project:archive:list','project:archive:view','project:archive:edit'})
        self.assertEqual(context['data_scope'],2)
        self.assertEqual(context['product_line_ids'],[result['line_id']])
        self.db.refresh(self.operator);self.db.refresh(self.head)
        self.assertEqual(self.operator.dept_id,self.head.dept_id)
        self.assertEqual(self.operator.password_hash,'keep-owner');self.assertEqual(self.head.password_hash,'keep-head')
        self.assertEqual(self.operator.email,'owner@example.com');self.assertEqual(self.head.email,'head@example.com')
        self.assertEqual([(row.role_id,row.menu_id) for row in self.db.query(SysRoleMenu).filter_by(role_id=self.original_id)],self.original_grants)
        count=self.db.query(SysOperationLog).count()
        self.assertEqual(count,3)
        configure_test_access(self.db)
        self.assertEqual(self.db.query(SysOperationLog).count(),count)


if __name__=='__main__':unittest.main()
