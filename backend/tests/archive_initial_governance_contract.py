"""Historical imports remain a restricted exception, never a public creation flag."""
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.database import Base
import app.models.init_db
from app.models.user import SysUser
from app.models.rbac import SysRole,SysMenu,SysRoleMenu,SysUserRole
from app.models.parameter import SysParameter
from app.models.project import PmsProjectArchive
from app.services.kingdee_initial_archive import insert_initial_archives
from app.services.parameter import ARCHIVE_INITIALIZATION_ENABLED


class InitialGovernanceContract(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://');Base.metadata.create_all(self.engine);self.db=Session(self.engine)
        self.user=SysUser(username='importer',real_name='期初操作人',password_hash='fixture',status=1)
        self.role=SysRole(role_code='importer',role_name='期初角色',status=1,data_scope=4)
        self.db.add_all([self.user,self.role]);self.db.flush()
        self.db.add(SysUserRole(user_id=self.user.id,role_id=self.role.id))
        for code in ('project:archive:import','business:data:all'):
            menu=SysMenu(menu_name=code,permission_code=code,menu_type='B',status=1)
            self.db.add(menu);self.db.flush();self.db.add(SysRoleMenu(role_id=self.role.id,menu_id=menu.id))
        self.db.commit()
        self.rows=[{'project_code':'INITIAL-NEW','project_name':None,'source_id':'source'}]
    def tearDown(self):self.db.close();self.engine.dispose()
    def test_enabled_initial_import_marks_historical_gaps(self):
        self.assertEqual(insert_initial_archives(self.db,self.rows,operator_id=self.user.id),1)
        self.db.commit()
        archive=self.db.query(PmsProjectArchive).one()
        self.assertTrue(archive.governance_legacy)
        self.assertIsNone(archive.manager_id)
    def test_disabled_initialization_rejects_even_authorized_importer(self):
        self.db.add(SysParameter(code=ARCHIVE_INITIALIZATION_ENABLED,value_text='false'))
        self.db.commit()
        with self.assertRaises(HTTPException):insert_initial_archives(self.db,self.rows,operator_id=self.user.id)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),0)
    def test_missing_import_permission_or_actor_cannot_create_legacy_archive(self):
        self.db.query(SysRoleMenu).delete();self.db.commit()
        for actor in (None,self.user.id):
            with self.subTest(actor=actor),self.assertRaises(HTTPException):
                insert_initial_archives(self.db,self.rows,operator_id=actor)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),0)


if __name__=='__main__':unittest.main()
