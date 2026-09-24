import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.database import Base
import app.models.init_db
from app.models.project import PmsProjectArchive,PmsProject
from app.models.erp_task import ErpSyncTask
from app.models.user import SysUser
from app.models.product_line import SysProductLine
from app.services.enum_registry import initialize_enum_definitions
class ImportContract(unittest.TestCase):
    def setUp(self):
        self.e=create_engine("sqlite://");Base.metadata.create_all(self.e);self.db=Session(self.e)
        initialize_enum_definitions(self.db)
        u=SysUser(username="import-test",password_hash="x",real_name="测试",status=1);self.db.add(u);self.db.commit()
        self.uid=u.id
        self.scope={"user_id":u.id,"data_scope":4,"permissions":["business:data:all"]}
        self.payload={"rows":[{"source_id":"S1-R2","source_sheet":"主机A","source_row":2,"values":{"project_code":"A-1","project_name":None,"quantity":"2.5"}},{"source_id":"S1-R3","source_sheet":"主机A","source_row":3,"values":{"project_code":"A-2","project_name":"有名"}}]}
    def tearDown(self):self.db.close();self.e.dispose()
    def test_preview_and_apply_idempotent(self):
        from app.services.offline_archive_import import preview_import,apply_import
        self.assertEqual(preview_import(self.db,self.payload,self.scope)["total"],2)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),0)
        first=apply_import(self.db,self.payload,self.uid,self.scope)
        self.assertEqual(first["created"],2)
        self.assertEqual(apply_import(self.db,self.payload,self.uid,self.scope)["created"],0)
        self.assertEqual(self.db.query(ErpSyncTask).count(),0)
        for a in self.db.query(PmsProjectArchive):
            self.assertEqual(a.erp_sync_policy,"manual")
            self.assertIsNone(a.business_product_line_id)
    def test_collision_blocks_entire_batch(self):
        from app.services.offline_archive_import import apply_import
        self.db.add(PmsProjectArchive(project_code="a-2",project_name="已存在"));self.db.commit()
        with self.assertRaises(HTTPException):apply_import(self.db,self.payload,self.uid,self.scope)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),1)
    def test_empty_authority_rejected(self):
        from app.services.offline_archive_import import preview_import
        with self.assertRaises(HTTPException):preview_import(self.db,self.payload,{"permissions":[]})
    def test_duplicate_normalized_code_rejected(self):
        from app.services.offline_archive_import import preview_import
        self.payload["rows"][1]["values"]["project_code"]=" a-1 "
        self.assertTrue(preview_import(self.db,self.payload,self.scope)["errors"])
    def test_policy_and_origin_cannot_be_spoofed(self):
        from app.services.offline_archive_import import preview_import
        self.payload["rows"][0]["values"]["erp_sync_policy"]="auto"
        self.assertTrue(preview_import(self.db,self.payload,self.scope)["errors"])
    def test_safe_rollback_and_modified_block(self):
        from app.services.offline_archive_import import apply_import,rollback_import
        result=apply_import(self.db,self.payload,self.uid,self.scope)
        a=self.db.query(PmsProjectArchive).first();a.customer="有人维护";self.db.commit()
        with self.assertRaises(HTTPException):rollback_import(self.db,result["batch_id"],self.uid,self.scope)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),2)
    def test_rollback_untouched(self):
        from app.services.offline_archive_import import apply_import,rollback_import
        result=apply_import(self.db,self.payload,self.uid,self.scope)
        self.assertEqual(rollback_import(self.db,result["batch_id"],self.uid,self.scope)["deleted"],2)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),0)
    def test_same_source_cannot_be_imported_after_code_edit(self):
        from app.services.offline_archive_import import apply_import,preview_import
        apply_import(self.db,self.payload,self.uid,self.scope)
        for a in self.db.query(PmsProjectArchive):a.project_code += "-edited"
        self.db.commit()
        self.payload["rows"][0]["values"]["customer"]="Changed"
        self.assertTrue(preview_import(self.db,self.payload,self.scope)["errors"])
    def test_disabled_line_assignment_rejected(self):
        from app.services.offline_archive_import import apply_import,assign_product_line
        apply_import(self.db,self.payload,self.uid,self.scope)
        line=SysProductLine(source_key="kingdee",organization_id=99,organization_code="99",organization_name="测试",display_name="禁用",name_key="disabled",is_enabled=0)
        self.db.add(line);self.db.commit()
        a=self.db.query(PmsProjectArchive).first()
        with self.assertRaises(HTTPException):
            assign_product_line(self.db,{"product_line_id":line.id,"items":[{"id":a.id,"expected_updated_at":a.updated_at.isoformat()}]},self.uid,self.scope)
        self.db.refresh(a);self.assertIsNone(a.business_product_line_id)
    def test_mid_batch_failure_rolls_back_rows_batch_and_logs(self):
        from unittest.mock import patch
        from app.services import offline_archive_import as service
        from app.models.archive_import import ArchiveImportBatch,ArchiveImportRow
        from app.models.operation_log import SysOperationLog
        original=service._log
        count=0
        def fail_second(*args,**kwargs):
            nonlocal count
            count+=1
            if count==2:raise RuntimeError("isolated simulated failure")
            return original(*args,**kwargs)
        with patch.object(service,"_log",side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                service.apply_import(self.db,self.payload,self.uid,self.scope)
        for model in (PmsProjectArchive,ArchiveImportBatch,ArchiveImportRow,SysOperationLog):
            self.assertEqual(self.db.query(model).count(),0)
    def test_source_retrieval_obeys_archive_scope(self):
        from app.services.offline_archive_import import apply_import,get_import_source
        apply_import(self.db,self.payload,self.uid,self.scope)
        a=self.db.query(PmsProjectArchive).first()
        source=get_import_source(self.db,a.id,self.scope)
        self.assertEqual(source["source_id"],"S1-R2")
        self.assertEqual(source["source_row"],2)
        with self.assertRaises(HTTPException):
            get_import_source(self.db,a.id,{"user_id":999,"data_scope":1,"permissions":[],"product_line_ids":[]})
    def test_assign_checks_version_and_keeps_manual(self):
        from app.services.offline_archive_import import apply_import,assign_product_line
        apply_import(self.db,self.payload,self.uid,self.scope)
        line=SysProductLine(source_key="kingdee",organization_id=9,organization_code="9",organization_name="测试",display_name="测试",name_key="nine")
        self.db.add(line);self.db.commit()
        a=self.db.query(PmsProjectArchive).first()
        with self.assertRaises(HTTPException):assign_product_line(self.db,{"product_line_id":line.id,"items":[{"id":a.id,"expected_updated_at":"2000-01-01"}]},self.uid,self.scope)
        self.db.refresh(a)
        result=assign_product_line(self.db,{"product_line_id":line.id,"items":[{"id":a.id,"expected_updated_at":a.updated_at.isoformat()}]},self.uid,self.scope)
        self.assertEqual(result["updated"],1)
        self.assertEqual(self.db.query(ErpSyncTask).count(),0)
if __name__=="__main__":unittest.main()
