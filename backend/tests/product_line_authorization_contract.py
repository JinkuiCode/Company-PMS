"""Explicit organization grants never inherit the legacy unlimited convention."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
import app.models.init_db
from app.models.product_line import SysProductLine, SysRoleProductLine
from app.models.rbac import SysRole, SysUserRole, SysMenu, SysRoleMenu
from app.models.user import SysUser
from app.services.authorization import build_authorization_context, get_me_context


class ProductLineAuthorization(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = SysUser(username='test', real_name='测试', password_hash='not-a-real-password')
        self.roles = [SysRole(role_code='admin', role_name='管理员', data_scope=4),
                      SysRole(role_code='operator', role_name='操作员', data_scope=1)]
        self.lines = [SysProductLine(source_key='kingdee', organization_id=org,
                      organization_code=str(org), organization_name=name, display_name=name,
                      name_key=name) for org, name in ((100, '甲'), (200, '乙'))]
        self.db.add_all([self.user, *self.roles, *self.lines])
        self.db.flush()
        self.db.add_all([SysUserRole(user_id=self.user.id, role_id=r.id) for r in self.roles])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def context(self):
        return build_authorization_context(self.db, self.user.id)

    def grant(self, role, line):
        self.db.add(SysRoleProductLine(role_id=role.id, product_line_id=line.id))
        self.db.commit()

    def test_admin_and_unrestricted_legacy_category_do_not_grant_product_lines(self):
        self.assertEqual(self.context()['product_line_ids'], [])
        self.assertEqual(self.context()['data_scope'], 4)

    def test_union_and_disabled_role(self):
        self.grant(self.roles[0], self.lines[0])
        self.grant(self.roles[1], self.lines[1])
        self.assertEqual(self.context()['product_line_ids'], [x.id for x in self.lines])
        self.roles[0].status = 0
        self.db.commit()
        self.assertEqual(self.context()['product_line_ids'], [self.lines[1].id])
        self.assertEqual(self.context()['data_scope'], 1)

    def test_next_context_reflects_revocation(self):
        self.grant(self.roles[0], self.lines[0])
        self.assertEqual(self.context()['product_line_ids'], [self.lines[0].id])
        self.db.query(SysRoleProductLine).delete()
        self.db.commit()
        self.assertEqual(self.context()['product_line_ids'], [])

    def test_disabled_line_retains_history_but_cannot_be_selected(self):
        from app.services.product_line_scope import require_line_access
        self.grant(self.roles[0], self.lines[0])
        self.lines[0].is_enabled = 0
        self.db.commit()
        self.assertEqual(require_line_access(self.db, self.context(), self.lines[0].id).id, self.lines[0].id)
        with self.assertRaises(HTTPException) as caught:
            require_line_access(self.db, self.context(), self.lines[0].id, selectable=True)
        self.assertEqual(caught.exception.status_code, 422)

    def test_missing_context_and_unauthorized_ids_fail_closed(self):
        from app.services.product_line_scope import require_line_access
        for context in (None, {}, self.context()):
            with self.assertRaises(HTTPException) as caught:
                require_line_access(self.db, context, self.lines[0].id)
            self.assertEqual(caught.exception.status_code, 404)

    def test_password_change_session_has_no_line_grants(self):
        self.grant(self.roles[0], self.lines[0])
        ctx = get_me_context({'user_id': self.user.id, 'must_change_password': True}, self.db)
        self.assertEqual(ctx['product_line_ids'], [])

    def recovery_permissions(self):
        from app.services.rbac import RECOVERY_PERMISSIONS
        for code in RECOVERY_PERMISSIONS:
            menu = SysMenu(menu_name=code, permission_code=code, menu_type='B')
            self.db.add(menu)
            self.db.flush()
            self.db.add(SysRoleMenu(role_id=self.roles[0].id, menu_id=menu.id))
        self.db.commit()

    def test_role_save_and_response_include_grants_and_empty_list_revokes(self):
        from app.services.rbac import update_role, get_role_list
        from app.schemas.rbac import RoleUpdate
        self.recovery_permissions()
        update_role(self.db, self.roles[1].id, RoleUpdate(product_line_ids=[self.lines[1].id]))
        self.assertEqual(self.context()['product_line_ids'], [self.lines[1].id])
        returned = next(r for r in get_role_list(self.db) if r.id == self.roles[1].id)
        self.assertEqual(returned.product_line_ids, [self.lines[1].id])
        update_role(self.db, self.roles[1].id, RoleUpdate(product_line_ids=[]))
        self.assertEqual(self.context()['product_line_ids'], [])

    def test_invalid_grant_rolls_back_role_fields_and_relationships(self):
        from app.services.rbac import update_role
        from app.schemas.rbac import RoleUpdate
        self.recovery_permissions()
        self.grant(self.roles[1], self.lines[0])
        with self.assertRaises(HTTPException) as caught:
            update_role(self.db, self.roles[1].id, RoleUpdate(role_name='不应保存', product_line_ids=[999]))
        self.assertEqual(caught.exception.status_code, 422)
        self.db.refresh(self.roles[1])
        self.assertEqual(self.roles[1].role_name, '操作员')
        self.assertEqual(self.context()['product_line_ids'], [self.lines[0].id])

    def test_new_disabled_grant_rejected_but_existing_can_be_kept(self):
        from app.services.rbac import update_role
        from app.schemas.rbac import RoleUpdate
        self.recovery_permissions()
        self.grant(self.roles[1], self.lines[0])
        for line in self.lines:
            line.is_enabled = 0
        self.db.commit()
        update_role(self.db, self.roles[1].id, RoleUpdate(product_line_ids=[self.lines[0].id]))
        with self.assertRaises(HTTPException):
            update_role(self.db, self.roles[1].id, RoleUpdate(product_line_ids=[self.lines[1].id]))

    def test_me_exposes_explicit_line_ids(self):
        from app.services.auth import get_current_user
        self.grant(self.roles[1], self.lines[0])
        info = get_current_user(self.db, self.user.id, self.context())
        self.assertEqual(info.product_line_ids, [self.lines[0].id])


if __name__ == '__main__':
    unittest.main()
