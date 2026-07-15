"""只读字段目录。

目录由 SQLAlchemy 模型、Pydantic 输入/输出 Schema 与项目总表注册表合并生成，
用于解释系统字段，不参与在线修改数据库结构。
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, get_args, get_origin

from app.core.database import Base
from app.models.dict import SysDict, SysDictItem  # noqa: F401 - register catalog models
from app.models.operation_log import SysOperationLog
from app.models.project import PmsProject, PmsProjectArchive, PmsTask
from app.models.rbac import SysDept, SysRole
from app.models.user import SysUser
from app.schemas.operation_log import OperationLogResponse
from app.schemas.project import (
    ArchiveCreate,
    ArchiveResponse,
    ArchiveUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.schemas.rbac import (
    DeptCreate,
    DeptResponse,
    DeptUpdate,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.project_sheet_fields import (
    GROUP_BY_KEY,
    PROJECT_SHEET_FIELDS,
)


MODULE_CONFIGS = (
    {
        "key": "user",
        "label": "用户管理",
        "group": "用户字段",
        "model": SysUser,
        "schemas": (UserCreate, UserUpdate, UserResponse),
        "editable_schemas": (UserCreate, UserUpdate),
    },
    {
        "key": "department",
        "label": "部门管理",
        "group": "部门字段",
        "model": SysDept,
        "schemas": (DeptCreate, DeptUpdate, DeptResponse),
        "editable_schemas": (DeptCreate, DeptUpdate),
    },
    {
        "key": "role",
        "label": "角色管理",
        "group": "角色字段",
        "model": SysRole,
        "schemas": (RoleCreate, RoleUpdate, RoleResponse),
        "editable_schemas": (RoleCreate, RoleUpdate),
    },
    {
        "key": "project_archive",
        "label": "项目档案",
        "group": "档案字段",
        "model": PmsProjectArchive,
        "schemas": (ArchiveCreate, ArchiveUpdate, ArchiveResponse),
        "editable_schemas": (ArchiveCreate, ArchiveUpdate),
    },
    {
        "key": "project_progress",
        "label": "项目进度",
        "group": "项目字段",
        "model": PmsProject,
        "schemas": (ProjectCreate, ProjectUpdate, ProjectResponse),
        "editable_schemas": (ProjectCreate, ProjectUpdate),
    },
    {
        "key": "task",
        "label": "任务进度",
        "group": "任务字段",
        "model": PmsTask,
        "schemas": (TaskCreate, TaskUpdate, TaskResponse),
        "editable_schemas": (TaskCreate, TaskUpdate),
    },
    {
        "key": "operation_log",
        "label": "操作日志",
        "group": "审计字段",
        "model": SysOperationLog,
        "schemas": (OperationLogResponse,),
        "editable_schemas": (),
    },
)


AUTO_MODEL_MODULES: dict[str, tuple[str, str, str]] = {
    "sys_remember_token": ("authentication", "登录认证", "会话令牌字段"),
    "sys_menu": ("permission_menu", "菜单权限", "菜单与权限字段"),
    "sys_user_role": ("user_role_relation", "用户角色关系", "关联字段"),
    "sys_role_menu": ("role_permission_relation", "角色权限关系", "关联字段"),
    "erp_sync_log": ("erp_sync_log", "ERP 同步日志", "同步日志字段"),
    "pms_project_sheet_detail": ("project_sheet_storage", "项目总表存储", "扩展存储字段"),
    "pms_progress_log": ("progress_history", "进度变更日志", "变更记录字段"),
    "sys_dict": ("enum_definition", "枚举定义", "枚举注册字段"),
    "sys_dict_item": ("enum_item", "枚举值", "枚举值字段"),
}


def _catalog_module_configs() -> list[dict[str, Any]]:
    """Return configured business modules plus every remaining mapped table."""
    configs = [dict(config) for config in MODULE_CONFIGS]
    configured_models = {config["model"] for config in configs}
    fallback_models = sorted(
        {
            mapper.class_
            for mapper in Base.registry.mappers
            if hasattr(mapper.class_, "__table__") and mapper.class_ not in configured_models
        },
        key=lambda model: model.__tablename__,
    )
    for model in fallback_models:
        table_name = model.__tablename__
        module_key, module_label, group = AUTO_MODEL_MODULES.get(
            table_name,
            (table_name, table_name, "模型字段"),
        )
        configs.append({
            "key": module_key,
            "label": module_label,
            "group": group,
            "model": model,
            "schemas": (),
            "editable_schemas": (),
        })
    return configs


FIELD_LABELS = {
    "id": "ID",
    "role_ids": "角色",
    "role_names": "角色名称",
    "password": "密码",
    "manager_name": "负责人",
    "created_by_name": "创建人",
    "updated_by_name": "最后编辑人",
    "erp_sync_by_name": "最后同步人",
    "dept_name": "部门名称",
    "pm_name": "项目经理",
    "assignee_name": "负责人",
    "task_count": "任务数",
    "total_progress": "总进度",
    "sheet_fields": "项目总表扩展字段",
    "children": "子级",
}


ENUM_BINDINGS: dict[tuple[str, str], tuple[str | None, str]] = {
    ("user", "status"): (None, "system_fixed"),
    ("department", "status"): (None, "system_fixed"),
    ("role", "status"): (None, "system_fixed"),
    ("role", "data_scope"): (None, "system_fixed"),
    ("role", "product_category_ids"): ("product_category", "enum"),
    ("project_archive", "status"): ("archive_status", "enum"),
    ("project_archive", "product_category"): ("product_category", "enum"),
    ("project_archive", "equipment_series"): ("equipment_series", "enum"),
    ("project_archive", "erp_sync_status"): (None, "system_fixed"),
    ("project_progress", "status"): ("project_status", "enum"),
    ("project_progress", "node_status"): ("project_status", "enum"),
    ("project_progress", "product_category"): ("product_category", "enum"),
    ("task", "status"): ("task_status", "enum"),
}


def _schema_fields(schemas: Iterable[type]) -> set[str]:
    fields: set[str] = set()
    for schema in schemas:
        fields.update(schema.model_fields)
    return fields


def _annotation_type(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is not None:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if origin is list:
            return "list"
        if origin is dict:
            return "json"
        if len(args) == 1:
            return _annotation_type(args[0])
    name = getattr(annotation, "__name__", str(annotation)).lower()
    if "datetime" in name:
        return "datetime"
    if name == "date" or "date" in name:
        return "date"
    if name in {"int", "integer"}:
        return "integer"
    if name in {"float", "decimal"}:
        return "number"
    if name in {"bool", "boolean"}:
        return "boolean"
    if name in {"dict", "mapping"}:
        return "json"
    if name == "list":
        return "list"
    return "text"


def _column_type(column: Any) -> str:
    try:
        return _annotation_type(column.type.python_type)
    except (AttributeError, NotImplementedError):
        return column.type.__class__.__name__.lower()


def _label_from_comment(code: str, comment: str | None) -> str:
    if code in FIELD_LABELS:
        return FIELD_LABELS[code]
    if comment:
        for separator in (":", "："):
            if separator in comment:
                return comment.split(separator, 1)[0].strip()
        return comment.strip()
    return code


def _base_catalog_for_module(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    model = config["model"]
    schema_fields = _schema_fields(config["schemas"])
    editable_fields = _schema_fields(config["editable_schemas"])
    model_columns = {column.name: column for column in model.__table__.columns}
    field_codes = list(model_columns)
    field_codes.extend(sorted(schema_fields - set(model_columns)))

    result: dict[str, dict[str, Any]] = {}
    for code in field_codes:
        column = model_columns.get(code)
        annotation = None
        for schema in config["schemas"]:
            schema_field = schema.model_fields.get(code)
            if schema_field:
                annotation = schema_field.annotation
                break
        comment = column.comment if column is not None else None
        enum_code, source_type = ENUM_BINDINGS.get(
            (config["key"], code),
            (None, "database" if column is not None else "relation"),
        )
        sources = []
        if column is not None:
            sources.append("SQLAlchemy")
        if code in schema_fields:
            sources.append("Pydantic")
        result[code] = {
            "module": config["key"],
            "module_name": config["label"],
            "group": config["group"],
            "field_name": _label_from_comment(code, comment),
            "field_code": code,
            "value_type": _column_type(column) if column is not None else _annotation_type(annotation),
            "source_type": source_type,
            "storage_table": model.__tablename__ if column is not None else None,
            "storage_column": code if column is not None else None,
            "editable": code in editable_fields and code not in {"id", "created_at", "updated_at"},
            "computed": False,
            "enum_code": enum_code,
            "description": comment or ("接口关联/展示字段" if column is None else ""),
            "catalog_source": "+".join(sources),
        }
    return result


def build_field_catalog() -> list[dict[str, Any]]:
    """合并模型、Schema 与项目总表注册表，返回稳定排序的字段目录。"""
    catalog: list[dict[str, Any]] = []
    for module_sort, config in enumerate(_catalog_module_configs(), 1):
        fields = _base_catalog_for_module(config)
        if config["model"] is PmsProject:
            model_columns = {column.name for column in PmsProject.__table__.columns}
            for sheet_field in PROJECT_SHEET_FIELDS:
                key = sheet_field["key"]
                enum_code, _ = ENUM_BINDINGS.get(
                    ("project_progress", key),
                    (sheet_field.get("enum_code"), sheet_field["source_type"]),
                )
                storage_table = None
                storage_column = None
                if key in model_columns:
                    storage_table = PmsProject.__tablename__
                    storage_column = key
                elif sheet_field["source_type"] == "detail":
                    storage_table = "pms_project_sheet_detail"
                    storage_column = f"detail_data.{key}"
                elif sheet_field["source_type"] == "archive":
                    storage_table = PmsProjectArchive.__tablename__
                    storage_column = key
                fields[key] = {
                    "module": "project_progress",
                    "module_name": config["label"],
                    "group": GROUP_BY_KEY[sheet_field["group"]]["label"],
                    "field_name": sheet_field["label"],
                    "field_code": key,
                    "value_type": sheet_field["value_type"],
                    "source_type": sheet_field["source_type"],
                    "storage_table": storage_table,
                    "storage_column": storage_column,
                    "editable": sheet_field["editable"],
                    "computed": sheet_field["computed"],
                    "enum_code": enum_code,
                    "description": _sheet_field_description(sheet_field),
                    "catalog_source": "PROJECT_SHEET_FIELDS",
                    "_sheet_sort": sheet_field["sort"],
                }

        for field_sort, field in enumerate(fields.values(), 1):
            field["sort"] = (
                module_sort * 10_000
                + field.get("_sheet_sort", field_sort)
            )
            field.pop("_sheet_sort", None)
            catalog.append(field)
    return sorted(catalog, key=lambda item: (item["sort"], item["field_code"]))


def _sheet_field_description(field: dict[str, Any]) -> str:
    if field["computed"]:
        return "系统自动计算，不允许人工维护"
    if field["source_type"] in {"archive", "system"}:
        return "引用来源字段，请在来源模块维护"
    if field["source_type"] == "project":
        return "项目进度主字段"
    return "项目总表人工维护字段"


def query_field_catalog(
    fields: list[dict[str, Any]] | None = None,
    *,
    keyword: str | None = None,
    module: str | None = None,
    value_type: str | None = None,
    source_type: str | None = None,
    enum_only: bool = False,
    page: int = 1,
    page_size: int = 30,
) -> dict[str, Any]:
    """按页面查询条件过滤字段目录。"""
    source_fields = list(fields if fields is not None else build_field_catalog())
    filtered = list(source_fields)
    if keyword:
        needle = keyword.strip().lower()
        filtered = [
            item
            for item in filtered
            if needle in item["field_name"].lower()
            or needle in item["field_code"].lower()
            or needle in item["description"].lower()
        ]
    if module:
        filtered = [item for item in filtered if item["module"] == module]
    if value_type:
        filtered = [item for item in filtered if item["value_type"] == value_type]
    if source_type:
        filtered = [item for item in filtered if item["source_type"] == source_type]
    if enum_only:
        filtered = [item for item in filtered if item["enum_code"]]

    page = max(page, 1)
    page_size = max(1, min(page_size, 200))
    total = len(filtered)
    start = (page - 1) * page_size
    module_counts: dict[str, int] = {}
    module_names: dict[str, str] = {}
    for item in source_fields:
        module_counts[item["module"]] = module_counts.get(item["module"], 0) + 1
        module_names.setdefault(item["module"], item["module_name"])
    return {
        "items": filtered[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "modules": [
            {"value": key, "label": module_names[key], "count": count}
            for key, count in module_counts.items()
        ],
    }
