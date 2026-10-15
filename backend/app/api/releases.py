from fastapi import APIRouter, Depends, Query, Request, HTTPException
from pydantic import BaseModel, Field, ConfigDict, StrictBool
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.authorization import get_current_user_context, require_permission
from app.services import releases, release_mail
from app.services.runtime_release import runtime_info, load_runtime_manifest
from app.models.release import PmsRelease
from app.core.business_time import business_time

router = APIRouter(prefix='/api/releases', tags=['运行版本及个人通知'])


class AcceptanceReceipt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    manifest_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    accepted: StrictBool
    validated_at: str = Field(max_length=64)


@router.post('/publish')
def publish(data: AcceptanceReceipt, request: Request, context=Depends(require_permission('system:release:publish')), db: Session=Depends(get_db)):
    manifest = load_runtime_manifest()
    if not manifest: raise HTTPException(422, '没有当前构建的版本清单，未发布')
    return releases.release_view(releases.publish_release(db, context, manifest, data.model_dump(), request))


@router.get('/runtime')
def runtime(context=Depends(get_current_user_context), db: Session=Depends(get_db)):
    value = runtime_info(context)
    current = db.query(PmsRelease).filter_by(version=value['version']).first()
    value['published_at'] = business_time(current.published_at) if current else None
    updates = {}
    for row in db.query(PmsRelease).order_by(PmsRelease.id.desc()):
        for change in releases.release_view(row)['changes']:
            updates.setdefault(change['guide'], {'version': row.version, 'published_at': business_time(row.published_at)})
    value['page_updates'] = updates
    return value


@router.get('/notices')
def notices(page: int=Query(1, ge=1), page_size: int=Query(50, ge=1, le=500),
            context=Depends(get_current_user_context), db: Session=Depends(get_db)):
    return releases.list_notices(db, context, page=page, page_size=page_size)


@router.post('/notices/{notice_id}/read')
def read(notice_id: int, request: Request, context=Depends(get_current_user_context), db: Session=Depends(get_db)):
    return releases.mark_read(db, context, notice_id, request)


@router.get('')
def history(page: int=Query(1, ge=1), page_size: int=Query(50, ge=1, le=500),
            context=Depends(get_current_user_context), db: Session=Depends(get_db)):
    return releases.list_releases(db, page=page, page_size=page_size)


@router.get('/{release_id}/mail-preview')
def preview(release_id: int, context=Depends(get_current_user_context), db: Session=Depends(get_db)):
    release = db.get(PmsRelease, release_id)
    if not release: raise HTTPException(404, '发布记录不存在')
    from types import SimpleNamespace
    message = release_mail.build_message({'sender': 'pms@example.invalid'}, release,
        SimpleNamespace(id=0), 'preview@example.invalid')
    return {'subject': str(message['Subject']), 'text': message.get_content()}


@router.get('/{release_id}/deliveries')
def deliveries(release_id: int, page: int=Query(1, ge=1), page_size: int=Query(50, ge=1, le=500),
               context=Depends(require_permission('system:release:manage')), db: Session=Depends(get_db)):
    return release_mail.list_deliveries(db, context, release_id, page=page, page_size=page_size)


class MailRetry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=500)
    checked_not_received: bool = False


@router.post('/mail/{mail_id}/retry')
def retry(mail_id: int, data: MailRetry, request: Request,
          context=Depends(require_permission('system:release:retry')), db: Session=Depends(get_db)):
    return release_mail.retry(db, context, mail_id, reason=data.reason,
        checked_not_received=data.checked_not_received, request=request)
