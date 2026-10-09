import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
import app.models.init_db
from app.models.rbac import SysMenu, SysRole, SysRoleMenu


class MigrationContract(unittest.TestCase):
    def test_menu_grants_once_and_preserves_revocation(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.stock_detail_migration'))
        from app.services.stock_detail_migration import initialize_stock_detail_report
        engine = create_engine('sqlite://')
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(SysRole(id=1, role_name='管理员', role_code='admin'))
            db.commit()
            initialize_stock_detail_report(db)
            node = db.query(SysMenu).filter_by(permission_code='report:stock-detail:export').one()
            self.assertEqual(db.query(SysRoleMenu).filter_by(role_id=1, menu_id=node.id).count(), 1)
            db.query(SysRoleMenu).filter_by(role_id=1, menu_id=node.id).delete()
            db.commit()
            initialize_stock_detail_report(db)
            self.assertEqual(db.query(SysRoleMenu).filter_by(role_id=1, menu_id=node.id).count(), 0)
            page = db.query(SysMenu).filter_by(permission_code='report:stock-detail:list').one()
            self.assertEqual(page.path, '/reports/stock-detail')

    def test_revision_and_field_catalog_include_report(self):
        from app.services.database_revision import CURRENT_DATABASE_REVISION
        self.assertEqual(CURRENT_DATABASE_REVISION, '2026-10-09-archive-02')
        from app.services.field_catalog import build_field_catalog
        fields = [row for row in build_field_catalog() if row['module'] == 'stock_detail_report']
        self.assertEqual(len(fields), 15)
        self.assertTrue(all(not row['editable'] for row in fields))


if __name__ == '__main__':
    unittest.main()
