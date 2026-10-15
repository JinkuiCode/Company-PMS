"""Display names use the same live grants without requiring ERP availability."""
import unittest
from unittest.mock import patch
from fastapi import HTTPException
import product_line_api_contract as fixture
from app.models.product_line import SysProductLine, SysRoleProductLine
from app.models.user import SysUser
from app.models.rbac import SysRole, SysUserRole, SysMenu, SysRoleMenu
from app.services.authorization import get_current_user_context
from app.core.security import user_access_token


class ProductLineLabels(unittest.TestCase):
    setUp = fixture.ProductLineAPI.setUp
    tearDown = fixture.ProductLineAPI.tearDown

    def lines(self):
        rows = [SysProductLine(source_key='kingdee', organization_id=i,
            organization_code=str(i), organization_name=str(i), display_name=name,
            name_key=name, is_enabled=int(i != 2))
            for i, name in [(1, '12吋Bench'), (2, '历史产品线'), (3, '其他范围')]]
        self.db.add_all(rows)
        self.db.commit()
        return rows

    def test_names_stay_scoped_and_keep_disabled_history_without_erp(self):
        lines = self.lines()
        self.ctx.update(permissions=['project:archive:view'], product_line_ids=[r.id for r in lines[:2]])
        with patch('app.api.product_lines.get_organization', side_effect=HTTPException(503, '目录不可用')) as source:
            response = self.client.get('/api/product-lines/labels')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), {'label_map': {str(r.id): r.display_name for r in lines[:2]}})
            source.assert_not_called()
            # Display recovery must not silently make unverified choices selectable.
            self.assertEqual(self.client.get('/api/product-lines/options').status_code, 503)

    def test_all_data_is_explicit_and_empty_scope_still_returns_nothing(self):
        lines = self.lines()
        self.ctx.update(permissions=['project:archive:view'], product_line_ids=[])
        response = self.client.get('/api/product-lines/labels')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'label_map': {}})
        self.ctx['permissions'].append('business:data:all')
        response = self.client.get('/api/product-lines/labels')
        self.assertEqual(response.json(), {'label_map': {str(r.id): r.display_name for r in lines}})

    def test_all_data_does_not_grant_page_access(self):
        self.ctx.update(permissions=['business:data:all'], product_line_ids=[1])
        self.assertEqual(self.client.get('/api/product-lines/labels').status_code, 403)

    def test_same_token_observes_scope_and_button_revocation(self):
        line = self.lines()[0]
        del self.client.app.dependency_overrides[get_current_user_context]
        user = SysUser(username='label-user', real_name='名称验收', password_hash='fixture-only', status=1)
        role = SysRole(role_code='operator', role_name='读取范围', data_scope=4, status=1)
        node = SysMenu(menu_name='档案查看', permission_code='project:archive:view', menu_type='B', status=1)
        self.db.add_all([user, role, node]); self.db.flush()
        self.db.add_all([SysUserRole(user_id=user.id, role_id=role.id),
            SysRoleMenu(role_id=role.id, menu_id=node.id), SysRoleProductLine(role_id=role.id, product_line_id=line.id)])
        self.db.commit()
        headers = {'Authorization': 'Bearer ' + user_access_token(user, 'oa')}
        self.assertEqual(self.client.get('/api/product-lines/labels', headers=headers).json(),
            {'label_map': {str(line.id): line.display_name}})
        self.db.query(SysRoleProductLine).delete(); self.db.commit()
        self.assertEqual(self.client.get('/api/product-lines/labels', headers=headers).json(), {'label_map': {}})
        self.db.query(SysRoleMenu).delete(); self.db.commit()
        self.assertEqual(self.client.get('/api/product-lines/labels', headers=headers).status_code, 403)


if __name__ == '__main__':
    unittest.main()
