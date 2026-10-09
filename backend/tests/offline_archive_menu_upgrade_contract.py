"""Upgrade a report-bearing database without reusing its menu identities."""
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import app.models.init_db as initializer
from app.core.database import Base
from app.models.rbac import SysMenu, SysRole, SysRoleMenu
from app.models.user import SysUser


class MenuUpgradeContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.db = self.sessions()
        self.db.add(SysUser(username="fixture", real_name="测试用户", password_hash="unused", status=1))
        self.roles = {}
        for code in ("admin", "business_admin", "operator", "report-only"):
            role = SysRole(role_name=code, role_code=code, data_scope=4, status=1)
            self.db.add(role); self.db.flush(); self.roles[code] = role.id
        self.db.add_all([
            SysMenu(id=1, parent_id=0, menu_name="系统管理", menu_type="M"),
            SysMenu(id=2, parent_id=0, menu_name="项目管理", menu_type="M"),
            SysMenu(id=21, parent_id=2, menu_name="项目进度", menu_type="C", path="/project/list", permission_code="project:list"),
            SysMenu(id=22, parent_id=2, menu_name="项目档案", menu_type="C", path="/project/archive", permission_code="project:archive:list"),
            SysMenu(id=227, parent_id=0, menu_name="报表中心", menu_type="M", icon="DataAnalysis", sort=3),
            SysMenu(id=228, parent_id=227, menu_name="采购进度查询", menu_type="C", path="/reports/purchase-progress", permission_code="report:purchase:list", icon="Document", sort=1),
            SysMenu(id=229, parent_id=228, menu_name="查看", menu_type="B", permission_code="report:purchase:view", sort=1),
            SysMenu(id=230, parent_id=228, menu_name="导出", menu_type="B", permission_code="report:purchase:export", sort=2),
        ])
        self.db.add(SysRoleMenu(role_id=self.roles["report-only"], menu_id=228))
        self.db.commit()

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def upgrade(self):
        with patch.object(initializer, "engine", self.engine), patch.object(initializer, "SessionLocal", self.sessions):
            initializer.init_db()
        self.db.expire_all()

    def test_existing_reports_and_role_grants_survive_new_archive_buttons(self):
        before = [(m.id, m.parent_id, m.menu_name, m.menu_type, m.permission_code, m.path, m.icon, m.status)
                  for m in self.db.query(SysMenu).filter(SysMenu.id.between(227,230)).order_by(SysMenu.id)]
        self.upgrade()
        after = [(m.id, m.parent_id, m.menu_name, m.menu_type, m.permission_code, m.path, m.icon, m.status)
                 for m in self.db.query(SysMenu).filter(SysMenu.id.between(227,230)).order_by(SysMenu.id)]
        self.assertEqual(after, before)
        self.assertEqual([g.menu_id for g in self.db.query(SysRoleMenu).filter_by(role_id=self.roles["report-only"])], [228])
        buttons = self.db.query(SysMenu).filter(SysMenu.permission_code.in_(["project:archive:import", "project:archive:assign-line"])).all()
        self.assertEqual(len(buttons), 2)
        for button in buttons:
            self.assertNotIn(button.id, [227,228,229,230])
            self.assertEqual((button.parent_id, button.menu_type, button.path), (22,"B",None))
            granted = {g.role_id for g in self.db.query(SysRoleMenu).filter_by(menu_id=button.id)}
            self.assertEqual(granted, {self.roles["admin"], self.roles["business_admin"]})
        import_button = next(b for b in buttons if b.permission_code == "project:archive:import")
        import_button.status = 0
        self.db.query(SysRoleMenu).filter_by(role_id=self.roles["admin"], menu_id=import_button.id).delete()
        self.db.commit()
        self.upgrade()
        self.assertEqual(self.db.get(SysMenu, import_button.id).status, 0)
        self.assertIsNone(self.db.query(SysRoleMenu).filter_by(role_id=self.roles["admin"], menu_id=import_button.id).first())
        self.assertEqual(self.db.query(SysMenu).filter_by(permission_code="project:archive:import").count(), 1)

    def test_existing_archive_permission_reuses_its_identity_without_grant_replenishment(self):
        button = SysMenu(parent_id=22, menu_name="期初导入", menu_type="B", permission_code="project:archive:import", status=0, sort=7)
        self.db.add(button); self.db.commit(); previous_id = button.id
        self.upgrade()
        node = self.db.query(SysMenu).filter_by(permission_code="project:archive:import").one()
        self.assertEqual((node.id,node.status), (previous_id,0))
        self.assertEqual(self.db.query(SysRoleMenu).filter_by(menu_id=previous_id).count(), 0)


if __name__ == "__main__":
    unittest.main()
