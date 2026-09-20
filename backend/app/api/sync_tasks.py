from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.authorization import require_permission, require_any_permission
from app.services.project import ensure_archive_access, get_scoped_archive_query
from app.models.erp_task import ErpSyncTask
from app.models.project import PmsProjectArchive
from app.services import erp_queue

router = APIRouter(prefix='/api/sync-tasks', tags=['同步管理'])


def ensure_task_access(db, task_id, ctx):
    from fastapi import HTTPException
    task = db.get(ErpSyncTask, task_id)
    if not task:
        raise HTTPException(404, '任务不存在')
    ensure_archive_access(db, task.archive_id, ctx)
    return task


@router.get('')
def list_tasks(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
               keyword: str = '', status: str = '', operator: str = '', start: datetime | None = None,
               end: datetime | None = None, db: Session = Depends(get_db),
               ctx: dict = Depends(require_permission('system:sync:view'))):
    from app.core.config import settings
    result = erp_queue.list_tasks(db, page=page, page_size=page_size, keyword=keyword, status=status,
        operator=operator, start=start, end=end, scope_context=ctx)
    result['worker_enabled'] = settings.ERP_SYNC_WORKER_ENABLED
    return result


@router.get('/archive/{archive_id}')
def archive_tasks(archive_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
                  db: Session = Depends(get_db), ctx: dict = Depends(require_any_permission('project:archive:view', 'system:sync:view'))):
    ensure_archive_access(db, archive_id, ctx)
    return erp_queue.list_tasks(db, page=page, page_size=page_size, archive_id=archive_id)


class BatchRetry(BaseModel):
    task_ids: list[int] = Field(min_length=1, max_length=100)


@router.post('/retry')
def retry_tasks(data: BatchRetry, request: Request, db: Session = Depends(get_db),
                ctx: dict = Depends(require_permission('system:sync:retry'))):
    from fastapi import HTTPException
    ids = list(dict.fromkeys(data.task_ids))
    for task_id in ids:
        ensure_task_access(db, task_id, ctx)
    results = []
    for task_id in ids:
        try:
            result = erp_queue.retry(db, task_id, ctx['user_id'], request)
            results.append({'id': task_id, 'success': True, 'task_id': result['id']})
        except HTTPException as exc:
            db.rollback()
            results.append({'id': task_id, 'success': False, 'message': exc.detail})
    return {'items': results}


@router.post('/{task_id}/inspect')
def inspect_task(task_id: int, request: Request, external_request_finished: bool = False, db: Session = Depends(get_db),
                 ctx: dict = Depends(require_permission('system:sync:retry'))):
    ensure_task_access(db, task_id, ctx)
    return erp_queue.inspect_result(db, task_id, ctx['user_id'], request, external_request_finished=external_request_finished)
