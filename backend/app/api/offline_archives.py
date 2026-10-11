from fastapi import APIRouter,Depends,Request,UploadFile,File,HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.authorization import require_permission
from app.schemas.offline_archive import ApprovedImportPayload,ProductLineAssignment
from app.services.offline_archive_import import preview_import,apply_import,rollback_import,assign_product_line
from app.services.offline_archive_approval import verify_payload
router=APIRouter(prefix="/api/offline-archives",tags=["期初项目档案"])


def initialization_gate(permission):
    def gate(db:Session=Depends(get_db),scope:dict=Depends(require_permission(permission))):
        from app.services.parameter import require_archive_initialization
        require_archive_initialization(db)
    return gate


@router.get("/initialization-status")
def initialization_status(db:Session=Depends(get_db),scope:dict=Depends(require_permission("project:archive:view"))):
    from app.services.parameter import archive_initialization_enabled
    return {"enabled": archive_initialization_enabled(db)}


@router.post("/preview", dependencies=[Depends(initialization_gate("project:archive:import"))])
def preview(data: ApprovedImportPayload,db: Session=Depends(get_db),scope: dict=Depends(require_permission("project:archive:import"))):
    return preview_import(db,verify_payload(data),scope)
@router.post("/apply", dependencies=[Depends(initialization_gate("project:archive:import"))])
def apply(data: ApprovedImportPayload,request: Request,db: Session=Depends(get_db),scope: dict=Depends(require_permission("project:archive:import"))):
    return apply_import(db,verify_payload(data),scope["user_id"],scope,request,source_file_hash=data.file_hash)
@router.post("/batches/{batch_id}/rollback")
def rollback(batch_id:int,request: Request,db: Session=Depends(get_db),scope: dict=Depends(require_permission("project:archive:import"))):
    return rollback_import(db,batch_id,scope["user_id"],scope,request)
@router.post("/assign-product-line", dependencies=[Depends(initialization_gate("project:archive:assign-line"))])
def assign(data:ProductLineAssignment,request:Request,db:Session=Depends(get_db),scope:dict=Depends(require_permission("project:archive:assign-line"))):
    return assign_product_line(db,data.model_dump(mode="json"),scope["user_id"],scope,request)

@router.post("/workbook", dependencies=[Depends(initialization_gate("project:archive:import"))])
async def workbook(file:UploadFile=File(...),db:Session=Depends(get_db),scope:dict=Depends(require_permission("project:archive:import"))):
    from app.services.offline_archive_import import require_import_scope
    from app.services.offline_archive_workbook import prepare_workbook
    require_import_scope(scope)
    content=await file.read(20*1024*1024+1)
    return prepare_workbook(db,content)


@router.get("/archives/{archive_id}/source")
def source(archive_id:int,db:Session=Depends(get_db),scope:dict=Depends(require_permission("project:archive:view"))):
    from app.services.offline_archive_import import get_import_source
    return get_import_source(db,archive_id,scope)
