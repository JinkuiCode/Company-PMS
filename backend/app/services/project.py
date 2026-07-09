"""项目管理业务逻辑"""
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from fastapi import HTTPException, Request

from app.models.project import PmsProject, PmsTask, PmsProgressLog, PmsProjectArchive, PmsProjectSheetDetail
from app.models.user import SysUser
from app.models.rbac import SysDept
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    TaskCreate, TaskUpdate, TaskResponse,
    ArchiveCreate, ArchiveUpdate, ArchiveResponse, ArchiveOption, ProjectSheetDetailUpdate,
)
from app.services.operation_log import record_operation_log, serialize_model
from app.services.project_sheet_fields import (
    build_sheet_detail_groups,
    compute_sheet_field_value,
    FIELD_BY_KEY,
    get_project_sheet_field_metadata as get_project_sheet_field_registry_metadata,
    normalize_sheet_field_keys,
    validate_sheet_detail_updates,
)


def get_child_dept_ids(db: Session, parent_id: int) -> list[int]:
    """递归获取某部门及其所有子部门 ID 列表"""
    result = [parent_id]
    children = db.query(SysDept).filter(SysDept.parent_id == parent_id).all()
    for child in children:
        result.extend(get_child_dept_ids(db, child.id))
    return result


def _apply_project_scope(query, db: Session, scope_context: dict | None = None):
    if not scope_context:
        return query

    scope = scope_context["data_scope"]
    if scope == 1:
        query = query.filter(PmsProject.pm_id == scope_context["user_id"])
    elif scope == 2:
        if scope_context["dept_id"]:
            query = query.filter(PmsProject.dept_id == scope_context["dept_id"])
    elif scope == 3:
        if scope_context["dept_id"]:
            allowed_depts = get_child_dept_ids(db, scope_context["dept_id"])
            query = query.filter(PmsProject.dept_id.in_(allowed_depts))

    allowed_lines = scope_context.get("product_lines")
    if allowed_lines is not None:
        query = query.outerjoin(PmsProjectArchive, PmsProject.archive_id == PmsProjectArchive.id).filter(
            or_(
                PmsProjectArchive.product_line.in_(allowed_lines),
                PmsProject.product_line.in_(allowed_lines),
            )
        )
    return query


def _jsonable(value):
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _load_detail_data(detail: PmsProjectSheetDetail | None) -> dict:
    if not detail or not detail.detail_data:
        return {}
    try:
        parsed = json.loads(detail.detail_data)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _dump_detail_data(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, default=_jsonable)


def get_project_sheet_field_metadata() -> dict[str, list[dict[str, Any]]]:
    return get_project_sheet_field_registry_metadata()


def _build_project_sheet_values(
    project: PmsProject,
    detail: PmsProjectSheetDetail | None,
    archive: PmsProjectArchive | None = None,
    dept: SysDept | None = None,
    pm: SysUser | None = None,
    editor: SysUser | None = None,
) -> dict[str, Any]:
    values = _load_detail_data(detail)
    values.update({
        "project_code": archive.project_code if archive else project.project_code,
        "project_name": archive.project_name if archive else project.project_name,
        "product_line": archive.product_line if archive and archive.product_line else project.product_line,
        "product_type": archive.product_type if archive else None,
        "node_status": project.status,
        "project_start_date": project.start_date,
        "original_planned_ship_date": project.end_date,
        "pm_name": pm.real_name if pm else "",
        "dept_name": dept.dept_name if dept else "",
        "design_progress": project.design_progress,
        "order_progress": project.order_progress,
        "kit_progress": project.kit_progress,
        "frame_progress": project.frame_progress,
        "dryer_progress": project.dryer_progress,
        "assembly_progress": project.assembly_progress,
        "test_progress": project.test_progress,
        "last_editor": editor.real_name if editor else "",
        "last_edit_time": detail.updated_at if detail else project.updated_at,
    })
    return {key: _jsonable(value) for key, value in values.items()}


def _project_sheet_values(db: Session, project: PmsProject, detail: PmsProjectSheetDetail | None) -> dict[str, Any]:
    archive = db.query(PmsProjectArchive).filter(PmsProjectArchive.id == project.archive_id).first() if project.archive_id else None
    dept = db.query(SysDept).filter(SysDept.id == project.dept_id).first()
    pm = db.query(SysUser).filter(SysUser.id == project.pm_id).first()
    editor = db.query(SysUser).filter(SysUser.id == detail.updated_by).first() if detail and detail.updated_by else None
    return _build_project_sheet_values(project, detail, archive=archive, dept=dept, pm=pm, editor=editor)


def _project_sheet_projection(values: dict[str, Any], requested_keys: list[str]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key in requested_keys:
        projected[key] = compute_sheet_field_value(key, values) if FIELD_BY_KEY[key]["computed"] else values.get(key)
    return projected


# ==================== 项目 ====================
def get_project_list(db: Session, page: int = 1, page_size: int = 15,
                     dept_id: int | None = None, status: int | None = None,
                     sheet_field_keys: str | list[str] | tuple[str, ...] | None = None,
                     scope_context: dict | None = None):
    query = _apply_project_scope(db.query(PmsProject), db, scope_context)
    if dept_id:
        query = query.filter(PmsProject.dept_id == dept_id)
    if status:
        query = query.filter(PmsProject.status == status)

    total = query.count()
    projects = query.order_by(PmsProject.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    if not projects:
        return {"total": total, "items": []}

    requested_sheet_keys = normalize_sheet_field_keys(sheet_field_keys)
    project_ids = [project.id for project in projects]
    dept_ids = sorted({project.dept_id for project in projects})
    pm_ids = sorted({project.pm_id for project in projects})
    archive_ids = sorted({project.archive_id for project in projects if project.archive_id})

    dept_map = {
        dept.id: dept
        for dept in db.query(SysDept).filter(SysDept.id.in_(dept_ids)).all()
    }
    pm_map = {
        user.id: user
        for user in db.query(SysUser).filter(SysUser.id.in_(pm_ids)).all()
    }
    archive_map = {
        archive.id: archive
        for archive in db.query(PmsProjectArchive).filter(PmsProjectArchive.id.in_(archive_ids)).all()
    } if archive_ids else {}
    detail_map = {
        detail.project_id: detail
        for detail in db.query(PmsProjectSheetDetail).filter(PmsProjectSheetDetail.project_id.in_(project_ids)).all()
    }
    task_stats = {
        row.project_id: {
            "task_count": int(row.task_count or 0),
            "avg_progress": round(float(row.avg_progress or 0), 1),
        }
        for row in db.query(
            PmsTask.project_id.label("project_id"),
            func.count(PmsTask.id).label("task_count"),
            func.avg(PmsTask.progress).label("avg_progress"),
        ).filter(
            PmsTask.project_id.in_(project_ids)
        ).group_by(
            PmsTask.project_id
        ).all()
    }

    items = []
    for p in projects:
        dept = dept_map.get(p.dept_id)
        pm = pm_map.get(p.pm_id)
        archive = archive_map.get(p.archive_id) if p.archive_id else None
        detail = detail_map.get(p.id)
        stats = task_stats.get(p.id, {"task_count": 0, "avg_progress": 0.0})
        sheet_fields: dict[str, Any] = {}
        if requested_sheet_keys:
            values = _build_project_sheet_values(
                p,
                detail,
                archive=archive,
                dept=dept,
                pm=pm,
            )
            sheet_fields = _project_sheet_projection(values, requested_sheet_keys)

        items.append(ProjectResponse(
            id=p.id, project_code=p.project_code, project_name=p.project_name,
            dept_id=p.dept_id, pm_id=p.pm_id, status=p.status,
            start_date=p.start_date, end_date=p.end_date,
            budget=p.budget, description=p.description,
            design_progress=p.design_progress,
            order_progress=p.order_progress,
            kit_progress=p.kit_progress,
            frame_progress=p.frame_progress,
            dryer_progress=p.dryer_progress,
            assembly_progress=p.assembly_progress,
            test_progress=p.test_progress,
            dept_name=dept.dept_name if dept else "",
            pm_name=pm.real_name if pm else "",
            product_line=archive.product_line if archive and archive.product_line else p.product_line,
            task_count=stats["task_count"], total_progress=stats["avg_progress"],
            sheet_fields=sheet_fields,
            created_at=p.created_at, updated_at=p.updated_at,
        ))
    return {"total": total, "items": items}


def get_project_sheet_detail(db: Session, project_id: int, scope_context: dict | None = None):
    query = db.query(PmsProject).filter(PmsProject.id == project_id)
    project = _apply_project_scope(query, db, scope_context).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    detail = db.query(PmsProjectSheetDetail).filter(PmsProjectSheetDetail.project_id == project_id).first()
    values = _project_sheet_values(db, project, detail)
    return {
        "project_id": project_id,
        "groups": build_sheet_detail_groups(values),
        "updated_at": detail.updated_at if detail else None,
    }


def update_project_sheet_detail(
    db: Session,
    project_id: int,
    data: ProjectSheetDetailUpdate,
    operator_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
):
    query = db.query(PmsProject).filter(PmsProject.id == project_id)
    project = _apply_project_scope(query, db, scope_context).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    try:
        update_data = validate_sheet_detail_updates(data.values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    detail = db.query(PmsProjectSheetDetail).filter(PmsProjectSheetDetail.project_id == project_id).first()
    if not detail:
        detail = PmsProjectSheetDetail(project_id=project_id, created_by=operator_id, updated_by=operator_id)
        db.add(detail)
        db.flush()

    before_data = _load_detail_data(detail)
    after_data = {**before_data, **update_data}
    detail.detail_data = _dump_detail_data(after_data)
    detail.updated_by = operator_id

    record_operation_log(
        db,
        module="项目进度",
        action="update",
        entity_type="pms_project_sheet_detail",
        entity_id=detail.id,
        entity_name=project.project_name,
        operator_id=operator_id,
        request=request,
        summary=f"更新项目总表详情：{project.project_name}",
        before_data=before_data,
        after_data=after_data,
    )
    db.commit()
    return get_project_sheet_detail(db, project_id)


def create_project(db: Session, data: ProjectCreate, operator_id: int | None = None, request: Request | None = None):
    if db.query(PmsProject).filter(PmsProject.project_code == data.project_code).first():
        raise HTTPException(status_code=400, detail="项目编号已存在")
    proj = PmsProject(**data.model_dump())
    db.add(proj)
    db.flush()
    record_operation_log(
        db,
        module="项目进度",
        action="create",
        entity_type="pms_project",
        entity_id=proj.id,
        entity_name=proj.project_name,
        operator_id=operator_id,
        request=request,
        summary=f"创建项目进度：{proj.project_name}",
        after_data=serialize_model(proj),
    )
    db.commit()
    db.refresh(proj)
    return {"msg": "创建成功", "id": proj.id}


def update_project(db: Session, project_id: int, data: ProjectUpdate, user_id: int | None = None, request: Request | None = None):
    proj = db.query(PmsProject).filter(PmsProject.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    before = serialize_model(proj)
    update_data = data.model_dump(exclude_unset=True)

    product_line_is_set = "product_line" in update_data
    product_line_value = update_data.pop("product_line", None)

    for key, val in update_data.items():
        setattr(proj, key, val)

    if product_line_is_set:
        proj.product_line = product_line_value
        if proj.archive_id:
            archive = db.query(PmsProjectArchive).filter(PmsProjectArchive.id == proj.archive_id).first()
            if archive:
                archive_before = serialize_model(archive)
                archive.product_line = product_line_value
                if user_id is not None:
                    archive.updated_by = user_id
                record_operation_log(
                    db,
                    module="项目档案",
                    action="update",
                    entity_type="pms_project_archive",
                    entity_id=archive.id,
                    entity_name=archive.project_name,
                    operator_id=user_id,
                    request=request,
                    summary=f"项目进度联动更新档案产品线：{archive.project_name}",
                    before_data=archive_before,
                    after_data=serialize_model(archive),
                )

    record_operation_log(
        db,
        module="项目进度",
        action="update",
        entity_type="pms_project",
        entity_id=proj.id,
        entity_name=proj.project_name,
        operator_id=user_id,
        request=request,
        summary=f"更新项目进度：{proj.project_name}",
        before_data=before,
        after_data=serialize_model(proj),
    )
    db.commit()
    return {"msg": "更新成功"}


def delete_project(db: Session, project_id: int, operator_id: int | None = None, request: Request | None = None):
    proj = db.query(PmsProject).filter(PmsProject.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    before = serialize_model(proj, extra={"task_count": db.query(PmsTask).filter(PmsTask.project_id == project_id).count()})
    db.query(PmsTask).filter(PmsTask.project_id == project_id).delete()
    db.delete(proj)
    record_operation_log(
        db,
        module="项目进度",
        action="delete",
        entity_type="pms_project",
        entity_id=project_id,
        entity_name=proj.project_name,
        operator_id=operator_id,
        request=request,
        summary=f"删除项目进度：{proj.project_name}",
        before_data=before,
    )
    db.commit()
    return {"msg": "删除成功"}


# ==================== 任务 & 进度 ====================
def get_tasks(db: Session, project_id: int,
              scope_context: dict | None = None) -> list[TaskResponse]:
    # JOIN 项目表以应用数据权限
    query = db.query(PmsTask).join(PmsProject, PmsTask.project_id == PmsProject.id)

    if scope_context:
        scope = scope_context["data_scope"]
        if scope == 1:
            query = query.filter(PmsProject.pm_id == scope_context["user_id"])
        elif scope == 2:
            if scope_context["dept_id"]:
                query = query.filter(PmsProject.dept_id == scope_context["dept_id"])
        elif scope == 3:
            if scope_context["dept_id"]:
                allowed_depts = get_child_dept_ids(db, scope_context["dept_id"])
                query = query.filter(PmsProject.dept_id.in_(allowed_depts))
        # scope == 4: 不附加过滤

    query = query.filter(PmsTask.project_id == project_id)
    tasks = query.order_by(PmsTask.sort, PmsTask.id).all()
    result = []
    for t in tasks:
        user = db.query(SysUser).filter(SysUser.id == t.assignee_id).first()
        result.append(TaskResponse(
            id=t.id, project_id=t.project_id, task_name=t.task_name,
            assignee_id=t.assignee_id, progress=t.progress, status=t.status,
            start_date=t.start_date, due_date=t.due_date, parent_id=t.parent_id, sort=t.sort,
            assignee_name=user.real_name if user else "",
            created_at=t.created_at, updated_at=t.updated_at,
        ))
    return result


def create_task(db: Session, data: TaskCreate, operator_id: int | None = None, request: Request | None = None):
    task = PmsTask(**data.model_dump())
    db.add(task)
    db.flush()
    record_operation_log(
        db,
        module="项目进度",
        action="create",
        entity_type="pms_task",
        entity_id=task.id,
        entity_name=task.task_name,
        operator_id=operator_id,
        request=request,
        summary=f"创建项目任务：{task.task_name}",
        after_data=serialize_model(task),
    )
    db.commit()
    db.refresh(task)
    return {"msg": "创建成功", "id": task.id}


def update_task(db: Session, task_id: int, data: TaskUpdate, operator_id: int, request: Request | None = None):
    task = db.query(PmsTask).filter(PmsTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    old_progress = task.progress
    before = serialize_model(task)

    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(task, key, val)

    # 如果进度发生变化，记录日志
    if "progress" in update_data and update_data["progress"] != old_progress:
        log = PmsProgressLog(
            task_id=task_id, old_progress=old_progress, new_progress=update_data["progress"],
            operator_id=operator_id,
        )
        db.add(log)

    record_operation_log(
        db,
        module="项目进度",
        action="update",
        entity_type="pms_task",
        entity_id=task.id,
        entity_name=task.task_name,
        operator_id=operator_id,
        request=request,
        summary=f"更新项目任务：{task.task_name}",
        before_data=before,
        after_data=serialize_model(task),
    )
    db.commit()
    return {"msg": "更新成功", "id": task.id}


def delete_task(db: Session, task_id: int, operator_id: int | None = None, request: Request | None = None):
    task = db.query(PmsTask).filter(PmsTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    before = serialize_model(task)
    db.query(PmsProgressLog).filter(PmsProgressLog.task_id == task_id).delete()
    db.delete(task)
    record_operation_log(
        db,
        module="项目进度",
        action="delete",
        entity_type="pms_task",
        entity_id=task_id,
        entity_name=task.task_name,
        operator_id=operator_id,
        request=request,
        summary=f"删除项目任务：{task.task_name}",
        before_data=before,
    )
    db.commit()
    return {"msg": "删除成功"}


def get_progress_logs(db: Session, task_id: int) -> list[dict]:
    logs = db.query(PmsProgressLog).filter(PmsProgressLog.task_id == task_id).order_by(PmsProgressLog.created_at.desc()).all()
    return [
        {"id": l.id, "task_id": l.task_id, "old_progress": l.old_progress,
         "new_progress": l.new_progress, "operator_id": l.operator_id,
         "remark": l.remark, "created_at": str(l.created_at)}
        for l in logs
    ]


# ==================== 项目档案 ====================
def get_archive_list(db: Session, page: int = 1, page_size: int = 15,
                     keyword: str | None = None, status: int | None = None,
                     product_line: str | None = None,
                     allowed_lines: list[str] | None = None):
    """查询项目档案列表"""
    query = db.query(PmsProjectArchive)

    if keyword:
        query = query.filter(
            (PmsProjectArchive.project_code.contains(keyword)) |
            (PmsProjectArchive.project_name.contains(keyword))
        )
    if status is not None:
        query = query.filter(PmsProjectArchive.status == status)
    if product_line:
        query = query.filter(PmsProjectArchive.product_line == product_line)
    # 产品线权限过滤
    if allowed_lines is not None:
        query = query.filter(PmsProjectArchive.product_line.in_(allowed_lines))

    total = query.count()
    rows = query.order_by(PmsProjectArchive.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for a in rows:
        manager = db.query(SysUser).filter(SysUser.id == a.manager_id).first()
        creator = db.query(SysUser).filter(SysUser.id == a.created_by).first()
        editor = db.query(SysUser).filter(SysUser.id == a.updated_by).first()
        syncer = db.query(SysUser).filter(SysUser.id == a.erp_sync_by).first() if a.erp_sync_by else None
        items.append(ArchiveResponse(
            id=a.id, project_code=a.project_code, project_name=a.project_name,
            status=a.status, manager_id=a.manager_id, product_type=a.product_type,
            product_line=a.product_line,
            plan_start_date=a.plan_start_date, plan_end_date=a.plan_end_date,
            manager_name=manager.real_name if manager else "",
            created_by_name=creator.real_name if creator else "",
            updated_by_name=editor.real_name if editor else "",
            erp_synced=a.erp_synced, erp_sync_time=a.erp_sync_time,
            erp_sync_by_name=syncer.real_name if syncer else "",
            erp_sync_status=a.erp_sync_status, erp_error_msg=a.erp_error_msg,
            created_at=a.created_at, updated_at=a.updated_at,
        ))
    return {"total": total, "items": items}


def get_archive_options(db: Session):
    """获取档案下拉选项（精简版，不分页）"""
    rows = db.query(PmsProjectArchive).order_by(PmsProjectArchive.project_code).all()
    return [ArchiveOption(id=a.id, project_code=a.project_code, project_name=a.project_name) for a in rows]


def create_archive(db: Session, data: ArchiveCreate, user_id: int, request: Request | None = None):
    """创建项目档案"""
    if db.query(PmsProjectArchive).filter(PmsProjectArchive.project_code == data.project_code).first():
        raise HTTPException(status_code=400, detail="项目编号已存在")
    archive = PmsProjectArchive(**data.model_dump(), created_by=user_id, updated_by=user_id)
    db.add(archive)
    db.flush()
    record_operation_log(
        db,
        module="项目档案",
        action="create",
        entity_type="pms_project_archive",
        entity_id=archive.id,
        entity_name=archive.project_name,
        operator_id=user_id,
        request=request,
        summary=f"创建项目档案：{archive.project_name}",
        after_data=serialize_model(archive),
    )
    db.commit()
    db.refresh(archive)
    return {"msg": "创建成功", "id": archive.id}


def update_archive(db: Session, archive_id: int, data: ArchiveUpdate, user_id: int, request: Request | None = None):
    """更新项目档案"""
    archive = db.query(PmsProjectArchive).filter(PmsProjectArchive.id == archive_id).first()
    if not archive:
        raise HTTPException(status_code=404, detail="档案不存在")
    before = serialize_model(archive)

    update_data = data.model_dump(exclude_unset=True)
    # 项目编号唯一性校验
    if "project_code" in update_data and update_data["project_code"] != archive.project_code:
        if db.query(PmsProjectArchive).filter(PmsProjectArchive.project_code == update_data["project_code"]).first():
            raise HTTPException(status_code=400, detail="项目编号已存在")

    for key, val in update_data.items():
        setattr(archive, key, val)
    archive.updated_by = user_id
    record_operation_log(
        db,
        module="项目档案",
        action="update",
        entity_type="pms_project_archive",
        entity_id=archive.id,
        entity_name=archive.project_name,
        operator_id=user_id,
        request=request,
        summary=f"更新项目档案：{archive.project_name}",
        before_data=before,
        after_data=serialize_model(archive),
    )
    db.commit()
    return {"msg": "更新成功"}


def delete_archive(db: Session, archive_id: int, operator_id: int | None = None, request: Request | None = None):
    """删除项目档案（需检查是否被项目引用）"""
    archive = db.query(PmsProjectArchive).filter(PmsProjectArchive.id == archive_id).first()
    if not archive:
        raise HTTPException(status_code=404, detail="档案不存在")
    before = serialize_model(archive)

    # 检查是否被项目进度引用
    ref_count = db.query(PmsProject).filter(PmsProject.archive_id == archive_id).count()
    if ref_count > 0:
        raise HTTPException(status_code=400, detail=f"该档案已被 {ref_count} 个项目引用，无法删除")

    db.delete(archive)
    record_operation_log(
        db,
        module="项目档案",
        action="delete",
        entity_type="pms_project_archive",
        entity_id=archive_id,
        entity_name=archive.project_name,
        operator_id=operator_id,
        request=request,
        summary=f"删除项目档案：{archive.project_name}",
        before_data=before,
    )
    db.commit()
    return {"msg": "删除成功"}
