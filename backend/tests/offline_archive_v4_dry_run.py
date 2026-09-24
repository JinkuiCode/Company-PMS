import sys,time
from pathlib import Path
started=time.perf_counter()
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.core.database import Base
import app.models.init_db
from app.models.dict import SysDict,SysDictItem
from app.models.user import SysUser
from app.models.project import PmsProjectArchive
from app.models.erp_task import ErpSyncTask
from app.services.enum_registry import initialize_enum_definitions
from app.services.offline_archive_workbook import read_archive_workbook,prepare_workbook
from app.services.offline_archive_import import preview_import,apply_import,rollback_import
from app.services.offline_archive_fields import OFFLINE_FIELDS
p=Path(sys.argv[1])
content=p.read_bytes()
rows=read_archive_workbook(content)
e=create_engine("sqlite://");Base.metadata.create_all(e);db=Session(e)
initialize_enum_definitions(db)
for key,code in {**{k:v["enum_code"] for k,v in OFFLINE_FIELDS.items() if v["enum_code"]},"equipment_series":"equipment_series"}.items():
    d=db.query(SysDict).filter_by(dict_code=code).one()
    existing=db.query(SysDictItem).filter_by(dict_id=d.id).all()
    labels={x.item_label for x in existing};n=max([int(x.item_value) for x in existing]+[0])
    for label in sorted({r["values"][key] for r in rows if r["values"].get(key)}-labels):
        n+=1;db.add(SysDictItem(dict_id=d.id,item_label=label,item_value=str(n),status=1,sort=n))
db.commit()
u=SysUser(username="offline-dry-run",password_hash="x",real_name="演练",status=1);db.add(u);db.commit()
scope={"user_id":u.id,"data_scope":4,"permissions":["business:data:all"]}
from unittest.mock import patch
from app.services.offline_archive_approval import settings,verify_payload
from app.schemas.offline_archive import ApprovedImportPayload
with patch.object(settings,"SECRET_KEY","isolated-dry-run-key-not-a-real-secret-000"):
    prepared=prepare_workbook(db,content)
    verified=verify_payload(ApprovedImportPayload.model_validate(prepared["payload"]))
assert not prepared["errors"],str(prepared["errors"])[:300]
preview=preview_import(db,verified,scope)
print("rows",len(rows),"preview_errors",len(preview["errors"]))
if preview["errors"]:
    from collections import Counter
    print(Counter(x["message"] for x in preview["errors"]));raise SystemExit(1)
result=apply_import(db,verified,u.id,scope)
assert result["created"]==3024
assert db.query(PmsProjectArchive).filter(PmsProjectArchive.business_product_line_id.isnot(None)).count()==0
assert db.query(PmsProjectArchive).filter(PmsProjectArchive.erp_sync_policy!="manual").count()==0
assert db.query(ErpSyncTask).count()==0
print("created",result["created"],"empty_names",db.query(PmsProjectArchive).filter(PmsProjectArchive.project_name.is_(None)).count(),"erp_tasks",db.query(ErpSyncTask).count())
print("rollback",rollback_import(db,result["batch_id"],u.id,scope)["deleted"])
assert db.query(PmsProjectArchive).count()==0

print("elapsed_seconds",round(time.perf_counter()-started,2))
