"""Approved reconciliation uses real transactions; no ERP calls."""
import copy, importlib, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from offline_archive_import_contract import ImportContract
from fastapi import HTTPException
from sqlalchemy import create_engine,inspect,text
from app.models.project import PmsProjectArchive,PmsProject,ErpSyncLog
from app.models.erp_task import ErpSyncTask
from app.models.archive_import import ArchiveImportBatch,ArchiveImportRow
from app.models.operation_log import SysOperationLog
from app.models.dict import SysDict,SysDictItem
from app.services import offline_archive_import as service
from app.services.operation_log import serialize_model

class MergeContract(ImportContract):
    def existing(self,**kw):
        a=PmsProjectArchive(project_code='A-1',project_name='线上名称',customer='线上客户',data_origin='kingdee_initial',erp_synced=1,erp_sync_policy='auto',**kw)
        self.db.add(a);self.db.commit();return a
    def bind(self):
        self.assertTrue(hasattr(service,'bind_existing_targets'),'预检需绑定服务器目标快照')
        return service.bind_existing_targets(self.db,self.payload)
    def test_merge_preserves_identity_name_line_and_erp(self):
        a=self.existing();self.payload['rows'][0]['values'].update(project_name='线下冲突名称',customer='线下客户',remarks='补充备注')
        before=serialize_model(a);payload=self.bind()
        result=service.apply_import(self.db,payload,self.uid,self.scope)
        self.assertEqual((result['created'],result['updated']),(1,1))
        self.db.refresh(a)
        for key in ['id','project_code','project_name','customer','data_origin','erp_synced','erp_sync_policy','business_product_line_id','created_by','created_at']:
            self.assertEqual(serialize_model(a)[key],before[key],key)
        self.assertEqual(a.remarks,'补充备注');self.assertEqual(self.db.query(ErpSyncTask).count(),0)
    def test_merge_fills_empty_name_and_does_not_overwrite_zero(self):
        a=self.existing(quantity=0);a.project_name=' ';a.customer=None;self.db.commit()
        self.payload['rows'][0]['values'].update(project_name='补齐名称',customer='补齐客户')
        service.apply_import(self.db,self.bind(),self.uid,self.scope);self.db.refresh(a)
        self.assertEqual(a.project_name,'补齐名称');self.assertEqual(a.customer,'补齐客户');self.assertEqual(a.quantity,0)
    def test_preview_counts_only_actual_patches(self):
        self.existing(quantity=0);self.payload['rows'][0]['values']['quantity']='9'
        result=service.preview_import(self.db,self.bind(),self.scope)
        self.assertEqual((result['created'],result['updated'],result['unchanged']),(1,0,1))
    def test_modified_after_preview_rejected_atomically(self):
        a=self.existing();payload=self.bind();a.customer='其他用户修改';self.db.commit()
        with self.assertRaises(HTTPException):service.apply_import(self.db,payload,self.uid,self.scope)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),1);self.assertEqual(self.db.query(ArchiveImportBatch).count(),0)
    def test_new_code_collision_after_preview_is_not_silently_merged(self):
        self.existing();payload=self.bind();self.db.add(PmsProjectArchive(project_code='A-2',project_name='并发新增'));self.db.commit()
        with self.assertRaises(HTTPException):service.apply_import(self.db,payload,self.uid,self.scope)
        self.assertEqual(self.db.query(ArchiveImportBatch).count(),0)
    def test_deleted_or_renamed_target_not_recreated(self):
        a=self.existing();payload=self.bind();a.project_code='A-1-edited';self.db.commit()
        with self.assertRaises(HTTPException):service.apply_import(self.db,payload,self.uid,self.scope)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),1)
    def test_same_serial_on_matched_record_allowed(self):
        self.existing(serial_no='SERIAL-1');self.payload['rows'][0]['values']['serial_no']='SERIAL-1'
        self.assertFalse(service.preview_import(self.db,self.bind(),self.scope)['errors'])
    def test_shared_serial_collision_blocks(self):
        self.existing();self.db.add(PmsProjectArchive(project_code='OTHER',project_name='其他档案',serial_no='SERIAL-1'));self.db.commit()
        self.payload['rows'][0]['values']['serial_no']='SERIAL-1'
        self.assertTrue(service.preview_import(self.db,self.bind(),self.scope)['errors'])
    def test_different_incoming_serial_does_not_overwrite_existing(self):
        a=self.existing(serial_no='KEEP');self.payload['rows'][0]['values']['serial_no']='DISCARD'
        self.payload['rows'][1]['values']['serial_no']='DISCARD'
        result=service.apply_import(self.db,self.bind(),self.uid,self.scope);self.db.refresh(a)
        self.assertEqual(a.serial_no,'KEEP');self.assertEqual(result['created'],1)
    def test_reupload_after_applied_is_idempotent(self):
        self.existing();self.payload['rows'][0]['values']['remarks']='补充'
        first=service.apply_import(self.db,self.bind(),self.uid,self.scope)
        second=service.apply_import(self.db,self.bind(),self.uid,self.scope)
        self.assertEqual(first['batch_id'],second['batch_id']);self.assertEqual(second['created'],0)
        self.assertEqual(self.db.query(ArchiveImportBatch).count(),1)
    def test_overlapping_identical_request_returns_completed_batch(self):
        from unittest.mock import patch
        from sqlalchemy.orm import Session
        self.existing();self.payload['rows'][0]['values']['remarks']='并发补充'
        payload=self.bind();original=service.claim_archive_lifecycle_rows
        completed={};overlap=False
        def claim(*args,**kwargs):
            nonlocal overlap
            if not overlap:
                overlap=True
                with Session(self.db.bind) as other:
                    completed.update(service.apply_import(other,payload,self.uid,self.scope))
            return original(*args,**kwargs)
        with patch.object(service,'claim_archive_lifecycle_rows',side_effect=claim):
            result=service.apply_import(self.db,payload,self.uid,self.scope)
        self.assertEqual(result['batch_id'],completed['batch_id'])
        self.assertEqual(result['created'],0)
        self.assertEqual(self.db.query(ArchiveImportBatch).count(),1)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),2)
    def test_busy_existing_target_rejected(self):
        self.existing(erp_sync_status='review')
        self.assertTrue(service.preview_import(self.db,self.bind(),self.scope)['errors'])
    def test_unknown_additional_targets_rejected(self):
        self.existing();payload=self.bind();payload['targets']['not-a-source']=next(iter(payload['targets'].values()))
        self.assertTrue(service.preview_import(self.db,payload,self.scope)['errors'])
    def test_restore_preexisting_record_even_with_existing_business_links(self):
        a=self.existing();before=serialize_model(a);self.payload['rows'][0]['values']['remarks']='导入备注'
        self.db.add(ErpSyncLog(source_id=a.id,action='create',status='success'));self.db.commit()
        result=service.apply_import(self.db,self.bind(),self.uid,self.scope)
        row=self.db.query(ArchiveImportRow).filter_by(archive_id=a.id).one()
        self.assertEqual(row.operation,'updated');self.assertIn('remarks',row.before_values)
        undone=service.rollback_import(self.db,result['batch_id'],self.uid,self.scope)
        self.db.refresh(a);self.assertEqual(a.remarks,None);self.assertEqual(a.project_name,before['project_name'])
        self.assertEqual(a.erp_synced,1);self.assertEqual((undone['deleted'],undone['restored']),(1,1))
        self.assertIsNone(service.get_import_source(self.db,a.id,self.scope))
    def test_later_edit_blocks_both_restore_and_delete(self):
        a=self.existing();self.payload['rows'][0]['values']['remarks']='导入备注'
        result=service.apply_import(self.db,self.bind(),self.uid,self.scope)
        a.customer='导入后修改';self.db.commit()
        with self.assertRaises(HTTPException):service.rollback_import(self.db,result['batch_id'],self.uid,self.scope)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),2);self.assertEqual(a.remarks,'导入备注')
    def test_merge_rolls_back_before_values_and_logs_on_failure(self):
        from unittest.mock import patch
        a=self.existing();self.payload['rows'][0]['values']['remarks']='导入备注'
        original=service._log;calls=0
        def fail_second(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==2:raise RuntimeError('test failure')
            return original(*args,**kwargs)
        with patch.object(service,'_log',side_effect=fail_second):
            with self.assertRaises(RuntimeError):service.apply_import(self.db,self.bind(),self.uid,self.scope)
        self.db.refresh(a);self.assertIsNone(a.remarks)
        for model in [ArchiveImportRow,ArchiveImportBatch,SysOperationLog]:self.assertEqual(self.db.query(model).count(),0)
    def test_provenance_lists_original_values_and_merge_mode(self):
        a=self.existing();self.payload['rows'][0]['values']['remarks']='补充备注'
        service.apply_import(self.db,self.bind(),self.uid,self.scope)
        result=service.get_import_source(self.db,a.id,self.scope)
        self.assertEqual(result['operation'],'updated')

class EnumMappingContract(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.offline_archive_enum_mapping'),'需实现已批准的固定映射')
        return importlib.import_module('app.services.offline_archive_enum_mapping')
    def test_approved_aliases_and_ambiguous_values(self):
        m=self.module()
        self.assertEqual(m.normalize_offline_enum('machine_model','8"CassetteLess'),'8吋 Cassette Less')
        self.assertEqual(m.normalize_offline_enum('machine_model','8" Cssstte Less'),'8" Cssstte Less')
        self.assertEqual(m.normalize_offline_enum('quantity_unit','EA'),'个')
        self.assertEqual(m.normalize_offline_enum('quantity_unit','PCS'),'个')
        self.assertEqual(m.normalize_offline_enum('quantity_unit','m'),'米')
        for field,value in [('machine_model','6.3/8吋兼容CassetteType'),('machine_model','Single'),('machine_model','辅机'),('quantity_unit','给')]:
            self.assertEqual(m.normalize_offline_enum(field,value),value)
        self.assertEqual(m.normalize_offline_enum('equipment_series','DF-2000TB'),'DF-2000TB')
    def test_seed_once_preserves_numeric_ids_and_disabled_choices(self):
        from app.core.database import Base
        from sqlalchemy.orm import Session
        from app.services.enum_registry import initialize_enum_definitions
        m=self.module();engine=create_engine('sqlite://');Base.metadata.create_all(engine)
        with Session(engine) as db:
            initialize_enum_definitions(db);m.initialize_offline_enum_options(db)
            definition=db.query(SysDict).filter_by(dict_code='archive_quantity_unit').one()
            item=db.query(SysDictItem).filter_by(dict_id=definition.id,item_label='个').one();value=item.item_value;item.status=0;db.commit()
            m.initialize_offline_enum_options(db);db.refresh(item)
            self.assertEqual(item.item_value,value);self.assertEqual(item.status,0)
            self.assertEqual(db.query(SysDictItem).filter_by(dict_id=definition.id).count(),17)
        engine.dispose()
    def test_existing_labels_reuse_their_stable_value(self):
        from app.core.database import Base
        from sqlalchemy.orm import Session
        from app.services.enum_registry import initialize_enum_definitions
        m=self.module();engine=create_engine('sqlite://');Base.metadata.create_all(engine)
        with Session(engine) as db:
            initialize_enum_definitions(db);definition=db.query(SysDict).filter_by(dict_code='equipment_series').one()
            db.add(SysDictItem(dict_id=definition.id,item_label='DF-2000B',item_value='87'));definition.next_value=90;db.commit()
            m.initialize_offline_enum_options(db)
            self.assertEqual(db.query(SysDictItem).filter_by(dict_id=definition.id,item_label='DF-2000B').one().item_value,'87')
            self.assertGreaterEqual(definition.next_value,102)
        engine.dispose()
    def test_upgrade_old_import_rows_is_idempotent(self):
        from app.services.offline_archive_migration import upgrade_offline_archive
        e=create_engine('sqlite://')
        with e.begin() as c:
            c.execute(text('CREATE TABLE pms_project_archive (id INTEGER PRIMARY KEY, project_code NVARCHAR(32))'))
            c.execute(text('CREATE TABLE pms_archive_import_row (id INTEGER PRIMARY KEY, snapshot_hash NVARCHAR(64))'))
            c.execute(text("INSERT INTO pms_archive_import_row VALUES(1,'old')"))
        upgrade_offline_archive(e);upgrade_offline_archive(e)
        self.assertIn('before_values',{r['name'] for r in inspect(e).get_columns('pms_archive_import_row')})
        with e.connect() as c:self.assertEqual(c.execute(text('SELECT operation FROM pms_archive_import_row')).scalar(),'created')
        e.dispose()

if __name__=='__main__':unittest.main()
