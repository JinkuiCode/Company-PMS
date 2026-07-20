"""项目管理业务逻辑"""
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
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
from app.services.project_archive_lifecycle import (
    apply_archive_lifecycle_lock,
    archive_not_pending_condition,
    ensure_archive_enabled,
    get_archive_delete_guard,
    get_archive_delete_guards,
    set_archive_enabled,
)
from app.services.enum_registry import validate_enum_value
from app.services.project_sheet_fields import (
    build_sheet_detail_groups,
    compute_sheet_field_value,
    FIELD_BY_KEY,
    get_project_sheet_field_metadata as get_project_sheet_field_registry_metadata,
    normalize_sheet_field_keys,
    validate_sheet_detail_updates,
)
from app.services.field_policy import (
    MODULE_PROJECT_ARCHIVE,
    MODULE_PROJECT_PROGRESS,
    get_effective_field_policies,
    validate_business_field_write,
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
        else:
            query = query.filter(PmsProject.id == -1)
    elif scope == 3:
        if scope_context["dept_id"]:
            allowed_depts = get_child_dept_ids(db, scope_context["dept_id"])
            query = query.filter(PmsProject.dept_id.in_(allowed_depts))
        else:
            query = query.filter(PmsProject.id == -1)

    allowed_category_ids = scope_context.get("product_category_ids")
    if allowed_category_ids is not None:
        query = query.outerjoin(PmsProjectArchive, PmsProject.archive_id == PmsProjectArchive.id).filter(
            or_(
                PmsProjectArchive.product_category.in_(allowed_category_ids),
                and_(
                    PmsProjectArchive.product_category.is_(None),
                    PmsProject.product_category.in_(allowed_category_ids),
                ),
            )
        )
    return query


def _apply_archive_scope(query, db: Session, scope_context: dict | None = None):
    if not scope_context:
        return query

    scope = scope_context["data_scope"]
    if scope == 1:
        query = query.filter(PmsProjectArchive.manager_id == scope_context["user_id"])
    elif scope in (2, 3):
        dept_id = scope_context.get("dept_id")
        if not dept_id:
            return query.filter(PmsProjectArchive.id == -1)
        allowed_depts = [dept_id] if scope == 2 else get_child_dept_ids(db, dept_id)
        manager_ids = [user_id for (user_id,) in db.query(SysUser.id).filter(
            SysUser.dept_id.in_(allowed_depts),
            SysUser.status == 1,
        ).all()]
        query = query.filter(PmsProjectArchive.manager_id.in_(manager_ids or [-1]))

    allowed_category_ids = scope_context.get("product_category_ids")
    if allowed_category_ids is not None:
        query = query.filter(PmsProjectArchive.product_category.in_(allowed_category_ids or [-1]))
    return query


def ensure_project_access(db: Session, project_id: int, scope_context: dict | None = None) -> PmsProject:
    project = _apply_project_scope(
        db.query(PmsProject).filter(PmsProject.id == project_id), db, scope_context
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")
    return project


def ensure_archive_access(
    db: Session,
    archive_id: int,
    scope_context: dict | None = None,
) -> PmsProjectArchive:
    archive = _apply_archive_scope(
        db.query(PmsProjectArchive).filter(PmsProjectArchive.id == archive_id), db, scope_context
    ).first()
    if not archive:
        raise HTTPException(status_code=404, detail="档案不存在或无权访问")
    return archive


def _ensure_product_category_allowed(product_category: int | None, scope_context: dict | None) -> None:
    if not scope_context:
        return
    allowed_category_ids = scope_context.get("product_category_ids")
    if allowed_category_ids is not None and product_category not in allowed_category_ids:
        raise HTTPException(status_code=404, detail="产品类别超出当前数据权限")


def _ensure_project_assignment_allowed(
    db: Session,
    *,
    dept_id: int | None,
    pm_id: int | None,
    product_category: int | None,
    scope_context: dict | None,
) -> None:
    if not scope_context:
        return
    scope = scope_context["data_scope"]
    if scope == 1 and pm_id != scope_context["user_id"]:
        raise HTTPException(status_code=404, detail="项目负责人超出当前数据权限")
    if scope in (2, 3):
        current_dept = scope_context.get("dept_id")
        allowed_depts = [] if not current_dept else (
            [current_dept] if scope == 2 else get_child_dept_ids(db, current_dept)
        )
        if dept_id not in allowed_depts:
            raise HTTPException(status_code=404, detail="项目部门超出当前数据权限")
    _ensure_product_category_allowed(product_category, scope_context)


def _ensure_archive_assignment_allowed(
    db: Session,
    *,
    manager_id: int | None,
    product_category: int | None,
    scope_context: dict | None,
) -> None:
    if not scope_context:
        return
    scope = scope_context["data_scope"]
    if scope == 1 and manager_id != scope_context["user_id"]:
        raise HTTPException(status_code=404, detail="档案负责人超出当前数据权限")
    if scope in (2, 3):
        manager = db.query(SysUser).filter(SysUser.id == manager_id, SysUser.status == 1).first()
        current_dept = scope_context.get("dept_id")
        allowed_depts = [] if not current_dept else (
            [current_dept] if scope == 2 else get_child_dept_ids(db, current_dept)
        )
        if not manager or manager.dept_id not in allowed_depts:
            raise HTTPException(status_code=404, detail="档案负责人超出当前数据权限")
    _ensure_product_category_allowed(product_category, scope_context)


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


def _policy_map(db: Session, module_code: str) -> dict[str, dict[str, Any]]:
    effective = get_effective_field_policies(db, module_code)
    return {item["field_key"]: item for item in effective["items"]}


def get_project_sheet_field_metadata(db: Session) -> dict[str, Any]:
    metadata = get_project_sheet_field_registry_metadata()
    effective = get_effective_field_policies(db, MODULE_PROJECT_PROGRESS)
    policies = {item["field_key"]: item for item in effective["items"]}
    visible_fields: list[dict[str, Any]] = []
    for field in metadata["fields"]:
        policy = policies.get(field["key"])
        if not policy or not policy["visible"]:
            continue
        visible_fields.append({
            **field,
            "visible": policy["visible"],
            "editable": bool(field["editable"] and policy["editable"]),
            "required": policy["required"],
            "list_available": bool(field["list_available"] and policy["list_available"]),
            "quick_addable": bool(field["quick_addable"] and policy["list_available"]),
        })
    field_map = {field["key"]: field for field in visible_fields}
    groups = [
        {
            **group,
            "fields": [field_map[field["key"]] for field in group["fields"] if field["key"] in field_map],
        }
        for group in metadata["groups"]
    ]
    return {"groups": groups, "fields": visible_fields, "policies": effective["items"]}


def get_archive_field_metadata(db: Session) -> dict[str, Any]:
    return get_effective_field_policies(db, MODULE_PROJECT_ARCHIVE)


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
        "customer": archive.customer if archive else None,
        "product_category": archive.product_category if archive and archive.product_category else project.product_category,
        "equipment_series": archive.equipment_series if archive else None,
        "serial_no": archive.serial_no if archive else None,
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

    allowed_sheet_keys = {
        item["field_key"]
        for item in get_effective_field_policies(db, MODULE_PROJECT_PROGRESS)["items"]
        if item["visible"] and item["list_available"]
    }
    requested_sheet_keys = [
        key for key in normalize_sheet_field_keys(sheet_field_keys) if key in allowed_sheet_keys
    ]
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
            product_category=archive.product_category if archive and archive.product_category else p.product_category,
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
    policies = _policy_map(db, MODULE_PROJECT_PROGRESS)
    groups = build_sheet_detail_groups(values)
    for group in groups:
        governed_fields = []
        for field in group["fields"]:
            policy = policies.get(field["key"])
            if not policy or not policy["visible"]:
                continue
            governed_fields.append({
                **field,
                "visible": policy["visible"],
                "editable": bool(field["editable"] and policy["editable"]),
                "required": policy["required"],
                "list_available": bool(field["list_available"] and policy["list_available"]),
                "quick_addable": bool(field["quick_addable"] and policy["list_available"]),
            })
        group["fields"] = governed_fields
    return {
        "project_id": project_id,
        "groups": groups,
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
        detail_updates = validate_sheet_detail_updates(data.values)
        project_updates = validate_project_progress_workbench_updates(
            data.project_values.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not detail_updates and not project_updates:
        return get_project_sheet_detail(db, project_id, scope_context=scope_context)

    if "status" in project_updates:
        validate_enum_value(
            db,
            "project_status",
            project_updates["status"],
            current_value=project.status,
        )

    detail = db.query(PmsProjectSheetDetail).filter(PmsProjectSheetDetail.project_id == project_id).first()
    before_data = _load_detail_data(detail)
    after_data = {**before_data, **detail_updates}
    current_policy_values = _project_policy_values(db, project, detail)
    validate_business_field_write(
        db,
        MODULE_PROJECT_PROGRESS,
        current_values=current_policy_values,
        updates={**_project_updates_to_policy_values(project_updates), **detail_updates},
        entity_created_at=project.created_at,
        is_create=False,
    )
    before_snapshot = {
        **{f"project.{key}": getattr(project, key) for key in project_updates},
        **{f"detail.{key}": before_data.get(key) for key in detail_updates},
    }

    try:
        for key, value in project_updates.items():
            setattr(project, key, value)

        if detail_updates:
            if not detail:
                detail = PmsProjectSheetDetail(project_id=project_id, created_by=operator_id, updated_by=operator_id)
                db.add(detail)
                db.flush()
            detail.detail_data = _dump_detail_data(after_data)
            detail.updated_by = operator_id

        db.flush()
        after_snapshot = {
            **{f"project.{key}": getattr(project, key) for key in project_updates},
            **{f"detail.{key}": after_data.get(key) for key in detail_updates},
        }
        record_operation_log(
            db,
            module="项目进度",
            action="update",
            entity_type="pms_project",
            entity_id=project.id,
            entity_name=project.project_name,
            operator_id=operator_id,
            request=request,
            summary=f"统一保存项目进度详情：{project.project_name}",
            before_data=before_snapshot,
            after_data=after_snapshot,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_project_sheet_detail(db, project_id, scope_context=scope_context)


PROJECT_PROGRESS_WORKBENCH_EDITABLE_FIELDS = {
    "status",
    "start_date",
    "end_date",
    "design_progress",
    "order_progress",
    "kit_progress",
    "frame_progress",
    "dryer_progress",
    "assembly_progress",
    "test_progress",
}


def validate_project_progress_workbench_updates(values: dict[str, Any]) -> dict[str, Any]:
    """阻止项目进度页绕过字段来源修改项目档案或主数据。"""
    accepted: dict[str, Any] = {}
    for key, value in values.items():
        if key not in PROJECT_PROGRESS_WORKBENCH_EDITABLE_FIELDS:
            if key in {"project_code", "project_name", "product_category", "archive_id", "dept_id", "pm_id", "budget"}:
                raise ValueError(f"字段不可编辑：{key}")
            raise ValueError(f"未知字段：{key}")
        accepted[key] = value
    return accepted


PROJECT_TO_POLICY_FIELD = {
    "status": "node_status",
    "start_date": "project_start_date",
    "end_date": "original_planned_ship_date",
    "design_progress": "design_progress",
    "order_progress": "order_progress",
    "kit_progress": "kit_progress",
    "frame_progress": "frame_progress",
    "dryer_progress": "dryer_progress",
    "assembly_progress": "assembly_progress",
    "test_progress": "test_progress",
    "archive_id": "archive_id",
    "project_code": "project_code",
    "project_name": "project_name",
    "product_category": "product_category",
    "dept_id": "dept_id",
    "pm_id": "pm_id",
    "budget": "budget",
    "description": "description",
}


def _project_updates_to_policy_values(values: dict[str, Any]) -> dict[str, Any]:
    return {
        PROJECT_TO_POLICY_FIELD[key]: value
        for key, value in values.items()
        if key in PROJECT_TO_POLICY_FIELD
    }


def _project_policy_values(
    db: Session,
    project: PmsProject,
    detail: PmsProjectSheetDetail | None = None,
) -> dict[str, Any]:
    values = _project_sheet_values(db, project, detail)
    values.update({
        "archive_id": project.archive_id,
        "dept_id": project.dept_id,
        "pm_id": project.pm_id,
        "budget": _jsonable(project.budget),
        "description": project.description,
    })
    return values


def create_project(
    db: Session,
    data: ProjectCreate,
    operator_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
):
    values = data.model_dump()
    provided_values = data.model_dump(exclude_unset=True)
    raw_sheet_values = values.pop("sheet_values", {})
    provided_values.pop("sheet_values", None)
    try:
        detail_updates = validate_sheet_detail_updates(raw_sheet_values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "code": "FIELD_POLICY_VALIDATION_FAILED",
            "fields": [{"field_key": "sheet_values", "message": str(exc)}],
        }) from exc
    archive = None
    if values.get("archive_id"):
        archive = ensure_archive_access(db, values["archive_id"], scope_context)
        ensure_archive_enabled(archive, "建立项目进度")
        values["project_code"] = archive.project_code
        values["project_name"] = archive.project_name
        values["product_category"] = archive.product_category
    if db.query(PmsProject).filter(PmsProject.project_code == values["project_code"]).first():
        raise HTTPException(status_code=409, detail={
            "code": "PROJECT_ARCHIVE_ALREADY_LINKED",
            "field_key": "archive_id",
            "message": "该项目档案已经建立项目进度",
        })
    effective_product_category = archive.product_category if archive and archive.product_category else values.get("product_category")
    validate_enum_value(db, "project_status", values.get("status"))
    if archive and archive.product_category:
        values["product_category"] = archive.product_category
    else:
        validate_enum_value(db, "product_category", values.get("product_category"))
    _ensure_project_assignment_allowed(
        db,
        dept_id=values.get("dept_id"),
        pm_id=values.get("pm_id"),
        product_category=effective_product_category,
        scope_context=scope_context,
    )
    policy_initial_values = {
        **_project_updates_to_policy_values({
            key: value
            for key, value in values.items()
            if key not in provided_values
            if key not in {"archive_id", "project_code", "project_name", "product_category"}
        }),
    }
    policy_user_updates = {
        **_project_updates_to_policy_values({
            key: value
            for key, value in provided_values.items()
            if key not in {"archive_id", "project_code", "project_name", "product_category"}
        }),
        **detail_updates,
    }
    validate_business_field_write(
        db,
        MODULE_PROJECT_PROGRESS,
        current_values=policy_initial_values,
        updates=policy_user_updates,
        entity_created_at=None,
        is_create=True,
    )

    try:
        proj = PmsProject(**values)
        db.add(proj)
        db.flush()
        if detail_updates:
            db.add(PmsProjectSheetDetail(
                project_id=proj.id,
                detail_data=_dump_detail_data(detail_updates),
                created_by=operator_id,
                updated_by=operator_id,
            ))
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
            after_data={**serialize_model(proj), "sheet_values": detail_updates},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "PROJECT_ARCHIVE_ALREADY_LINKED",
            "field_key": "archive_id",
            "message": "该项目档案已经建立项目进度",
        }) from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(proj)
    return {"msg": "创建成功", "id": proj.id}


def update_project(
    db: Session,
    project_id: int,
    data: ProjectUpdate,
    user_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
):
    proj = ensure_project_access(db, project_id, scope_context)
    before = serialize_model(proj)
    update_data = data.model_dump(exclude_unset=True)
    if "product_category" in update_data:
        raise HTTPException(status_code=400, detail="产品类别来自项目档案，请在项目档案中维护")
    if "status" in update_data:
        validate_enum_value(db, "project_status", update_data["status"], current_value=proj.status)

    archive = (
        db.query(PmsProjectArchive).filter(PmsProjectArchive.id == proj.archive_id).first()
        if proj.archive_id else None
    )
    effective_product_category = archive.product_category if archive and archive.product_category else proj.product_category

    _ensure_project_assignment_allowed(
        db,
        dept_id=update_data.get("dept_id", proj.dept_id),
        pm_id=update_data.get("pm_id", proj.pm_id),
        product_category=effective_product_category,
        scope_context=scope_context,
    )

    detail = db.query(PmsProjectSheetDetail).filter(PmsProjectSheetDetail.project_id == project_id).first()
    validate_business_field_write(
        db,
        MODULE_PROJECT_PROGRESS,
        current_values=_project_policy_values(db, proj, detail),
        updates=_project_updates_to_policy_values(update_data),
        entity_created_at=proj.created_at,
        is_create=False,
    )

    for key, val in update_data.items():
        setattr(proj, key, val)

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


def delete_project(
    db: Session,
    project_id: int,
    operator_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
):
    proj = ensure_project_access(db, project_id, scope_context)
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
    ensure_project_access(db, project_id, scope_context)
    query = db.query(PmsTask).filter(PmsTask.project_id == project_id)
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


def create_task(
    db: Session,
    data: TaskCreate,
    operator_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
):
    ensure_project_access(db, data.project_id, scope_context)
    validate_enum_value(db, "task_status", data.status)
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


def update_task(
    db: Session,
    task_id: int,
    data: TaskUpdate,
    operator_id: int,
    request: Request | None = None,
    scope_context: dict | None = None,
    expected_project_id: int | None = None,
):
    task = db.query(PmsTask).filter(PmsTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if expected_project_id is not None and task.project_id != expected_project_id:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")
    ensure_project_access(db, task.project_id, scope_context)

    old_progress = task.progress
    before = serialize_model(task)

    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data:
        validate_enum_value(db, "task_status", update_data["status"], current_value=task.status)
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


def delete_task(
    db: Session,
    task_id: int,
    operator_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
    expected_project_id: int | None = None,
):
    task = db.query(PmsTask).filter(PmsTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if expected_project_id is not None and task.project_id != expected_project_id:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")
    ensure_project_access(db, task.project_id, scope_context)
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
ARCHIVE_UNIQUE_FIELDS = {
    "project_code": ("project_code_key", "项目编号", True),
    "project_name": ("project_name_key", "项目名称", False),
    "serial_no": ("serial_no_key", "序列号", True),
}


def _normalize_archive_values(values: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(values)
    for field_key in ("project_code", "project_name", "customer", "serial_no"):
        if field_key not in normalized:
            continue
        cleaned = str(normalized[field_key] or "").strip()
        if field_key in {"project_code", "project_name"} and not cleaned:
            label = "项目编号" if field_key == "project_code" else "项目名称"
            raise HTTPException(status_code=422, detail={
                "code": "ARCHIVE_FIELD_REQUIRED",
                "field_key": field_key,
                "message": f"{label}不能为空",
            })
        normalized[field_key] = cleaned or None
    return normalized


def _ensure_archive_unique_values(
    db: Session,
    values: dict[str, Any],
    *,
    exclude_archive_id: int | None = None,
) -> None:
    for field_key, (column_name, label, case_insensitive) in ARCHIVE_UNIQUE_FIELDS.items():
        if field_key not in values or values[field_key] in (None, ""):
            continue
        normalized = str(values[field_key]).casefold() if case_insensitive else str(values[field_key])
        query = db.query(PmsProjectArchive.id).filter(
            getattr(PmsProjectArchive, column_name) == normalized
        )
        if exclude_archive_id is not None:
            query = query.filter(PmsProjectArchive.id != exclude_archive_id)
        if query.first():
            raise HTTPException(status_code=409, detail={
                "code": "ARCHIVE_UNIQUE_CONFLICT",
                "field_key": field_key,
                "message": f"{label}已存在",
            })


def get_archive_list(db: Session, page: int = 1, page_size: int = 15,
                     keyword: str | None = None, status: int | None = None,
                     product_category: int | None = None,
                     allowed_category_ids: list[int] | None = None,
                     enabled: bool | None = None,
                     scope_context: dict | None = None):
    """查询项目档案列表"""
    query = _apply_archive_scope(db.query(PmsProjectArchive), db, scope_context)

    if keyword:
        query = query.filter(
            (PmsProjectArchive.project_code.contains(keyword)) |
            (PmsProjectArchive.project_name.contains(keyword))
        )
    if status is not None:
        query = query.filter(PmsProjectArchive.status == status)
    if product_category is not None:
        query = query.filter(PmsProjectArchive.product_category == product_category)
    if allowed_category_ids is not None:
        query = query.filter(PmsProjectArchive.product_category.in_(allowed_category_ids))
    if enabled is not None:
        query = query.filter(PmsProjectArchive.is_enabled == int(enabled))

    total = query.count()
    rows = query.order_by(PmsProjectArchive.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    guards = get_archive_delete_guards(db, [archive.id for archive in rows])

    items = []
    for a in rows:
        guard = guards[a.id]
        manager = db.query(SysUser).filter(SysUser.id == a.manager_id).first()
        creator = db.query(SysUser).filter(SysUser.id == a.created_by).first()
        editor = db.query(SysUser).filter(SysUser.id == a.updated_by).first()
        syncer = db.query(SysUser).filter(SysUser.id == a.erp_sync_by).first() if a.erp_sync_by else None
        items.append(ArchiveResponse(
            id=a.id, project_code=a.project_code, project_name=a.project_name,
            status=a.status, manager_id=a.manager_id, customer=a.customer,
            equipment_series=a.equipment_series, serial_no=a.serial_no,
            product_category=a.product_category,
            plan_start_date=a.plan_start_date, plan_end_date=a.plan_end_date,
            manager_name=manager.real_name if manager else "",
            created_by_name=creator.real_name if creator else "",
            updated_by_name=editor.real_name if editor else "",
            erp_synced=a.erp_synced, erp_sync_time=a.erp_sync_time,
            erp_sync_by_name=syncer.real_name if syncer else "",
            erp_sync_status=a.erp_sync_status, erp_error_msg=a.erp_error_msg,
            is_enabled=a.is_enabled,
            can_delete=guard["can_delete"],
            delete_blockers=guard["blockers"],
            created_at=a.created_at, updated_at=a.updated_at,
        ))
    return {"total": total, "items": items}


def get_archive_options(db: Session, scope_context: dict | None = None):
    """获取档案下拉选项（精简版，不分页）"""
    rows = _apply_archive_scope(db.query(PmsProjectArchive), db, scope_context).filter(
        PmsProjectArchive.is_enabled == 1
    ).order_by(
        PmsProjectArchive.project_code
    ).all()
    return [ArchiveOption(id=a.id, project_code=a.project_code, project_name=a.project_name) for a in rows]


def create_archive(
    db: Session,
    data: ArchiveCreate,
    user_id: int,
    request: Request | None = None,
    scope_context: dict | None = None,
):
    """创建项目档案"""
    values = _normalize_archive_values(data.model_dump())
    _ensure_archive_unique_values(db, values)
    validate_enum_value(db, "archive_status", values.get("status"))
    validate_enum_value(db, "product_category", values.get("product_category"))
    validate_enum_value(db, "equipment_series", values.get("equipment_series"))
    _ensure_archive_assignment_allowed(
        db,
        manager_id=values.get("manager_id"),
        product_category=values.get("product_category"),
        scope_context=scope_context,
    )
    validate_business_field_write(
        db,
        MODULE_PROJECT_ARCHIVE,
        current_values={},
        updates=values,
        entity_created_at=None,
        is_create=True,
    )
    try:
        archive = PmsProjectArchive(**values, created_by=user_id, updated_by=user_id)
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
    except IntegrityError as exc:
        db.rollback()
        _ensure_archive_unique_values(db, values)
        raise HTTPException(status_code=409, detail={
            "code": "ARCHIVE_UNIQUE_CONFLICT",
            "field_key": "project_code",
            "message": "项目编号已存在",
        }) from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(archive)
    return {"msg": "创建成功", "id": archive.id}


def update_archive(
    db: Session,
    archive_id: int,
    data: ArchiveUpdate,
    user_id: int,
    request: Request | None = None,
    scope_context: dict | None = None,
):
    """更新项目档案"""
    archive = ensure_archive_access(db, archive_id, scope_context)
    ensure_archive_enabled(archive, "编辑")
    before = serialize_model(archive)

    update_data = _normalize_archive_values(data.model_dump(exclude_unset=True))
    _ensure_archive_unique_values(db, update_data, exclude_archive_id=archive.id)
    if "status" in update_data:
        validate_enum_value(db, "archive_status", update_data["status"], current_value=archive.status)
    if "product_category" in update_data:
        validate_enum_value(
            db,
            "product_category",
            update_data["product_category"],
            current_value=archive.product_category,
        )
    if "equipment_series" in update_data:
        validate_enum_value(
            db,
            "equipment_series",
            update_data["equipment_series"],
            current_value=archive.equipment_series,
        )
    _ensure_archive_assignment_allowed(
        db,
        manager_id=update_data.get("manager_id", archive.manager_id),
        product_category=update_data.get("product_category", archive.product_category),
        scope_context=scope_context,
    )
    validate_business_field_write(
        db,
        MODULE_PROJECT_ARCHIVE,
        current_values={key: _jsonable(getattr(archive, key, None)) for key in {
            item["field_key"] for item in get_effective_field_policies(db, MODULE_PROJECT_ARCHIVE)["items"]
        }},
        updates=update_data,
        entity_created_at=archive.created_at,
        is_create=False,
    )
    try:
        for key, val in update_data.items():
            setattr(archive, key, val)
        archive.updated_by = user_id
        linked_project_updates = {
            source: update_data[source]
            for source in ("project_code", "project_name", "product_category")
            if source in update_data
        }
        if linked_project_updates:
            db.query(PmsProject).filter(PmsProject.archive_id == archive.id).update(
                linked_project_updates,
                synchronize_session=False,
            )
        db.flush()
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
    except IntegrityError as exc:
        db.rollback()
        _ensure_archive_unique_values(db, update_data, exclude_archive_id=archive_id)
        raise HTTPException(status_code=409, detail={
            "code": "ARCHIVE_UNIQUE_CONFLICT",
            "field_key": "project_code",
            "message": "项目编号已存在",
        }) from exc
    except Exception:
        db.rollback()
        raise
    return {"msg": "更新成功"}


def validate_archive_for_business_operation(db: Session, archive: PmsProjectArchive) -> None:
    """ERP 等后续业务操作前复用档案必填规则。"""
    policies = get_effective_field_policies(db, MODULE_PROJECT_ARCHIVE)["items"]
    current_values = {
        item["field_key"]: _jsonable(getattr(archive, item["field_key"], None))
        for item in policies
    }
    validate_business_field_write(
        db,
        MODULE_PROJECT_ARCHIVE,
        current_values=current_values,
        updates={},
        entity_created_at=archive.created_at,
        is_create=False,
    )


def delete_archive(
    db: Session,
    archive_id: int,
    operator_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
):
    """删除未被业务或 ERP 操作保护的项目档案。"""
    archive = _load_batch_archives(db, [archive_id], scope_context)[0]
    before = serialize_model(archive)
    guard = get_archive_delete_guard(db, archive_id)
    if not guard["can_delete"]:
        message = format_archive_delete_blockers(guard["blockers"])
        record_operation_log(
            db,
            module="项目档案",
            action="delete",
            entity_type="pms_project_archive",
            entity_id=archive_id,
            entity_name=archive.project_name,
            operator_id=operator_id,
            request=request,
            status="failed",
            summary=f"删除项目档案失败：{archive.project_name}",
            before_data=before,
            after_data={"blockers": guard["blockers"]},
            error_msg=message,
            commit=True,
        )
        raise HTTPException(status_code=409, detail={
            "code": "ARCHIVE_DELETE_BLOCKED",
            "message": message,
            "blockers": guard["blockers"],
            "suggested_action": "disable",
        })

    try:
        deleted = (
            db.query(PmsProjectArchive)
            .filter(
                PmsProjectArchive.id == archive_id,
                or_(
                    PmsProjectArchive.erp_synced.is_(None),
                    PmsProjectArchive.erp_synced != 1,
                ),
                archive_not_pending_condition(),
            )
            .delete(synchronize_session=False)
        )
        if deleted != 1:
            db.rollback()
            current = _load_batch_archives(db, [archive_id], scope_context)[0]
            current_guard = get_archive_delete_guard(db, current.id)
            if current_guard["can_delete"]:
                raise HTTPException(status_code=409, detail={
                    "code": "ARCHIVE_LIFECYCLE_CONFLICT",
                    "message": "项目档案状态已变化，请刷新后重试",
                })
            message = format_archive_delete_blockers(current_guard["blockers"])
            record_operation_log(
                db,
                module="项目档案",
                action="delete",
                entity_type="pms_project_archive",
                entity_id=current.id,
                entity_name=current.project_name,
                operator_id=operator_id,
                request=request,
                status="failed",
                summary=f"删除项目档案失败：{current.project_name}",
                before_data=serialize_model(current),
                after_data={"blockers": current_guard["blockers"]},
                error_msg=message,
                commit=True,
            )
            raise HTTPException(status_code=409, detail={
                "code": "ARCHIVE_DELETE_BLOCKED",
                "message": message,
                "blockers": current_guard["blockers"],
                "suggested_action": "disable",
            })

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
        db.expunge(archive)
        db.commit()
    except Exception:
        if db.in_transaction():
            db.rollback()
        raise
    return {"msg": "删除成功"}


def format_archive_delete_blockers(blockers: list[dict[str, Any]]) -> str:
    """将删除保护项转换为可直接反馈给用户的原因。"""
    details = "；".join(
        f"{item['label']}（{item['count']}）" for item in blockers
    )
    return f"项目档案无法删除：{details}"


def _load_batch_archives(
    db: Session,
    archive_ids: list[int],
    scope_context: dict | None = None,
) -> list[PmsProjectArchive]:
    """按固定 ID 顺序锁定目标档案，并应用现有范围限制。"""
    unique_ids = sorted(set(archive_ids))
    scoped_query = _apply_archive_scope(
        db.query(PmsProjectArchive), db, scope_context
    )
    archives = apply_archive_lifecycle_lock(scoped_query, unique_ids).all()
    archive_by_id = {archive.id: archive for archive in archives}
    if len(archive_by_id) != len(unique_ids):
        db.rollback()
        raise HTTPException(status_code=404, detail="档案不存在或无权访问")
    return [archive_by_id[archive_id] for archive_id in unique_ids]


def batch_delete_archives(
    db: Session,
    archive_ids: list[int],
    operator_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
) -> dict:
    """原子删除多个项目档案，存在任一保护项时不删除任何记录。"""
    archives = _load_batch_archives(db, archive_ids, scope_context)
    guards = get_archive_delete_guards(db, [archive.id for archive in archives])
    blocked_archives = [
        {
            "archive_id": archive.id,
            "project_code": archive.project_code,
            "project_name": archive.project_name,
            "blockers": guards[archive.id]["blockers"],
        }
        for archive in archives
        if not guards[archive.id]["can_delete"]
    ]
    if blocked_archives:
        message = "；".join(
            f"{item['project_name']}：{format_archive_delete_blockers(item['blockers'])}"
            for item in blocked_archives
        )
        record_operation_log(
            db,
            module="项目档案",
            action="batch_delete",
            entity_type="pms_project_archive",
            entity_id=",".join(str(archive.id) for archive in archives),
            entity_name="项目档案批量删除",
            operator_id=operator_id,
            request=request,
            status="failed",
            summary="批量删除项目档案失败",
            after_data={
                "archive_ids": [archive.id for archive in archives],
                "blockers": blocked_archives,
            },
            error_msg=message,
            commit=True,
        )
        raise HTTPException(status_code=409, detail={
            "code": "ARCHIVE_DELETE_BLOCKED",
            "message": message,
            "blockers": blocked_archives,
            "suggested_action": "disable",
        })

    archive_id_set = [archive.id for archive in archives]
    before_by_id = {archive.id: serialize_model(archive) for archive in archives}
    try:
        deleted = (
            db.query(PmsProjectArchive)
            .filter(
                PmsProjectArchive.id.in_(archive_id_set),
                or_(
                    PmsProjectArchive.erp_synced.is_(None),
                    PmsProjectArchive.erp_synced != 1,
                ),
                archive_not_pending_condition(),
            )
            .delete(synchronize_session=False)
        )
        if deleted != len(archives):
            db.rollback()
            current_archives = _load_batch_archives(db, archive_id_set, scope_context)
            current_guards = get_archive_delete_guards(
                db, [archive.id for archive in current_archives]
            )
            current_blocked = [
                {
                    "archive_id": archive.id,
                    "project_code": archive.project_code,
                    "project_name": archive.project_name,
                    "blockers": current_guards[archive.id]["blockers"],
                }
                for archive in current_archives
                if not current_guards[archive.id]["can_delete"]
            ]
            if current_blocked:
                message = "；".join(
                    f"{item['project_name']}：{format_archive_delete_blockers(item['blockers'])}"
                    for item in current_blocked
                )
                record_operation_log(
                    db,
                    module="项目档案",
                    action="batch_delete",
                    entity_type="pms_project_archive",
                    entity_id=",".join(str(item_id) for item_id in archive_id_set),
                    entity_name="项目档案批量删除",
                    operator_id=operator_id,
                    request=request,
                    status="failed",
                    summary="批量删除项目档案失败",
                    after_data={"archive_ids": archive_id_set, "blockers": current_blocked},
                    error_msg=message,
                    commit=True,
                )
                raise HTTPException(status_code=409, detail={
                    "code": "ARCHIVE_DELETE_BLOCKED",
                    "message": message,
                    "blockers": current_blocked,
                    "suggested_action": "disable",
                })
            raise HTTPException(status_code=409, detail={
                "code": "ARCHIVE_LIFECYCLE_CONFLICT",
                "message": "项目档案状态已变化，请刷新后重试",
            })

        for archive in archives:
            record_operation_log(
                db,
                module="项目档案",
                action="delete",
                entity_type="pms_project_archive",
                entity_id=archive.id,
                entity_name=archive.project_name,
                operator_id=operator_id,
                request=request,
                summary=f"批量删除项目档案：{archive.project_name}",
                before_data=before_by_id[archive.id],
            )
            db.expunge(archive)
        db.commit()
    except Exception:
        if db.in_transaction():
            db.rollback()
        raise
    return {"msg": "批量删除成功", "count": len(archives)}


def change_archive_enabled(
    db: Session,
    archive_id: int,
    enabled: bool,
    operator_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
) -> dict:
    """在数据范围校验后，启用或禁用单个项目档案。"""
    archive = _load_batch_archives(db, [archive_id], scope_context)[0]
    return set_archive_enabled(db, archive, enabled, operator_id, request)


def batch_change_archives_enabled(
    db: Session,
    archive_ids: list[int],
    enabled: bool,
    operator_id: int | None = None,
    request: Request | None = None,
    scope_context: dict | None = None,
) -> dict:
    """原子启用或禁用多个项目档案，成功时仅提交一次。"""
    archives = _load_batch_archives(db, archive_ids, scope_context)
    target_enabled = int(enabled)
    changes = [archive for archive in archives if archive.is_enabled != target_enabled]
    if not enabled and any(archive.erp_sync_status == "pending" for archive in changes):
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "ARCHIVE_OPERATION_PENDING",
            "message": "项目档案正在同步，无法禁用，请等待同步完成",
        })
    if not changes:
        db.rollback()
        return {"msg": "批量启用成功" if enabled else "批量禁用成功", "count": 0}

    action = "enable" if enabled else "disable"
    action_label = "启用" if enabled else "禁用"
    change_ids = [archive.id for archive in changes]
    before_by_id = {archive.id: serialize_model(archive) for archive in changes}
    mutation = db.query(PmsProjectArchive).filter(
        PmsProjectArchive.id.in_(change_ids),
        PmsProjectArchive.is_enabled != target_enabled,
    )
    if not enabled:
        mutation = mutation.filter(archive_not_pending_condition())

    try:
        changed_count = mutation.update(
            {PmsProjectArchive.is_enabled: target_enabled},
            synchronize_session=False,
        )
        if changed_count != len(changes):
            db.rollback()
            current_archives = _load_batch_archives(db, change_ids, scope_context)
            if not enabled and any(
                archive.erp_sync_status == "pending" for archive in current_archives
            ):
                raise HTTPException(status_code=409, detail={
                    "code": "ARCHIVE_OPERATION_PENDING",
                    "message": "项目档案正在同步，无法禁用，请等待同步完成",
                })
            raise HTTPException(status_code=409, detail={
                "code": "ARCHIVE_LIFECYCLE_CONFLICT",
                "message": "项目档案状态已变化，请刷新后重试",
            })

        for archive in changes:
            after = dict(before_by_id[archive.id])
            after["is_enabled"] = target_enabled
            record_operation_log(
                db,
                module="项目档案",
                action=action,
                entity_type="pms_project_archive",
                entity_id=archive.id,
                entity_name=archive.project_name,
                operator_id=operator_id,
                request=request,
                summary=f"批量{action_label}项目档案：{archive.project_name}",
                before_data=before_by_id[archive.id],
                after_data=after,
            )
        db.commit()
    except Exception:
        if db.in_transaction():
            db.rollback()
        raise
    return {"msg": f"批量{action_label}成功", "count": len(changes)}
