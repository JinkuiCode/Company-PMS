"""Batch validation is bounded and reads current rules again on each call."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sqlalchemy import event
from fastapi import HTTPException
from unittest.mock import patch
from offline_archive_import_contract import ImportContract
from app.models.dict import SysDict,SysDictItem
from app.models.field_policy import SysBusinessFieldPolicy
from app.models.project import PmsProjectArchive
from app.services import offline_archive_import as service
from app.services.field_policy import MODULE_PROJECT_ARCHIVE

class PerformanceContract(ImportContract):
    def batch(self,n):
        definition=self.db.query(SysDict).filter_by(dict_code='equipment_series').one()
        item=self.db.query(SysDictItem).filter_by(dict_id=definition.id,status=1).first()
        self.assertIsNotNone(item)
        self.item=item
        return {'rows':[{'source_id':f'P-{i}','source_sheet':'性能样本','source_row':i+2,'values':{'project_code':f'P-{i}','customer':'客户','equipment_series':int(item.item_value)}} for i in range(n)]}
    def reads(self,payload):
        statements=[]
        def capture(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
        event.listen(self.e,'before_cursor_execute',capture)
        try:result=service.preview_import(self.db,payload,self.scope)
        finally:event.remove(self.e,'before_cursor_execute',capture)
        return result,len(statements)
    def test_query_count_does_not_grow_with_batch_rows(self):
        small,first=self.reads(self.batch(5));large,second=self.reads(self.batch(200))
        self.assertFalse(small['errors']);self.assertFalse(large['errors'])
        self.assertEqual(large['created'],200)
        self.assertLessEqual(second,20,'batch metadata must not query once per row')
        self.assertLessEqual(second,first+2)
    def test_disabled_enum_is_rechecked_and_reported_for_every_row(self):
        payload=self.batch(8);self.assertFalse(service.preview_import(self.db,payload,self.scope)['errors'])
        self.item.status=0;self.db.commit()
        errors=service.preview_import(self.db,payload,self.scope)['errors']
        self.assertEqual({e['source_id'] for e in errors if e.get('field')=='equipment_series'},{f'P-{i}' for i in range(8)})
    def readonly_customer(self):
        self.db.add(SysBusinessFieldPolicy(module_code=MODULE_PROJECT_ARCHIVE,field_key='customer',visible=True,editable=False,required=False,list_available=True))
        self.db.flush()
    def test_field_rule_changes_are_read_on_next_preview(self):
        payload=self.batch(8);self.assertFalse(service.preview_import(self.db,payload,self.scope)['errors'])
        self.readonly_customer();self.db.commit()
        errors=service.preview_import(self.db,payload,self.scope)['errors']
        self.assertEqual({e['source_id'] for e in errors},{f'P-{i}' for i in range(8)})
    def test_apply_revalidates_rules_after_lifecycle_locks(self):
        payload=self.batch(2);original=service.claim_archive_lifecycle_rows
        def changed_rule(*args,**kwargs):
            locked=original(*args,**kwargs);self.readonly_customer();return locked
        with patch.object(service,'claim_archive_lifecycle_rows',side_effect=changed_rule):
            with self.assertRaises(HTTPException):service.apply_import(self.db,payload,self.uid,self.scope)
        self.assertEqual(self.db.query(PmsProjectArchive).count(),0)
if __name__=='__main__':unittest.main()
