"""Offline archive behavior in isolated databases; no ERP requests."""
import sys, unittest
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.database import Base
import app.models.init_db
from app.models.project import PmsProjectArchive
from app.models.erp_task import ErpSyncTask
from app.models.user import SysUser
from app.models.product_line import SysProductLine
from app.schemas.project import ArchiveUpdate, ArchiveCreate
from app.services import project
from app.services.enum_registry import initialize_enum_definitions

class OfflineArchiveContract(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine)
        initialize_enum_definitions(self.db)
        self.user=SysUser(username="offline-test", real_name="测试",password_hash="x",status=1)
        self.db.add(self.user);self.db.commit()
        self.scope={"user_id":self.user.id,"data_scope":4,"permissions":["business:data:all"]}
    def tearDown(self):
        self.db.close();self.engine.dispose()
    def archive(self, **kw):
        obj=PmsProjectArchive(project_code="AS-TEST-1",project_name="原名称",
            data_origin="offline_initial",**kw)
        self.db.add(obj);self.db.commit();return obj
    def test_business_fields_and_policy(self):
        self.assertIn("erp_sync_policy",PmsProjectArchive.__table__.columns)
        for k in ("archive_category","customer_full_name","machine_model","quantity","quantity_unit",
                  "sales_company","legacy_archive_status","legacy_code_date","legacy_updated_date","delivery_note","remarks"):
            self.assertIn(k,PmsProjectArchive.__table__.columns)
            self.assertIn(k,ArchiveUpdate.model_fields)
    def test_manual_rename_does_not_queue(self):
        a=self.archive();a.erp_sync_policy="manual"
        result=project.update_archive(self.db,a.id,ArchiveUpdate(project_name="新名称"),self.user.id,scope_context=self.scope)
        self.assertFalse(result["sync_queued"])
        self.assertEqual(self.db.query(ErpSyncTask).count(),0)
    def test_empty_legacy_name_can_edit_customer(self):
        a=self.archive();a.project_name=None;a.erp_sync_policy="manual";self.db.commit()
        project.update_archive(self.db,a.id,ArchiveUpdate(customer="客户"),self.user.id,scope_context=self.scope)
        self.assertIsNone(a.project_name)
        self.assertEqual(a.customer,"客户")
    def test_category_write_rejected(self):
        a=self.archive()
        with self.assertRaises(HTTPException) as caught:
            project.update_archive(self.db,a.id,ArchiveUpdate(product_category=1),self.user.id,scope_context=self.scope)
        self.assertEqual(caught.exception.status_code,422)
    def test_implicit_manual_enqueue_rejected(self):
        from app.services.erp_queue import enqueue
        a=self.archive();a.erp_sync_policy="manual"
        with self.assertRaises(HTTPException):
            enqueue(self.db,a,self.user.id)
        self.assertEqual(self.db.query(ErpSyncTask).count(),0)
    def test_explicit_sync_requires_target_and_name(self):
        from app.services.offline_archive import request_archive_sync
        a=self.archive();a.erp_sync_policy="manual"
        with self.assertRaises(HTTPException):
            request_archive_sync(self.db,a.id,self.user.id,self.scope)
        self.assertEqual(self.db.query(ErpSyncTask).count(),0)
    def test_role_category_write_rejected(self):
        from app.schemas.rbac import RoleCreate
        from app.services.rbac import create_role
        with self.assertRaises(HTTPException) as caught:
            create_role(self.db,RoleCreate(role_name="旧授权",role_code="old-cat",product_category_ids="1"),self.user.id)
        self.assertEqual(caught.exception.status_code,422)
        self.assertIn("产品类别已停用",str(caught.exception.detail))
    def test_manual_explicit_sync_preserves_policy(self):
        from app.services.offline_archive import request_archive_sync
        line=SysProductLine(source_key="kingdee",organization_id=100,organization_code="100",organization_name="测试",display_name="测试",name_key="line")
        self.db.add(line);self.db.commit()
        a=self.archive();a.erp_sync_policy="manual";a.business_product_line_id=line.id;self.db.commit()
        result=request_archive_sync(self.db,a.id,self.user.id,self.scope)
        self.assertIn("task_id",result)
        self.assertEqual(self.db.query(ErpSyncTask).count(),1)
        self.assertEqual(a.erp_sync_policy,"manual")
    def test_offline_enums_public_and_retired_category_hidden(self):
        from app.services.enum_registry import MANAGED_ENUM_CODES
        self.assertIn("archive_machine_model",MANAGED_ENUM_CODES)
        self.assertNotIn("product_category",MANAGED_ENUM_CODES)
    def test_legacy_raw_address_does_not_block_customer_edit(self):
        a=self.archive();a.erp_sync_policy="manual";a.address_detail="原台账交付地点";self.db.commit()
        project.update_archive(self.db,a.id,ArchiveUpdate(customer="新客户"),self.user.id,scope_context=self.scope)
        self.assertEqual(a.address_detail,"原台账交付地点")
    def test_new_quantity_filter_before_pagination(self):
        from app.services.project import get_archive_list
        a=self.archive();a.quantity=2.5;self.db.commit()
        result=get_archive_list(self.db,filters=[{"field":"quantity","operator":"equals","value":2.5}])
        self.assertEqual(result["total"],1)
    def test_upgrade_idempotent_default(self):
        from app.services.offline_archive_migration import upgrade_offline_archive
        e=create_engine("sqlite://")
        with e.begin() as c:
            c.execute(text("CREATE TABLE pms_project_archive (id INTEGER PRIMARY KEY, project_code NVARCHAR(32))"))
            c.execute(text("INSERT INTO pms_project_archive VALUES (1, 'OLD')"))
        upgrade_offline_archive(e);upgrade_offline_archive(e)
        with e.connect() as c:
            self.assertEqual(c.execute(text("SELECT erp_sync_policy FROM pms_project_archive")).scalar(),"auto")
        e.dispose()
if __name__=="__main__":unittest.main()
