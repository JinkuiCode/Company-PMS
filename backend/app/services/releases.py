"""One published record feeds about, notices, mail and page guides."""
import json
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.models.release import PmsRelease, PmsReleaseNotice, PmsReleaseMail
from app.models.user import SysUser
from app.services.authorization import enforce_permission, build_authorization_context
from app.services.operation_log import record_operation_log
from app.services.runtime_release import manifest_digest, validated_manifest, load_runtime_manifest
from app.core.business_time import business_time


def release_view(row):
    return {'id': row.id, 'version': row.version, 'title': row.title, 'summary': row.summary,
            'published_at': business_time(row.published_at), 'changes': json.loads(row.content_json)}


def _version(value): return tuple(int(part) for part in value.removeprefix('v').split('.'))


def publish_release(db, context, manifest, receipt, request=None):
    enforce_permission(context, 'system:release:publish')
    # CLI and worker callers also re-read live identity/rights, just like HTTP callers.
    enforce_permission(build_authorization_context(db, context.get('user_id')), 'system:release:publish')
    try:
        validated = validated_manifest(manifest)
        runtime = load_runtime_manifest()
        if not runtime or manifest_digest(runtime) != manifest_digest(manifest): raise ValueError()
        accepted = datetime.fromisoformat(str(receipt.get('validated_at', '')).replace('Z', '+00:00'))
        built = datetime.fromisoformat(validated['built_at'])
        if receipt.get('accepted') is not True or receipt.get('manifest_sha256') != manifest_digest(manifest) or accepted.tzinfo is None or accepted < built or accepted > datetime.now(timezone.utc):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(422, '发布清单或当前构建验收凭据不匹配，未发布通知')
    digest = manifest_digest(manifest)
    # Serialize publication (and the initial no-release case) using an existing row.
    from app.models.database_revision import PmsDatabaseRevision
    revision = db.execute(select(PmsDatabaseRevision.revision).where(PmsDatabaseRevision.id == 1).with_hint(
        PmsDatabaseRevision, 'WITH (UPDLOCK, HOLDLOCK)', dialect_name='mssql'))
    if revision.scalar_one_or_none() != manifest['database_revision']:
        raise HTTPException(503, '当前数据库版本尚未通过发布检查')
    current = db.query(PmsRelease).filter_by(version=manifest['version']).first()
    if current:
        if current.manifest_sha256 != digest: raise HTTPException(409, '相同版本已有不同发布内容，禁止覆盖')
        return current
    latest = db.query(PmsRelease).order_by(PmsRelease.id.desc()).first()
    target = _version(manifest['version'])
    if latest:
        major, minor, fix = _version(latest.version)
        allowed = {(major, minor, fix+1), (major, minor+1, 0), (major+1, 0, 0)}
        if target not in allowed: raise HTTPException(422, '版本须按主版本、功能或修复顺序递增')
    elif target != (1, 0, 0): raise HTTPException(422, '首个统一管理的正式版本须为v1.0.0')
    try:
        release = PmsRelease(version=manifest['version'], title=validated['title'], summary=validated['summary'],
            content_json=json.dumps(validated['changes'], ensure_ascii=False), manifest_sha256=digest,
            code_commit=manifest['commit'], build_id=manifest['build_id'], database_revision=manifest['database_revision'],
            published_by=context['user_id'])
        db.add(release); db.flush()
        for user in db.query(SysUser).filter_by(status=1).order_by(SysUser.id):
            notice = PmsReleaseNotice(release_id=release.id, user_id=user.id)
            db.add(notice); db.flush()
            db.add(PmsReleaseMail(notice_id=notice.id))
        record_operation_log(db, module='版本发布', action='publish', entity_type='pms_release',
            entity_id=release.id, entity_name=release.version, operator_id=context['user_id'], request=request,
            summary=f'发布{release.version}', after_data={'version': release.version, 'manifest_sha256': digest})
        db.commit(); db.refresh(release)
        return release
    except IntegrityError:
        db.rollback()
        current = db.query(PmsRelease).filter_by(version=manifest['version']).first()
        if current and current.manifest_sha256 == digest: return current
        raise HTTPException(409, '另一个发布操作已完成，请刷新核对版本及内容')
    except Exception:
        db.rollback(); raise


def list_releases(db, *, page=1, page_size=50):
    query = db.query(PmsRelease)
    return {'total': query.count(), 'items': [release_view(row) for row in query.order_by(PmsRelease.id.desc()).offset((page-1)*page_size).limit(page_size)]}


def list_notices(db, context, *, page=1, page_size=50):
    query = db.query(PmsReleaseNotice).filter_by(user_id=context['user_id'])
    return {'total': query.count(), 'unread': query.filter(PmsReleaseNotice.read_at.is_(None)).count(),
        'items': [dict(id=row.id, read_at=business_time(row.read_at), release=release_view(db.get(PmsRelease, row.release_id)))
                  for row in query.order_by(PmsReleaseNotice.id.desc()).offset((page-1)*page_size).limit(page_size)]}


def mark_read(db, context, notice_id, request=None):
    row = db.query(PmsReleaseNotice).filter_by(id=notice_id, user_id=context['user_id']).first()
    if not row: raise HTTPException(404, '通知不存在或无权访问')
    changed = db.execute(update(PmsReleaseNotice).where(PmsReleaseNotice.id == row.id,
        PmsReleaseNotice.read_at.is_(None)).values(read_at=datetime.utcnow()))
    if changed.rowcount:
        record_operation_log(db, module='版本通知', action='read', entity_type='pms_release_notice',
            entity_id=row.id, operator_id=context['user_id'], request=request, summary='确认已阅读升级通知')
        db.commit()
    return {'read': True}
