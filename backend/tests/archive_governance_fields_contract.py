import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
TMP=tempfile.TemporaryDirectory();os.environ['DB_DIALECT']='sqlite';os.environ['SQLITE_DB_PATH']=str(Path(TMP.name)/'unused.db')
from app.core.database import Base
import app.models.init_db
from app.models.project import PmsProjectArchive
from app.models.user import SysUser
from app.schemas.project import ArchiveCreate,ArchiveUpdate,ArchiveResponse
from app.services.field_policy import validate_business_field_write,get_effective_field_policies


class GovernanceFields(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://');Base.metadata.create_all(self.engine);self.db=Session(self.engine)
        self.user=SysUser(username='active',real_name='有效用户',password_hash='fixture',status=1)
        self.db.add(self.user);self.db.commit()
    def tearDown(self):self.db.close();self.engine.dispose()
    def validate(self,values,**kwargs):
        return validate_business_field_write(self.db,'project_archive',current_values=kwargs.pop('current',{}),updates=values,
            entity_created_at=kwargs.pop('created_at',None),is_create=kwargs.pop('is_create',True),
            entity_governance_legacy=kwargs.pop('legacy',False),**kwargs)
    def valid(self):return dict(project_code='NEW',project_name='档案',product_line_id=1,archive_category=1,machine_model=1,quantity=1,quantity_unit=7,manager_id=self.user.id,equipment_series=1,serial_no='SN',contract_signed_date='2026-10-01',contract_ship_date='2026-12-01')
    def test_new_business_required_and_main_machine_conditions(self):
        for key in ('archive_category','machine_model','quantity','quantity_unit','manager_id','equipment_series','serial_no'):
            with self.subTest(key=key):
                values=self.valid();values[key]=None
                with self.assertRaises(HTTPException) as caught:self.validate(values)
                self.assertEqual(caught.exception.status_code,422)
        values=self.valid();values.update(archive_category=2,equipment_series=None,serial_no=None)
        self.validate(values)
    def test_historical_untouched_gaps_stay_maintainable_but_new_invalid_user_rejected(self):
        self.validate({'customer':'补充客户'},current={'archive_category':1},created_at=datetime.now()-timedelta(days=1000),is_create=False,historical_import=True,legacy=True)
        values=self.valid();values['manager_id']=9999
        with self.assertRaises(HTTPException):self.validate(values)
        self.user.status=0;self.db.commit();values['manager_id']=self.user.id
        with self.assertRaises(HTTPException):self.validate(values)
    def test_customer_full_name_is_readonly_and_plan_fields_removed(self):
        with self.assertRaises(HTTPException):self.validate({**self.valid(),'customer_full_name':'不可新建'})
        with self.assertRaises(HTTPException):self.validate({'customer_full_name':'改写'},current={'customer_full_name':'历史完整名'},is_create=False)
        for cls in (ArchiveCreate,ArchiveUpdate,ArchiveResponse):
            self.assertNotIn('plan_start_date',cls.model_fields);self.assertNotIn('plan_end_date',cls.model_fields)
        self.assertNotIn('plan_start_date',PmsProjectArchive.__table__.columns)
        self.assertFalse(any(item['field_key'].startswith('plan_') for item in get_effective_field_policies(self.db,'project_archive')['items']))
        with self.assertRaises(ValidationError):ArchiveUpdate(plan_start_date='2026-10-01')
        for cls in (ArchiveCreate,ArchiveUpdate):
            with self.assertRaises(ValidationError):cls(project_code='X',project_name='X',governance_legacy=True)

    def test_legacy_marker_not_creation_clock_controls_governance_requirements(self):
        from app.services.archive_governance_migration import install_archive_governance
        install_archive_governance(self.db);self.db.commit()
        self.validate({'customer':'保留历史缺项'},current={'archive_category':1},
            created_at=datetime.now()+timedelta(days=1),is_create=False,legacy=True)
        with self.assertRaises(HTTPException):
            self.validate({'quantity':None},current=self.valid(),created_at=datetime(2000,1,1),is_create=False)
        with self.assertRaises(HTTPException):
            self.validate({'archive_category':1},current={'archive_category':2},is_create=False,legacy=True)
    def test_old_required_override_cannot_make_the_readonly_full_name_required(self):
        from app.models.field_policy import SysBusinessFieldPolicy
        self.db.add(SysBusinessFieldPolicy(module_code='project_archive',field_key='customer_full_name',
            visible=True,editable=True,required=True,list_available=True,required_effective_at=datetime.now()-timedelta(days=1)))
        self.db.commit()
        field=next(item for item in get_effective_field_policies(self.db,'project_archive')['items'] if item['field_key']=='customer_full_name')
        self.assertFalse(field['required'])
        self.validate(self.valid())
    def test_saving_conditional_policy_preserves_its_effective_time(self):
        from app.services.archive_governance_migration import install_archive_governance
        from app.services.field_policy import update_field_policies
        from app.schemas.field_policy import FieldPolicyBatchUpdate,FieldPolicyUpdateItem
        install_archive_governance(self.db);self.db.commit()
        fields=get_effective_field_policies(self.db,'project_archive')['items']
        old=next(field for field in fields if field['field_key']=='serial_no')
        update_field_policies(self.db,'project_archive',FieldPolicyBatchUpdate(items=[FieldPolicyUpdateItem(
            field_key='serial_no',visible=True,editable=True,required=False,list_available=True,expected_updated_at=old['updated_at'])]),operator_id=self.user.id)
        latest=next(field for field in get_effective_field_policies(self.db,'project_archive')['items'] if field['field_key']=='serial_no')
        self.assertEqual(latest['required_effective_at'],old['required_effective_at'])
        values=self.valid()
        with self.assertRaises(HTTPException):
            self.validate({'serial_no':None},current=values,created_at=datetime.now(),is_create=False)
    def test_server_created_archive_uses_the_same_clock_as_required_cutoff(self):
        from app.services.archive_governance_migration import install_archive_governance
        install_archive_governance(self.db);self.db.commit()
        archive=PmsProjectArchive(project_code='AFTER-UPGRADE',project_name='新建',manager_id=self.user.id)
        self.db.add(archive);self.db.commit();self.db.refresh(archive)
        with self.assertRaises(HTTPException):
            self.validate({'quantity':None},current=self.valid(),created_at=archive.created_at,is_create=False)
    def test_unconditional_toggle_cannot_delay_the_main_machine_requirement(self):
        from app.services.archive_governance_migration import install_archive_governance
        from app.services.field_policy import update_field_policies
        from app.schemas.field_policy import FieldPolicyBatchUpdate,FieldPolicyUpdateItem
        install_archive_governance(self.db);self.db.commit()
        field=next(item for item in get_effective_field_policies(self.db,'project_archive')['items'] if item['field_key']=='serial_no')
        introduced=field['required_effective_at']
        for required in (True,False):
            with patch.object(self.db,'scalar',return_value=introduced+timedelta(hours=2)):
                result=update_field_policies(self.db,'project_archive',FieldPolicyBatchUpdate(items=[FieldPolicyUpdateItem(
                    field_key='serial_no',visible=True,editable=True,required=required,list_available=True,
                    expected_updated_at=field['updated_at'])]),operator_id=self.user.id)
            field=next(item for item in result['items'] if item['field_key']=='serial_no')
        with self.assertRaises(HTTPException):
            self.validate({'serial_no':None},current=self.valid(),created_at=introduced+timedelta(hours=1),is_create=False)

if __name__=='__main__':unittest.main()
