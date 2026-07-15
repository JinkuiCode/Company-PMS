"""项目档案字段语义化、唯一性与档案引用契约测试。"""
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "pms-test-project-archive-semantic.db"

if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = str(DB_PATH)


def test_archive_model_and_schema_use_business_semantic_names():
    from app.models.project import PmsProject, PmsProjectArchive
    from app.schemas.project import ArchiveCreate, ArchiveResponse, ArchiveUpdate, ProjectResponse

    archive_columns = set(PmsProjectArchive.__table__.columns.keys())
    project_columns = set(PmsProject.__table__.columns.keys())
    archive_create_fields = set(ArchiveCreate.model_fields)
    archive_update_fields = set(ArchiveUpdate.model_fields)
    archive_response_fields = set(ArchiveResponse.model_fields)
    project_response_fields = set(ProjectResponse.model_fields)

    expected_archive_fields = {
        "customer",
        "product_category",
        "equipment_series",
        "serial_no",
    }
    assert expected_archive_fields <= archive_columns
    assert expected_archive_fields <= archive_create_fields
    assert expected_archive_fields <= archive_update_fields
    assert expected_archive_fields <= archive_response_fields
    assert "product_category" in project_columns
    assert "product_category" in project_response_fields

    for legacy_name in ("product_line", "product_type"):
        assert legacy_name not in archive_columns
        assert legacy_name not in archive_create_fields
        assert legacy_name not in archive_update_fields
        assert legacy_name not in archive_response_fields
    assert "product_line" not in project_columns
    assert "product_line" not in project_response_fields

    assert PmsProjectArchive.__table__.columns.product_category.type.python_type is int
    assert PmsProjectArchive.__table__.columns.equipment_series.type.python_type is int
    assert PmsProject.__table__.columns.product_category.type.python_type is int


def test_archive_update_enforces_database_text_lengths():
    from pydantic import ValidationError

    from app.schemas.project import ArchiveUpdate

    limits = {
        "project_code": 32,
        "project_name": 128,
        "customer": 128,
        "serial_no": 64,
    }
    for field_key, max_length in limits.items():
        try:
            ArchiveUpdate(**{field_key: "x" * (max_length + 1)})
        except ValidationError:
            continue
        raise AssertionError(f"{field_key} 更新值必须限制为数据库列长度 {max_length}")


def test_project_sheet_archive_fields_are_read_only_references():
    from app.services.project_sheet_fields import FIELD_BY_KEY

    expected = {
        "project_code": "项目号",
        "project_name": "项目名称",
        "customer": "客户",
        "product_category": "产品类别",
        "equipment_series": "设备系列",
        "serial_no": "序列号",
    }
    for field_key, label in expected.items():
        field = FIELD_BY_KEY[field_key]
        assert field["label"] == label
        assert field["source_type"] == "archive"
        assert field["editable"] is False
    assert "product_line" not in FIELD_BY_KEY


def test_archive_field_policy_declares_unique_fields_and_enum_bindings():
    from app.services.field_policy import MODULE_PROJECT_ARCHIVE, get_business_field_registry

    fields = {
        item["key"]: item
        for item in get_business_field_registry(MODULE_PROJECT_ARCHIVE)
    }
    assert fields["project_code"]["label"] == "项目编号"
    assert fields["project_code"]["editable_locked"] is True
    assert fields["project_name"]["label"] == "项目名称"
    assert fields["customer"]["value_type"] == "text"
    assert fields["product_category"]["enum_code"] == "product_category"
    assert fields["equipment_series"]["enum_code"] == "equipment_series"
    assert fields["serial_no"]["value_type"] == "text"
    assert "product_line" not in fields
    assert "product_type" not in fields


def test_archive_uniqueness_and_linked_project_synchronization():
    from fastapi import HTTPException

    from app.core.database import Base, SessionLocal, engine
    from app.models.project import PmsProject, PmsProjectArchive
    from app.models.rbac import SysDept
    from app.models.user import SysUser
    from app.schemas.project import ArchiveCreate, ArchiveUpdate, ProjectUpdate
    from app.services.enum_registry import initialize_enum_definitions
    from app.services.project import create_archive, update_archive, update_project

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        initialize_enum_definitions(db)
        user = SysUser(username="archive-semantic", real_name="档案测试", password_hash="x", status=1)
        dept = SysDept(dept_name="档案测试部门", status=1)
        db.add_all([user, dept])
        db.commit()

        first_id = create_archive(
            db,
            ArchiveCreate(
                project_code="  ARCH-001  ",
                project_name="  唯一项目一  ",
                customer=" 客户 A ",
                product_category=1,
                equipment_series=1,
                serial_no=" SN-001 ",
            ),
            user_id=user.id,
        )["id"]
        first = db.get(PmsProjectArchive, first_id)
        assert first.project_code == "ARCH-001"
        assert first.project_name == "唯一项目一"
        assert first.customer == "客户 A"
        assert first.serial_no == "SN-001"

        def expect_conflict(payload: ArchiveCreate, field_key: str) -> None:
            try:
                create_archive(db, payload, user_id=user.id)
            except HTTPException as exc:
                assert exc.status_code == 409
                assert exc.detail["field_key"] == field_key
            else:
                raise AssertionError(f"{field_key} 重复时必须拒绝")

        expect_conflict(
            ArchiveCreate(project_code="arch-001", project_name="另一个名称"),
            "project_code",
        )
        expect_conflict(
            ArchiveCreate(project_code="ARCH-002", project_name=" 唯一项目一 "),
            "project_name",
        )
        expect_conflict(
            ArchiveCreate(project_code="ARCH-003", project_name="唯一项目三", serial_no="sn-001"),
            "serial_no",
        )

        second_id = create_archive(
            db,
            ArchiveCreate(project_code="ARCH-004", project_name="唯一项目四", serial_no=None),
            user_id=user.id,
        )["id"]
        create_archive(
            db,
            ArchiveCreate(project_code="ARCH-005", project_name="唯一项目五", serial_no=""),
            user_id=user.id,
        )

        for payload, field_key in (
            (ArchiveCreate(project_code="   ", project_name="有效名称"), "project_code"),
            (ArchiveCreate(project_code="ARCH-006", project_name="   "), "project_name"),
        ):
            try:
                create_archive(db, payload, user_id=user.id)
            except HTTPException as exc:
                assert exc.status_code == 422
                assert exc.detail["field_key"] == field_key
            else:
                raise AssertionError(f"{field_key} 去除首尾空格后为空时必须拒绝")

        project = PmsProject(
            archive_id=second_id,
            project_code="ARCH-004",
            project_name="唯一项目四",
            dept_id=dept.id,
            pm_id=user.id,
            product_category=1,
            status=1,
        )
        db.add(project)
        db.commit()

        update_archive(
            db,
            second_id,
            ArchiveUpdate(
                project_code="ARCH-004-NEW",
                project_name="唯一项目四（新）",
                product_category=2,
            ),
            user_id=user.id,
        )
        db.refresh(project)
        assert project.project_code == "ARCH-004-NEW"
        assert project.project_name == "唯一项目四（新）"
        assert project.product_category == 2

        try:
            update_project(
                db,
                project.id,
                ProjectUpdate(project_name="项目进度侧改名"),
                user_id=user.id,
            )
        except HTTPException as exc:
            assert exc.status_code == 422
            assert exc.detail["code"] == "FIELD_POLICY_VALIDATION_FAILED"
            assert exc.detail["fields"] == [{
                "field_key": "project_name",
                "message": "字段已设为只读",
            }]
        else:
            raise AssertionError("已关联档案的项目名称必须在项目档案中维护")
        db.refresh(project)
        assert project.project_name == "唯一项目四（新）"
    finally:
        db.close()


if __name__ == "__main__":
    test_archive_model_and_schema_use_business_semantic_names()
    test_archive_update_enforces_database_text_lengths()
    test_project_sheet_archive_fields_are_read_only_references()
    test_archive_field_policy_declares_unique_fields_and_enum_bindings()
    test_archive_uniqueness_and_linked_project_synchronization()
    print("project archive semantic contract passed")
