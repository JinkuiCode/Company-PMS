"""项目进度动态列表字段契约测试。"""
import json
import os
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = "data/pms-test-project-sheet-list.db"

DB_PATH = ROOT / os.environ["SQLITE_DB_PATH"]
if DB_PATH.exists():
    DB_PATH.unlink()


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def seed_project_sheet_list_runtime_data() -> int:
    from app.core.database import SessionLocal
    from app.models.init_db import init_db
    from app.models.project import PmsProject, PmsProjectArchive, PmsProjectSheetDetail, PmsTask
    from app.models.rbac import SysDept
    from app.models.user import SysUser

    init_db()
    db = SessionLocal()
    try:
        dept = SysDept(parent_id=0, dept_name="项目部", sort=1, status=1)
        pm = SysUser(
            username="sheet-list-pm",
            real_name="项目经理甲",
            password_hash="hash",
            dept_id=None,
            status=1,
        )
        db.add_all([dept, pm])
        db.flush()

        pm.dept_id = dept.id

        archive = PmsProjectArchive(
            project_code="PA-001",
            project_name="档案项目A",
            status=1,
            manager_id=pm.id,
            product_type="链式",
            product_line="Bench",
        )
        db.add(archive)
        db.flush()

        project = PmsProject(
            archive_id=archive.id,
            project_code="PR-001",
            project_name="进度项目A",
            dept_id=dept.id,
            pm_id=pm.id,
            product_line="Single",
            status=1,
            start_date=date(2026, 1, 5),
            end_date=date(2026, 3, 10),
            design_progress=35,
            order_progress=55,
        )
        db.add(project)
        db.flush()

        detail = PmsProjectSheetDetail(
            project_id=project.id,
            detail_data=json.dumps(
                {
                    "customer": "客户甲",
                    "plan_ship_date": "2026-02-01",
                    "actual_ship_date": "2026-02-06",
                    "progress_notes": "长文本说明",
                    "configuration": "A1",
                },
                ensure_ascii=False,
            ),
            updated_by=pm.id,
        )
        task = PmsTask(
            project_id=project.id,
            task_name="任务A",
            progress=80,
            status=2,
            parent_id=0,
            sort=1,
        )
        db.add_all([detail, task])
        db.commit()
        return project.id
    finally:
        db.close()


def test_project_sheet_list_contract_files_and_route_order():
    schema = read("app/schemas/project.py")
    api = read("app/api/projects.py")
    service = read("app/services/project.py")
    fields_service = read("app/services/project_sheet_fields.py")

    assert '@router.get("/sheet-fields"' in api
    assert api.index('@router.get("/sheet-fields"') < api.index('@router.put("/{project_id}"')
    assert api.index('@router.get("/sheet-fields"') < api.index('@router.get("/{project_id}/sheet-detail"')
    assert "sheet_field_keys" in api
    assert "sheet_fields" in schema
    assert "normalize_sheet_field_keys" in fields_service
    assert "get_project_sheet_field_metadata" in fields_service
    assert "list_available" in fields_service
    assert "quick_addable" in fields_service
    assert "sheet_fields" in service


def test_project_sheet_metadata_flags_and_no_values():
    from app.services.project_sheet_fields import FIELD_BY_KEY, get_project_sheet_field_metadata

    assert FIELD_BY_KEY["customer"]["list_available"] is True
    assert FIELD_BY_KEY["customer"]["quick_addable"] is True
    assert FIELD_BY_KEY["progress_notes"]["list_available"] is True
    assert FIELD_BY_KEY["progress_notes"]["quick_addable"] is False
    assert FIELD_BY_KEY["difference_days"]["list_available"] is True
    assert FIELD_BY_KEY["difference_days"]["quick_addable"] is True
    assert FIELD_BY_KEY["last_editor"]["list_available"] is False
    assert FIELD_BY_KEY["last_editor"]["quick_addable"] is False

    metadata = get_project_sheet_field_metadata()
    assert set(metadata.keys()) == {"groups", "fields"}
    assert metadata["fields"]
    assert all("value" not in field for field in metadata["fields"])
    assert all("value" not in field for group in metadata["groups"] for field in group["fields"])


def test_normalize_sheet_field_keys_deduplicates_and_ignores_unknown_or_hidden():
    from app.services.project_sheet_fields import normalize_sheet_field_keys

    normalized = normalize_sheet_field_keys(
        "customer,customer,last_editor,unknown,progress_notes,product_line"
    )
    assert normalized == ["customer", "progress_notes", "product_line"]


def test_project_sheet_fields_metadata_endpoint_returns_groups_without_values():
    from fastapi.testclient import TestClient

    from app.api.auth import get_current_user_context
    from main import app

    app.dependency_overrides[get_current_user_context] = lambda: {
        "user_id": 1,
        "dept_id": None,
        "data_scope": 4,
        "product_lines": None,
    }
    try:
        with TestClient(app) as client:
            response = client.get("/api/projects/sheet-fields")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "groups" in payload
    assert "fields" in payload
    assert all("value" not in field for field in payload["fields"])


def test_project_sheet_ratio_fields_compute_from_immediate_dependencies():
    from app.services.project_sheet_fields import compute_sheet_field_value

    values = {
        "design_start_date": "2026-01-01",
        "actual_bom_release_date": "2026-01-11",
        "actual_drawing_done_date": "2026-01-16",
        "actual_purchase_request_done_date": "2026-01-21",
        "actual_order_done_date": "2026-01-25",
        "actual_frame_arrive_date": "2026-02-04",
        "actual_power_on_date": "2026-02-09",
        "actual_test_done_date": "2026-02-14",
        "delivery_cycle": 40,
    }

    assert compute_sheet_field_value("rd_duration_ratio", values) == 25.0
    assert compute_sheet_field_value("purchase_duration_ratio", values) == 12.5
    assert compute_sheet_field_value("assembly_duration_ratio", values) == 12.5
    assert compute_sheet_field_value("test_duration_ratio", values) == 12.5


def test_project_list_sheet_fields_projection_and_backwards_compatibility():
    project_id = seed_project_sheet_list_runtime_data()

    from app.core.database import SessionLocal
    from app.services.project import get_project_list

    db = SessionLocal()
    try:
        scoped = {
            "user_id": 1,
            "dept_id": None,
            "data_scope": 4,
            "product_lines": None,
        }
        result = get_project_list(
            db,
            page=1,
            page_size=20,
            scope_context=scoped,
            sheet_field_keys="customer,product_line,difference_days,design_progress,project_code,last_editor,unknown",
        )
        items_by_id = {item.id: item for item in result["items"]}
        item = items_by_id[project_id]

        assert item.sheet_fields == {
            "customer": "客户甲",
            "product_line": "Bench",
            "difference_days": 5,
            "design_progress": 35,
            "project_code": "PA-001",
        }

        legacy = get_project_list(db, page=1, page_size=20, scope_context=scoped)
        legacy_item = {item.id: item for item in legacy["items"]}[project_id]
        assert legacy_item.sheet_fields == {}
    finally:
        db.close()


if __name__ == "__main__":
    test_project_sheet_list_contract_files_and_route_order()
    test_project_sheet_metadata_flags_and_no_values()
    test_normalize_sheet_field_keys_deduplicates_and_ignores_unknown_or_hidden()
    test_project_sheet_fields_metadata_endpoint_returns_groups_without_values()
    test_project_sheet_ratio_fields_compute_from_immediate_dependencies()
    test_project_list_sheet_fields_projection_and_backwards_compatibility()
    print("project sheet list contract passed")
