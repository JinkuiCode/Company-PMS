"""Explicit, live authorization for an ERP outbox execution identity."""
import json
from fastapi import HTTPException
from app.services.authorization import build_authorization_context, enforce_permission

ACTION_PERMISSIONS = frozenset({
    'project:archive:add', 'project:archive:edit', 'project:archive:sync',
    'project:archive:maintain', 'system:sync:retry',
})


def task_permissions(action):
    if action not in ACTION_PERMISSIONS:
        raise ValueError('不支持的同步授权来源')
    return ([action, 'project:archive:view', 'project:archive:edit']
            if action == 'project:archive:maintain' else [action])


def authorization_changed():
    return HTTPException(403, detail={
        'code': 'ERP_TASK_AUTH_CHANGED',
        'message': '原操作人或授权已变化，未发送金蝶请求；请重新授权后提交或重试',
    })


def authorize_task_execution(db, task, archive):
    """Do not infer a system identity or unrestricted scope from missing metadata."""
    from app.services.project import ensure_archive_access
    db.expire_all()
    if task is None or task.operator_id is None or archive is None or task.archive_id != archive.id:
        raise authorization_changed()
    try:
        history = json.loads(task.history or '[]')
        source = history[0]['authorization']
        action = source['action']
        expected = {'action': action, 'permissions': task_permissions(action)}
        if source != expected:
            raise ValueError('授权来源不完整')
    except (TypeError, ValueError, IndexError, KeyError):
        raise authorization_changed() from None
    try:
        context = build_authorization_context(db, task.operator_id)
        for permission in expected['permissions']:
            enforce_permission(context, permission)
        ensure_archive_access(db, archive.id, context)
    except HTTPException:
        raise authorization_changed() from None
    return context
