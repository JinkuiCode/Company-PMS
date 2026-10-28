"""Approval events share the business transaction; reads always use current grants."""
from fastapi import HTTPException
from sqlalchemy import and_, or_, select, update
from app.core.business_time import business_time
from app.models.business_notice import BusinessNotice, BusinessNoticeMail, utc_now
from app.models.archive_change import ArchiveChange
from app.models.project import PmsProjectArchive
from app.models.user import SysUser
from app.models.rbac import SysDept
from app.services.authorization import build_authorization_context, enforce_permission
from app.services.operation_log import record_operation_log

VIEW = 'project:archive:view'
MANAGE = 'project:archive:notification:manage'
RETRY = 'project:archive:notification:retry'


def queue_archive_notice(db, change, event):
    user_id = change.approver_id if event == 'submitted' else change.author_id
    row = BusinessNotice(change_id=change.id, event=event, request_version=change.version, user_id=user_id)
    db.add(row); db.flush()
    db.add(BusinessNoticeMail(notice_id=row.id))


def live_context(db, context):
    current = build_authorization_context(db, context.get('user_id'))
    enforce_permission(current, VIEW)
    return current


def visible_changes(db, context):
    from app.services.archive_change import archive_change_query
    # Former approvers lose access when the owner/department's current route changes.
    current_head = select(PmsProjectArchive.id).join(SysUser, SysUser.id == PmsProjectArchive.manager_id).join(
        SysDept, SysDept.id == SysUser.dept_id).where(
        PmsProjectArchive.id == ArchiveChange.archive_id, SysUser.status == 1, SysDept.status == 1,
        SysDept.id == ArchiveChange.department_id, SysDept.leader_id == context['user_id']).exists()
    return archive_change_query(db, context).filter(or_(ArchiveChange.author_id == context['user_id'],
        and_(ArchiveChange.approver_id == context['user_id'], current_head)))


def personal_query(db, context):
    changes = visible_changes(db, context).with_entities(ArchiveChange.id).order_by(None).subquery()
    return db.query(BusinessNotice).filter(BusinessNotice.user_id == context['user_id'], BusinessNotice.change_id.in_(select(changes.c.id)))


def serialize_notices(db, rows):
    changes = {c.id:c for c in db.query(ArchiveChange).filter(ArchiveChange.id.in_({r.change_id for r in rows}))} if rows else {}
    archives = {a.id:a for a in db.query(PmsProjectArchive).filter(PmsProjectArchive.id.in_({c.archive_id for c in changes.values()}))} if changes else {}
    users = {u.id:u for u in db.query(SysUser).filter(SysUser.id.in_({i for c in changes.values() for i in (c.author_id,c.approver_id)}))} if changes else {}
    items = []
    for row in rows:
        change = changes[row.change_id]; archive = archives[change.archive_id]
        items.append({'id':row.id, 'change_id':row.change_id, 'event':row.event, 'request_version':row.request_version,
            'created_at':business_time(row.created_at), 'read_at':business_time(row.read_at), 'status':change.status,
            'project_code':archive.project_code, 'project_name':archive.project_name,
            'author_name':users[change.author_id].real_name or users[change.author_id].username,
            'approver_name':users[change.approver_id].real_name or users[change.approver_id].username})
    return items


def list_notices(db, context, *, page=1, page_size=50, unread_only=False):
    current = live_context(db, context)
    query = personal_query(db, current)
    unread = query.filter(BusinessNotice.read_at.is_(None)).count()
    if unread_only: query = query.filter(BusinessNotice.read_at.is_(None))
    return {'total':query.count(), 'unread':unread,
        'items':serialize_notices(db, query.order_by(BusinessNotice.id.desc()).offset((page-1)*page_size).limit(page_size).all())}


def get_notice(db, context, notice_id):
    row = personal_query(db, live_context(db, context)).filter(BusinessNotice.id == notice_id).first()
    if row is None: raise HTTPException(404, '通知不存在或无权访问')
    return serialize_notices(db, [row])[0]


def get_request(db, context, change_id):
    from app.services.archive_change import serialize_archive_changes
    current = live_context(db, context)
    row = visible_changes(db, current).filter(ArchiveChange.id == change_id).first()
    if row is None: raise HTTPException(404, '变更申请不存在或无权访问')
    return serialize_archive_changes(db, [row], current)[0]


def mark_read(db, context, notice_id, request=None):
    try:
        current = live_context(db, context)
        item = get_notice(db, current, notice_id)
        changed = db.execute(update(BusinessNotice).where(BusinessNotice.id == notice_id,
            BusinessNotice.user_id == current['user_id'], BusinessNotice.read_at.is_(None)).values(read_at=utc_now()))
        if changed.rowcount:
            record_operation_log(db, module='业务通知', action='read', entity_type='pms_business_notice',
                entity_id=notice_id, entity_name=item['project_code'], operator_id=current['user_id'], request=request,
                summary='标为已读', before_data={'read_at':None}, after_data={'read_at':db.get(BusinessNotice,notice_id).read_at})
        db.commit()
        return {'read':True}
    except Exception:
        db.rollback(); raise
