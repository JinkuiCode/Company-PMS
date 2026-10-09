"""Local-only full-workbook rehearsal; optional minimal read-only archive snapshot."""
import hashlib,json,sys,time
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
import app.models.init_db
from app.models.project import PmsProjectArchive
from app.models.erp_task import ErpSyncTask
from app.models.user import SysUser
from app.models.dict import SysDict,SysDictItem
from app.services.enum_registry import initialize_enum_definitions
from app.services.offline_archive_enum_mapping import initialize_offline_enum_options,APPROVED_ENUM_OPTIONS
from app.services.offline_archive_workbook import prepare_workbook
from app.services.offline_archive_import import preview_import,apply_import,rollback_import,digest
from app.services.offline_archive_approval import settings,verify_payload
from app.schemas.offline_archive import ApprovedImportPayload
from app.services.operation_log import serialize_model

started=time.perf_counter()
content=Path(sys.argv[1]).read_bytes()
engine=create_engine('sqlite://');Base.metadata.create_all(engine)
with Session(engine) as db:
    initialize_enum_definitions(db);initialize_offline_enum_options(db)
    for code,labels in APPROVED_ENUM_OPTIONS.items():
        definition=db.query(SysDict).filter_by(dict_code=code).one()
        assert set(labels) <= {x.item_label for x in db.query(SysDictItem).filter_by(dict_id=definition.id)}
    original={}
    snapshot_date=None
    if len(sys.argv)>2:
        snapshot=json.loads(Path(sys.argv[2]).read_text());snapshot_date=snapshot.get('checked_at')
        for record in snapshot['archives']:
            db.add(PmsProjectArchive(**record))
        db.commit()
        original={a.id:serialize_model(a) for a in db.query(PmsProjectArchive)}
    user=SysUser(username='isolated-rehearsal',password_hash='not-used',real_name='隔离演练',status=1);db.add(user);db.commit()
    scope={'user_id':user.id,'data_scope':4,'permissions':['business:data:all']}
    with patch.object(settings,'SECRET_KEY','isolated-rehearsal-not-a-real-secret-0000'):
        prepared=prepare_workbook(db,content)
        assert not prepared['errors'],str(prepared['errors'])[:200]
        payload=verify_payload(ApprovedImportPayload.model_validate(prepared['payload']))
    preview=preview_import(db,payload,scope)
    assert not preview['errors'],str(preview['errors'])[:300]
    result=apply_import(db,payload,user.id,scope,source_file_hash=prepared['file_hash'])
    assert result['created']+result['updated']+result['unchanged']==3024
    assert db.query(PmsProjectArchive).count()==len(original)+result['created']
    for a in db.query(PmsProjectArchive):
        if a.id in original:
            old=original[a.id]
            for key,value in old.items():
                if key in ['updated_by','updated_at']:continue
                if value is not None and not (isinstance(value,str) and not value.strip()):
                    assert serialize_model(a)[key]==value,(a.id,key)
            for key in ['project_code','data_origin','business_product_line_id','erp_synced','erp_sync_status','erp_sync_policy']:
                assert serialize_model(a)[key]==old[key],(a.id,key)
        else:
            assert a.erp_sync_policy=='manual' and a.business_product_line_id is None
    assert db.query(ErpSyncTask).count()==0
    with patch.object(settings,'SECRET_KEY','isolated-rehearsal-not-a-real-secret-0000'):
        second=verify_payload(ApprovedImportPayload.model_validate(prepare_workbook(db,content)['payload']))
    again=apply_import(db,second,user.id,scope)
    assert again['batch_id']==result['batch_id'] and again['created']==0
    undone=rollback_import(db,result['batch_id'],user.id,scope)
    assert undone['deleted']==result['created'] and undone['restored']==result['updated']
    assert db.query(PmsProjectArchive).count()==len(original)
    for a in db.query(PmsProjectArchive):
        after=serialize_model(a);before=original[a.id]
        assert all(after[k]==v for k,v in before.items() if k not in ['updated_at','updated_by'])
    print(json.dumps({'file_sha256':hashlib.sha256(content).hexdigest(),'snapshot_checked_at':snapshot_date,
        'source_rows':3024,'existing_archives':len(original),'preview_errors':len(preview['errors']),
        'created':result['created'],'updated':result['updated'],'unchanged':result['unchanged'],
        'erp_tasks':db.query(ErpSyncTask).count(),'repeat_created':again['created'],
        'rollback_deleted':undone['deleted'],'rollback_restored':undone['restored'],
        'remaining_archives':db.query(PmsProjectArchive).count(),'enum_targets':sum(map(len,APPROVED_ENUM_OPTIONS.values())),
        'elapsed_seconds':round(time.perf_counter()-started,2)},ensure_ascii=False))
engine.dispose()
