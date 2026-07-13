"""数据字典字段目录契约测试。"""
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DB_DIALECT", "sqlite")
os.environ.setdefault("SQLITE_DB_PATH", str(ROOT / "data" / "pms-test-field-catalog.db"))


def test_catalog_covers_models_schemas_and_project_sheet_registry():
    from app.core.database import Base
    from app.services.field_catalog import build_field_catalog

    fields = build_field_catalog()
    modules = {field["module"] for field in fields}
    assert {
        "user",
        "department",
        "role",
        "project_archive",
        "project_progress",
        "task",
        "operation_log",
    }.issubset(modules)

    sheet_fields = [
        field
        for field in fields
        if field["module"] == "project_progress"
        and field["catalog_source"] == "PROJECT_SHEET_FIELDS"
    ]
    assert len(sheet_fields) == 126
    assert len({field["field_code"] for field in sheet_fields}) == 126

    field_keys = {(field["module"], field["field_code"]) for field in fields}
    for expected in [
        ("user", "username"),
        ("user", "role_ids"),
        ("department", "parent_id"),
        ("role", "data_scope"),
        ("project_archive", "erp_sync_status"),
        ("project_progress", "frame_progress"),
        ("task", "progress"),
        ("operation_log", "diff_data"),
    ]:
        assert expected in field_keys

    catalog_tables = {
        field["storage_table"]
        for field in fields
        if field["storage_table"] and "SQLAlchemy" in field["catalog_source"]
    }
    assert set(Base.metadata.tables).issubset(catalog_tables)

    storage_fields = {
        (field["storage_table"], field["storage_column"])
        for field in fields
    }
    for expected in [
        ("erp_sync_log", "error_msg"),
        ("pms_progress_log", "old_progress"),
        ("sys_menu", "permission_code"),
        ("sys_dict", "dict_code"),
        ("sys_dict_item", "item_label"),
        ("sys_remember_token", "token_hash"),
    ]:
        assert expected in storage_fields


def test_catalog_exposes_enum_metadata_and_supports_filters():
    from app.services.field_catalog import build_field_catalog, query_field_catalog
    from app.services.project_sheet_fields import FIELD_BY_KEY

    fields = build_field_catalog()
    by_key = {(field["module"], field["field_code"]): field for field in fields}
    assert by_key[("project_archive", "status")]["enum_code"] == "archive_status"
    assert by_key[("project_archive", "product_line")]["enum_code"] == "product_line"
    assert by_key[("project_progress", "node_status")]["enum_code"] == "project_status"
    assert by_key[("project_progress", "node_status")]["source_type"] == "project"
    assert by_key[("project_progress", "product_line")]["source_type"] == "archive"
    assert by_key[("task", "status")]["enum_code"] == "task_status"
    assert by_key[("role", "data_scope")]["source_type"] == "system_fixed"
    assert FIELD_BY_KEY["node_status"]["enum_code"] == "project_status"

    result = query_field_catalog(
        fields,
        keyword="项目号",
        module="project_progress",
        enum_only=False,
        page=1,
        page_size=20,
    )
    assert result["total"] >= 1
    assert all(item["module"] == "project_progress" for item in result["items"])
    assert any(item["field_code"] == "project_code" for item in result["items"])

    enum_result = query_field_catalog(fields, enum_only=True, page=1, page_size=200)
    assert enum_result["total"] >= 5
    assert all(item["enum_code"] for item in enum_result["items"])


def test_field_catalog_api_and_permission_contract():
    api = (ROOT / "app/api/field_catalog.py").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'prefix="/api/field-catalog"' in api
    assert 'require_permission("system:dict:view")' in api
    assert "field_catalog.router" in main


if __name__ == "__main__":
    test_catalog_covers_models_schemas_and_project_sheet_registry()
    test_catalog_exposes_enum_metadata_and_supports_filters()
    test_field_catalog_api_and_permission_contract()
    print("field catalog contract passed")
