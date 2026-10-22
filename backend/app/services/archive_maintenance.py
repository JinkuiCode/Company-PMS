"""Explicit maintenance privilege; never an administrator role-name bypass."""
from fastapi import HTTPException
from app.models.user import SysUser
from app.services.authorization import enforce_permission
from app.services.archive_change import (
    _check_version, _ensure_no_active, _relation, archive_business_values,
)
from app.services.operation_log import build_operation_log_diff_items, diff_data

MAINTENANCE_PERMISSIONS = ('project:archive:view', 'project:archive:edit', 'project:archive:maintain')


def maintenance_context(archive, scope, pending):
    allowed = bool(scope and scope.get('user_id') and all(
        permission in scope.get('permissions', []) for permission in MAINTENANCE_PERMISSIONS))
    reason = ('当前账号没有档案维护授权' if not allowed else
              '项目档案已禁用，仅供查看' if archive.is_enabled != 1 else
              '有变更申请待处理' if pending else
              '档案同步中或结果待核查，请处理后再维护' if archive.erp_sync_status in ('pending', 'review') else '')
    return {'can_maintain': not bool(reason), 'maintain_reason': reason}


def _prepare(db, archive_id, data, actor, scope):
    from app.services.project import _claim_enabled_archive_for_write, apply_archive_updates
    for permission in MAINTENANCE_PERMISSIONS:
        enforce_permission(scope or {}, permission)
    user = db.get(SysUser, actor)
    if not user or user.status != 1 or (scope or {}).get('user_id') != actor:
        raise HTTPException(403, '维护操作用户已失效或不匹配')
    from app.services.project import lock_archive_identity_update
    lock_archive_identity_update(db, data.updates)
    archive = _claim_enabled_archive_for_write(db, archive_id, scope,
        action_label='维护', reject_pending=True)
    _check_version(archive, data.expected_version)
    _ensure_no_active(db, archive.id)
    from app.services.project import _legacy_manager_address_context
    # Qualify ORIGINAL business keys before discarding unchanged values.
    address_context = _legacy_manager_address_context(archive,
        data.updates.model_dump(exclude_unset=True, exclude={'expected_version'}))
    updates = apply_archive_updates(db, archive.id, data.updates, actor,
        archive=archive, scope_context=scope, dry_run=True,
        _maintenance_address_context=address_context)
    current = archive_business_values(archive)
    updates = {key: value for key, value in updates.items() if current.get(key) != value}
    if not updates:
        raise HTTPException(422, '尚未修改业务字段')
    if 'manager_id' in updates:
        from types import SimpleNamespace
        owner, _, _ = _relation(db, SimpleNamespace(manager_id=updates['manager_id']))
        if not owner:
            raise HTTPException(422, detail={'field_key': 'manager_id',
                'message': '新负责人须有有效所属部门，且该部门已配置有效部门负责人'})
    differences = build_operation_log_diff_items(diff_data(current, {**current, **updates}),
        entity_type='pms_project_archive', entity_id=str(archive.id), db=db)
    return archive, updates, differences, address_context


def preview_archive_maintenance(db, archive_id, data, actor, *, scope_context):
    try:
        _, _, differences, _ = _prepare(db, archive_id, data, actor, scope_context)
        return {'mode': 'maintenance', 'expected_version': data.expected_version, 'differences': differences}
    finally:
        db.rollback()


def maintain_archive(db, archive_id, data, actor, *, scope_context, request=None):
    from app.schemas.project import ArchiveUpdate
    from app.services.project import apply_archive_updates
    try:
        archive, updates, _, address_context = _prepare(db, archive_id, data, actor, scope_context)
        result = apply_archive_updates(db, archive_id, ArchiveUpdate(**updates), actor,
            archive=archive, scope_context=scope_context, request=request, commit=False,
            audit_action='maintain', audit_summary=f'档案维护：{data.reason}',
            audit_extra={'maintenance': {'reason': data.reason,
                'authorization_permissions': list(MAINTENANCE_PERMISSIONS)}},
            queue_permission='project:archive:maintain',
            _maintenance_address_context=address_context)
        db.commit()
        return {**result, 'mode': 'maintenance'}
    except Exception:
        db.rollback()
        raise
