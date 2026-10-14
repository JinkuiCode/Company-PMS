"""Exercise real dev account grants on a private SQLite copy, without creating live test orders."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from uuid import uuid4


def main():
    root=Path(__file__).resolve().parents[2]
    source=root/'.runtime/data/pms-dev.db'
    with tempfile.TemporaryDirectory(prefix='pms-archive-acceptance-') as directory:
        copy=Path(directory)/'acceptance.db'
        with sqlite3.connect(f'file:{source}?mode=ro',uri=True) as original,sqlite3.connect(copy) as target:
            original.backup(target)
            assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        os.chmod(copy,0o600)
        os.environ.update(DB_DIALECT='sqlite',SQLITE_DB_PATH=str(copy),K3_READ_ONLY='true',
            ERP_SYNC_WORKER_ENABLED='false',PMS_CONFIG_FILE=str(root/'backend/.env.local'),
            PMS_PURCHASE_CONFIG_FILE=str(root/'.runtime/private/purchase-report.env'))
        sys.path.insert(0,str(root/'backend'))
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from sqlalchemy.orm import Session
        from app.core.database import engine,get_db
        from app.api import projects,archive_changes
        from app.models.user import SysUser
        from app.models.project import PmsProjectArchive
        from app.models.dict import SysDict,SysDictItem
        from app.services.authorization import get_current_user_context,build_authorization_context
        from app.services.operation_log import serialize_model

        assert str(engine.url.database)==str(copy)
        with Session(engine) as db:
            owner=db.query(SysUser).filter_by(username='ael',status=1).one()
            head=db.query(SysUser).filter_by(username='A000645',status=1).one()
            original_archives={row.id:serialize_model(row) for row in db.query(PmsProjectArchive)}
            actor=[owner.id]
            app=FastAPI();app.include_router(projects.router);app.include_router(archive_changes.router)
            app.dependency_overrides[get_db]=lambda:db
            # Identity is supplied only in this in-process harness; all grants are read live from the copied database.
            app.dependency_overrides[get_current_user_context]=lambda:build_authorization_context(db,actor[0])
            def enum_value(code):
                return int(db.query(SysDictItem.item_value).join(SysDict,SysDict.id==SysDictItem.dict_id)
                    .filter(SysDict.dict_code==code,SysDictItem.status==1).order_by(SysDictItem.sort,SysDictItem.id).first()[0])
            code='DEV-GOV-'+uuid4().hex[:12].upper()
            payload=dict(project_code=code,project_name='开发机审批闭环测试',product_line_id=3,manager_id=owner.id,
                archive_category=1,machine_model=enum_value('archive_machine_model'),quantity=1,
                quantity_unit=enum_value('archive_quantity_unit'),equipment_series=enum_value('equipment_series'),
                serial_no='DEV-SN-'+uuid4().hex[:12],contract_signed_date='2026-10-14',contract_ship_date='2026-12-01')
            with TestClient(app) as client:
                result=client.post('/api/projects/archives',json={**payload,'serial_no':None})
                assert result.status_code==422,result.text
                result=client.post('/api/projects/archives',json=payload)
                assert result.status_code==200,result.text
                archive_id=result.json()['id']
                def snapshot():
                    result=client.get('/api/projects/archives/list',params={'archive_id':archive_id,'enabled':'all'})
                    assert result.status_code==200,result.text
                    assert result.json()['total']==1,result.text
                    return result.json()['items'][0]
                current=snapshot()
                assert current['change_mode']=='approval' and current['approver_id']==head.id
                assert current['governance_legacy'] is False
                result=client.post(f'/api/projects/archive-changes/{archive_id}/submit',json={
                    'updates':{'customer':'审批闭环通过'},'expected_version':current['change_version'],
                    'submission_id':str(uuid4()),'reason':'开发机副本验收，不写金蝶'})
                assert result.status_code==200,result.text
                pending=result.json()
                assert pending['status']==2
                assert snapshot()['customer'] is None
                actor[0]=head.id
                context=build_authorization_context(db,head.id)
                assert set(context['permissions'])=={'project:archive:list','project:archive:view','project:archive:edit'}
                assert context['data_scope']==2 and context['product_line_ids']==[3]
                assert client.post('/api/projects/archives',json={**payload,'project_code':code+'X'}).status_code==403
                assert snapshot()['pending_change_id']==pending['id']
                requests=client.get('/api/projects/archive-changes')
                assert requests.status_code==200 and any(row['id']==pending['id'] and row['can_approve'] for row in requests.json()['items'])
                decision={'decision':'approve','expected_version':pending['version'],'opinion':'开发机副本验收通过'}
                for _ in range(2):
                    result=client.post(f"/api/projects/archive-changes/requests/{pending['id']}/decide",json=decision)
                    assert result.status_code==200,result.text
                    assert result.json()['status']==3
                assert snapshot()['customer']=='审批闭环通过'
                db.expire_all()
                assert original_archives=={row.id:serialize_model(row) for row in db.query(PmsProjectArchive).filter(PmsProjectArchive.id.in_(original_archives))}
            print(json.dumps({'database':'private development copy','source_archives':len(original_archives),
                'required_guard':'passed','owner_submission':'passed','formal_unchanged_while_pending':'passed',
                'real_role_scope':'passed','head_add_denied':'passed','head_approval_and_retry':'passed',
                'source_archives_unchanged':True,'external_erp_writes':False,'workers_started':False},ensure_ascii=False))
        engine.dispose()


if __name__=='__main__':main()
