"""项目档案与项目进度字段规则契约测试。"""
import datetime
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "pms-test-field-policy.db"

if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = str(DB_PATH)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_field_policy_registry_preserves_technical_limits():
    from app.services.field_policy import (
        MODULE_PROJECT_ARCHIVE,
        MODULE_PROJECT_PROGRESS,
        get_business_field_registry,
    )

    archive_fields = {
        field["key"]: field
        for field in get_business_field_registry(MODULE_PROJECT_ARCHIVE)
    }
    progress_fields = {
        field["key"]: field
        for field in get_business_field_registry(MODULE_PROJECT_PROGRESS)
    }

    assert archive_fields["project_code"]["required_locked"] is True
    assert archive_fields["project_code"]["editable_locked"] is True
    assert archive_fields["project_code"]["source_type"] == "detail"
    assert "status" not in archive_fields
    assert progress_fields["archive_id"]["required_locked"] is True
    assert progress_fields["archive_id"]["required_cap"] is True
    assert progress_fields["dept_id"]["required_locked"] is True
    assert progress_fields["pm_id"]["required_locked"] is True
    assert progress_fields["budget"]["source_type"] == "project"
    assert progress_fields["customer"]["editable_cap"] is False
    assert progress_fields["product_category"]["editable_cap"] is False
    assert progress_fields["design_days"]["editable_cap"] is False


def test_field_policy_rejects_invalid_combinations_and_tracks_required_effective_time():
    from fastapi import HTTPException

    from app.core.database import Base, SessionLocal, engine
    from app.schemas.field_policy import FieldPolicyBatchUpdate, FieldPolicyUpdateItem
    from app.services.field_policy import update_field_policies

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        try:
            update_field_policies(
                db,
                "project_progress",
                FieldPolicyBatchUpdate(items=[
                    FieldPolicyUpdateItem(
                        field_key="category",
                        visible=True,
                        editable=False,
                        required=True,
                        list_available=True,
                    )
                ]),
                operator_id=1,
            )
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError("只读字段不能同时设为必填")

        result = update_field_policies(
            db,
            "project_progress",
            FieldPolicyBatchUpdate(items=[
                FieldPolicyUpdateItem(
                    field_key="category",
                    visible=True,
                    editable=True,
                    required=True,
                    list_available=True,
                )
            ]),
            operator_id=1,
        )
        category = next(item for item in result["items"] if item["field_key"] == "category")
        assert category["required"] is True
        assert category["required_effective_at"] is not None

        try:
            update_field_policies(
                db,
                "project_progress",
                FieldPolicyBatchUpdate(items=[
                    FieldPolicyUpdateItem(
                        field_key="category",
                        visible=True,
                        editable=True,
                        required=True,
                        list_available=False,
                    )
                ]),
                operator_id=2,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("缺少更新时间的旧快照不能覆盖已保存规则")

        update_field_policies(
            db,
            "project_progress",
            FieldPolicyBatchUpdate(items=[
                FieldPolicyUpdateItem(
                    field_key="category",
                    visible=True,
                    editable=True,
                    required=True,
                    list_available=False,
                    expected_updated_at=category["updated_at"],
                )
            ]),
            operator_id=2,
        )
    finally:
        db.close()


def test_required_policy_applies_to_new_entities_and_exempts_legacy_entities():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.services.field_policy import validate_business_field_write

    db = SessionLocal()
    try:
        policy_time = datetime.datetime.now()
        try:
            validate_business_field_write(
                db,
                "project_progress",
                current_values={},
                updates={},
                entity_created_at=policy_time + datetime.timedelta(seconds=1),
                is_create=False,
            )
        except HTTPException as exc:
            assert exc.status_code == 422
            assert exc.detail["code"] == "FIELD_POLICY_VALIDATION_FAILED"
            assert exc.detail["fields"][0]["field_key"] == "category"
        else:
            raise AssertionError("规则生效后的项目必须满足必填字段")

        validate_business_field_write(
            db,
            "project_progress",
            current_values={},
            updates={},
            entity_created_at=policy_time - datetime.timedelta(days=1),
            is_create=False,
        )
    finally:
        db.close()


def test_project_create_enforces_dynamic_required_fields_and_rolls_back():
    import json

    from fastapi import HTTPException

    from app.core.database import Base, SessionLocal, engine
    from app.models.project import PmsProject, PmsProjectArchive, PmsProjectSheetDetail
    from app.models.rbac import SysDept
    from app.models.user import SysUser
    from app.schemas.project import ProjectCreate
    from app.services.enum_registry import initialize_enum_definitions
    from app.services.project import create_project

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        initialize_enum_definitions(db)
        dept = SysDept(dept_name="字段规则测试部门", status=1)
        user = SysUser(username="field-policy-user", real_name="字段规则用户", password_hash="x", status=1)
        archive = PmsProjectArchive(project_code="FP-ARCHIVE", project_name="字段规则档案", status=1)
        db.add_all([dept, user, archive])
        db.commit()

        base_data = {
            "archive_id": archive.id,
            "project_code": "FP-PROJECT",
            "project_name": "字段规则项目",
            "dept_id": dept.id,
            "pm_id": user.id,
        }
        try:
            create_project(
                db,
                ProjectCreate(**base_data),
                operator_id=user.id,
            )
        except HTTPException as exc:
            assert exc.status_code == 422
            assert exc.detail["fields"][0]["field_key"] == "category"
        else:
            raise AssertionError("新项目缺少生效后的动态必填字段时必须拒绝")
        assert db.query(PmsProject).filter(PmsProject.project_code == "FP-PROJECT").count() == 0
        assert db.query(PmsProjectSheetDetail).count() == 0

        result = create_project(
            db,
            ProjectCreate(**base_data, sheet_values={"category": "标准项目"}),
            operator_id=user.id,
        )
        detail = db.query(PmsProjectSheetDetail).filter(
            PmsProjectSheetDetail.project_id == result["id"]
        ).one()
        assert json.loads(detail.detail_data)["category"] == "标准项目"
    finally:
        db.close()


def test_field_policy_routes_and_runtime_integration_contract():
    main = read("main.py")
    api = read("app/api/field_policies.py")
    projects = read("app/services/project.py")
    schema = read("app/schemas/project.py")

    assert "field_policies.router" in main
    assert 'require_permission("system:field-policy:view")' in api
    assert 'require_permission("system:field-policy:edit")' in api
    assert "validate_business_field_write" in projects
    assert "sheet_values" in schema
    assert "archive_id: int\n" in schema


if __name__ == "__main__":
    test_field_policy_registry_preserves_technical_limits()
    test_field_policy_rejects_invalid_combinations_and_tracks_required_effective_time()
    test_required_policy_applies_to_new_entities_and_exempts_legacy_entities()
    test_project_create_enforces_dynamic_required_fields_and_rolls_back()
    test_field_policy_routes_and_runtime_integration_contract()
    print("field policy contract passed")
