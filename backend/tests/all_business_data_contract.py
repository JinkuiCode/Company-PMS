"""Explicit all-data grants are independent of role names and action grants."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.business_data_scope import ALL_DATA_SCOPE
from product_line_project_scope_contract import ProjectScope
from product_line_authorization_contract import ProductLineAuthorization


class AllDataScope(ProjectScope):
    def test_all_data_write_scope_keeps_action_permission_separate(self):
        from app.services import project
        ctx = dict(self.ctx, permissions=['business:data:all'], data_scope=1, dept_id=None)
        project._ensure_archive_assignment_allowed(self.db, scope_context=ctx, manager_id=self.users[1].id, product_category=None)
        project._ensure_project_assignment_allowed(self.db, scope_context=ctx, pm_id=self.users[1].id, dept_id=None, product_category=None)
    def test_all_data_includes_unassigned_and_orphan_without_department(self):
        from app.services import project
        from app.models.project import PmsProject
        ctx = dict(self.ctx, permissions=['business:data:all'], product_line_ids=[], data_scope=1, dept_id=None)
        self.assertEqual(project.get_archive_list(self.db, scope_context=ctx)['total'], 3)
        self.assertEqual(project._apply_project_scope(self.db.query(PmsProject), self.db, ctx).count(), 4)

    def test_report_scope_and_export_signature_are_explicit(self):
        from app.api.purchase_reports import project_scope
        from app.services.purchase_reader import scope_clause
        from app.services.report_export_jobs import scope_signature
        ctx = dict(self.ctx, permissions=['business:data:all'], product_line_ids=[])
        self.assertIs(project_scope(self.db, ctx), ALL_DATA_SCOPE)
        self.assertEqual(scope_clause('a.FNUMBER', ALL_DATA_SCOPE), ('1=1', []))
        self.assertEqual(scope_clause('a.FNUMBER', None), ('1=0', []))
        self.assertEqual(scope_clause('a.FNUMBER', []), ('1=0', []))
        self.assertNotEqual(scope_signature(self.db, ctx, 'purchase'), scope_signature(self.db, self.ctx, 'purchase'))

    def test_inventory_all_keeps_user_filters(self):
        from app.services.inventory_reader import effective_organizations, where_clause, InventoryQuery
        query = InventoryQuery(keyword='abc')
        self.assertIs(effective_organizations(query, ALL_DATA_SCOPE), ALL_DATA_SCOPE)
        self.assertEqual(effective_organizations(query, None), [])
        sql, params = where_clause(query, ALL_DATA_SCOPE)
        self.assertNotIn('1=0', sql)
        self.assertIn('%abc%', params)
        self.assertEqual(effective_organizations(InventoryQuery(organization_id=123), ALL_DATA_SCOPE), [123])


class AllDataAuthorization(ProductLineAuthorization):
    def test_migration_grants_once_and_revocation_remains_effective(self):
        from app.services.all_data_migration import initialize_all_business_data
        from app.models.rbac import SysRoleMenu
        from app.services.authorization import enforce_permission
        from fastapi import HTTPException
        initialize_all_business_data(self.db)
        ctx = self.context()
        self.assertIn('business:data:all', ctx['permissions'])
        from app.models.rbac import SysMenu
        from app.services.rbac import normalize_role_menu_ids
        node = self.db.query(SysMenu).filter_by(permission_code='business:data:all').one()
        self.assertEqual(normalize_role_menu_ids(self.db, [node.id]), [node.id])
        self.roles[0].status = 0
        self.db.commit()
        self.assertNotIn('business:data:all', self.context()['permissions'])
        self.roles[0].status = 1
        self.db.commit()
        with self.assertRaises(HTTPException):
            enforce_permission(ctx, 'project:archive:delete')
        self.db.query(SysRoleMenu).delete()
        self.db.commit()
        initialize_all_business_data(self.db)
        self.assertNotIn('business:data:all', self.context()['permissions'])


if __name__ == '__main__':
    unittest.main()
