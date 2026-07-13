"""项目总表字段接入契约测试。"""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_project_sheet_registry_covers_all_excel_fields():
    from app.services.project_sheet_fields import PROJECT_SHEET_FIELDS, PROJECT_SHEET_GROUPS

    assert len(PROJECT_SHEET_FIELDS) == 126
    assert len({field["key"] for field in PROJECT_SHEET_FIELDS}) == 126
    assert len({field["label"] for field in PROJECT_SHEET_FIELDS}) == 126

    group_labels = [group["label"] for group in PROJECT_SHEET_GROUPS]
    for label in [
        "基础信息",
        "计划节点",
        "实际节点",
        "阶段进度",
        "产品配置",
        "交付验收",
        "人员分工",
        "问题统计",
        "工期分析",
        "系统信息",
        "推进记录",
    ]:
        assert label in group_labels

    labels = [field["label"] for field in PROJECT_SHEET_FIELDS]
    for label in ["项目号", "项目名称", "产品类", "推进记录", "设计进度", "配置", "工艺工期"]:
        assert label in labels


def test_project_sheet_reference_and_computed_fields_are_readonly():
    from app.services.project_sheet_fields import FIELD_BY_KEY

    for key in ["project_code", "project_name", "product_line"]:
        field = FIELD_BY_KEY[key]
        assert field["source_type"] in {"archive", "project"}
        assert field["editable"] is False
        assert field["computed"] is False

    for key in [
        "planned_ship_year",
        "actual_ship_year",
        "planned_ship_month",
        "planned_ship_year_month",
        "actual_ship_year_month",
        "actual_ship_month",
        "warranty_end_date",
        "difference_days",
        "rd_duration_ratio",
        "process_duration_days",
    ]:
        field = FIELD_BY_KEY[key]
        assert field["source_type"] == "computed"
        assert field["editable"] is False
        assert field["computed"] is True

    assert FIELD_BY_KEY["configuration"]["editable"] is True
    assert FIELD_BY_KEY["progress_notes"]["editable"] is True


def test_project_sheet_backend_contract_files_and_routes():
    model = read("app/models/project.py")
    schema = read("app/schemas/project.py")
    service = read("app/services/project.py")
    api = read("app/api/projects.py")
    init_db = read("app/models/init_db.py")

    assert "class PmsProjectSheetDetail" in model
    assert '__tablename__ = "pms_project_sheet_detail"' in model
    assert "detail_data" in model
    assert "ProjectSheetDetailResponse" in schema
    assert "ProjectSheetDetailUpdate" in schema
    assert "get_project_sheet_detail" in service
    assert "update_project_sheet_detail" in service
    assert "record_operation_log" in service
    assert '@router.get("/{project_id}/sheet-detail"' in api
    assert '@router.put("/{project_id}/sheet-detail"' in api
    assert "PmsProjectSheetDetail" in init_db


def test_project_sheet_update_only_accepts_editable_detail_fields():
    from app.services.project_sheet_fields import validate_sheet_detail_updates

    accepted = validate_sheet_detail_updates({"customer": "客户A", "configuration": "配置说明"})
    assert accepted == {"customer": "客户A", "configuration": "配置说明"}

    for payload in [
        {"project_code": "P-001"},
        {"planned_ship_year": 2026},
        {"product_line": "Bench"},
    ]:
        try:
            validate_sheet_detail_updates(payload)
        except ValueError as exc:
            assert "不可编辑" in str(exc)
        else:
            raise AssertionError(f"{payload} should be rejected")


if __name__ == "__main__":
    test_project_sheet_registry_covers_all_excel_fields()
    test_project_sheet_reference_and_computed_fields_are_readonly()
    test_project_sheet_backend_contract_files_and_routes()
    test_project_sheet_update_only_accepts_editable_detail_fields()
    print("project sheet detail contract passed")
