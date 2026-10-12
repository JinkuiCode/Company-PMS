"""Export nodes migrate once without granting data scope or replenishing grants."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.models.init_db as initializer
from app.core.database import Base
from app.models.rbac import SysMenu, SysRole, SysRoleMenu
from app.models.user import SysUser
from app.services.database_revision import CURRENT_DATABASE_REVISION


class BusinessExportUpgradeContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.db = self.sessions()
        self.db.add(SysUser(username='fixture', real_name='测试', password_hash='unused'))
        self.roles = {}
        for code in ('admin', 'business_admin', 'operator', 'custom'):
            role = SysRole(role_name=code, role_code=code, data_scope=1)
            self.db.add(role)
            self.db.flush()
            self.roles[code] = role.id
        self.db.add(SysMenu(id=1, parent_id=0, menu_name='系统管理', menu_type='M'))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def upgrade(self):
        with patch.object(initializer, 'engine', self.engine), patch.object(initializer, 'SessionLocal', self.sessions):
            initializer.init_db()
        self.db.expire_all()

    def test_nodes_once_revocation_and_disabled_state_survive_repeat(self):
        self.upgrade()
        codes = ('project:archive:export', 'project:list:export')
        nodes = self.db.query(SysMenu).filter(SysMenu.permission_code.in_(codes)).all()
        self.assertEqual(len(nodes), 2, 'missing dedicated business export permission nodes')
        for node in nodes:
            self.assertEqual((node.parent_id, node.menu_type), (22 if 'archive' in node.permission_code else 21, 'B'))
            self.assertEqual({r.role_id for r in self.db.query(SysRoleMenu).filter_by(menu_id=node.id)},
                             {self.roles['admin']})
        node = nodes[0]
        node.status = 0
        self.db.query(SysRoleMenu).filter_by(menu_id=node.id, role_id=self.roles['admin']).delete()
        self.db.commit()
        self.upgrade()
        self.assertEqual(self.db.get(SysMenu, node.id).status, 0)
        self.assertIsNone(self.db.query(SysRoleMenu).filter_by(menu_id=node.id, role_id=self.roles['admin']).first())
        self.assertEqual(self.db.query(SysMenu).filter(SysMenu.permission_code.in_(codes)).count(), 2)

    def test_revision_has_explicit_business_export_upgrade(self):
        self.assertEqual(CURRENT_DATABASE_REVISION, '2026-10-12-parameter-secret-01')


if __name__ == '__main__':
    unittest.main()
