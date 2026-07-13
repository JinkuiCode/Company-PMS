"""
金蝶 ERP 对接 API 路由
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.services.authorization import require_permission
from app.services.project import ensure_archive_access
from app.services import kingdee

router = APIRouter(prefix="/api/erp", tags=["金蝶 ERP 对接"])


class SyncRequest(BaseModel):
    """同步请求"""
    archive_id: int


class BatchSyncRequest(BaseModel):
    """批量同步请求"""
    archive_ids: list[int]


@router.post("/test", summary="测试金蝶连接")
def test_connection(_scope_ctx: dict = Depends(require_permission("project:archive:sync"))):
    """测试金蝶 ERP 连接是否正常"""
    return kingdee.test_erp_connection()


@router.post("/sync", summary="同步单个项目档案")
def sync_project_archive(
    data: SyncRequest,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:archive:sync")),
):
    """
    同步单个项目档案到金蝶 ERP
    - 如果金蝶中不存在则创建
    - 如果已存在则更新
    """
    ensure_archive_access(db, data.archive_id, scope_ctx)
    return kingdee.sync_project_archive_to_erp(
        db, data.archive_id, user_id=scope_ctx["user_id"], request=request
    )


@router.post("/sync/batch", summary="批量同步项目档案")
def batch_sync_project_archives(
    data: BatchSyncRequest,
    request: Request,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:archive:sync")),
):
    """批量同步多个项目档案到金蝶 ERP"""
    for archive_id in data.archive_ids:
        ensure_archive_access(db, archive_id, scope_ctx)
    return kingdee.batch_sync_project_archives(
        db, data.archive_ids, user_id=scope_ctx["user_id"], request=request
    )


@router.get("/logs/{archive_id}", summary="查询同步日志")
def get_sync_logs(
    archive_id: int,
    limit: int = 10,
    db: Session = Depends(get_db),
    scope_ctx: dict = Depends(require_permission("project:archive:view")),
):
    """查询指定项目档案的同步日志"""
    ensure_archive_access(db, archive_id, scope_ctx)
    logs = kingdee.get_sync_logs(db, archive_id, limit)
    return {"success": True, "data": logs}
