"""项目档案删除保护与启停生命周期服务。"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.project import ErpSyncLog, PmsProject, PmsProjectArchive
from app.services.operation_log import record_operation_log, serialize_model


def get_archive_delete_guard(db: Session, archive_id: int) -> dict[str, Any]:
    """获取单个项目档案的删除保护结果。"""
    return get_archive_delete_guards(db, [archive_id])[archive_id]


def get_archive_delete_guards(db: Session, archive_ids: list[int]) -> dict[int, dict[str, Any]]:
    """批量聚合项目引用、ERP 成功记录和同步中状态，避免逐档案查询。"""
    unique_ids = list(dict.fromkeys(archive_ids))
    if not unique_ids:
        return {}

    project_counts = dict(
        db.query(PmsProject.archive_id, func.count(PmsProject.id))
        .filter(PmsProject.archive_id.in_(unique_ids))
        .group_by(PmsProject.archive_id)
        .all()
    )
    sync_counts = dict(
        db.query(ErpSyncLog.source_id, func.count(ErpSyncLog.id))
        .filter(
            ErpSyncLog.source_id.in_(unique_ids),
            ErpSyncLog.status == "success",
        )
        .group_by(ErpSyncLog.source_id)
        .all()
    )
    archive_sync_states = {
        archive_id: (erp_synced, erp_sync_status)
        for archive_id, erp_synced, erp_sync_status in db.query(
            PmsProjectArchive.id,
            PmsProjectArchive.erp_synced,
            PmsProjectArchive.erp_sync_status,
        )
        .filter(PmsProjectArchive.id.in_(unique_ids))
        .all()
    }

    guards: dict[int, dict[str, Any]] = {}
    for archive_id in unique_ids:
        blockers: list[dict[str, Any]] = []
        erp_synced, erp_sync_status = archive_sync_states.get(archive_id, (0, None))
        if project_count := project_counts.get(archive_id, 0):
            blockers.append({
                "type": "business_reference",
                "source": "project_progress",
                "label": "项目进度",
                "count": project_count,
            })
        sync_count = sync_counts.get(archive_id, 0)
        if sync_count or erp_synced == 1:
            blockers.append({
                "type": "external_sync",
                "source": "kingdee",
                "label": "金蝶 ERP",
                "count": max(sync_count, int(erp_synced == 1)),
            })
        if erp_sync_status == "pending":
            blockers.append({
                "type": "operation_pending",
                "source": "kingdee",
                "label": "ERP 同步中",
                "count": 1,
            })
        guards[archive_id] = {
            "can_delete": len(blockers) == 0,
            "blockers": blockers,
        }
    return guards


def ensure_archive_enabled(archive: PmsProjectArchive, action_label: str) -> None:
    """拒绝对禁用项目档案执行写操作。"""
    if archive.is_enabled == 1:
        return
    raise HTTPException(status_code=409, detail={
        "code": "ARCHIVE_DISABLED",
        "message": f"项目档案已禁用，无法{action_label}，请先重新启用",
    })


def set_archive_enabled(
    db: Session,
    archive: PmsProjectArchive,
    enabled: bool,
    operator_id: int | None,
    request: Request | None,
) -> dict:
    """幂等地启用或禁用已通过访问校验的项目档案。"""
    target_enabled = int(enabled)
    action = "enable" if enabled else "disable"
    message = "启用成功" if enabled else "禁用成功"

    if archive.is_enabled == target_enabled:
        return {"msg": message}
    if not enabled and archive.erp_sync_status == "pending":
        raise HTTPException(status_code=409, detail={
            "code": "ARCHIVE_OPERATION_PENDING",
            "message": "项目档案正在同步，无法禁用，请等待同步完成",
        })

    before = serialize_model(archive)
    archive.is_enabled = target_enabled
    record_operation_log(
        db,
        module="项目档案",
        action=action,
        entity_type="pms_project_archive",
        entity_id=archive.id,
        entity_name=archive.project_name,
        operator_id=operator_id,
        request=request,
        summary=f"{'启用' if enabled else '禁用'}项目档案：{archive.project_name}",
        before_data=before,
        after_data=serialize_model(archive),
    )
    db.commit()
    return {"msg": message}
