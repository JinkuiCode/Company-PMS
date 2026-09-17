"""金蝶项目档案期初预检的行为契约。"""
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = str(ROOT / "data" / "pms-test-kingdee-initial.db")


def test_preflight_maps_only_remark_to_pms_name():
    from app.services.kingdee_initial_archive import preflight_initial_archives

    report = preflight_initial_archives([
        {"TypeCode": "xsxm", "ProjectCode": " A-001 ", "ProjectName": "金蝶旧名称", "Remarks": " 真实项目名 ", "ProjectID": 1},
        {"TypeCode": "xsxm", "ProjectCode": "A-002", "ProjectName": "另一金蝶旧名称", "Remarks": "  ", "ProjectID": 2},
        {"TypeCode": "other", "ProjectCode": "X-001", "ProjectName": "排除", "Remarks": "排除", "ProjectID": 3},
    ])
    assert [(row["project_code"], row["project_name"]) for row in report["ready"]] == [
        ("A-001", "真实项目名"),
        ("A-002", None),
    ]
    assert report["ready"][0]["data_origin"] == "kingdee_initial"
    assert report["ready"][1]["project_name"] is None
    assert report["legacy_name_differences"] == ["A-001", "A-002"]


def test_preflight_allows_repeated_names_but_quarantines_repeated_codes():
    from app.services.kingdee_initial_archive import preflight_initial_archives

    rows = [
        {"TypeCode": "xsxm", "ProjectCode": "N-1", "ProjectName": "N-1", "Remarks": "同名", "ProjectID": 1},
        {"TypeCode": "xsxm", "ProjectCode": "N-2", "ProjectName": "N-2", "Remarks": "同名", "ProjectID": 2},
        {"TypeCode": "xsxm", "ProjectCode": "N-3", "ProjectName": "N-3", "Remarks": "现有名称", "ProjectID": 3},
        {"TypeCode": "xsxm", "ProjectCode": "D-1", "ProjectName": "D-1", "Remarks": "任意", "ProjectID": 4},
        {"TypeCode": "xsxm", "ProjectCode": "d-1", "ProjectName": "d-1", "Remarks": "不同", "ProjectID": 5},
    ]
    report = preflight_initial_archives(rows)
    assert [row["project_code"] for row in report["ready"]] == ["N-1", "N-2", "N-3"]
    assert [issue["reason"] for issue in report["issues"]] == ["duplicate_code", "duplicate_code"]


def test_preflight_quarantines_conflicts_without_substitution():
    from app.services.kingdee_initial_archive import preflight_initial_archives

    rows = [
        {"TypeCode": "xsxm", "ProjectCode": "D-1", "ProjectName": "D-1", "Remarks": "不同备注甲", "ProjectID": 1},
        {"TypeCode": "xsxm", "ProjectCode": "d-1", "ProjectName": "d-1", "Remarks": "不同备注乙", "ProjectID": 2},
        {"TypeCode": "xsxm", "ProjectCode": "N-1", "ProjectName": "N-1", "Remarks": "相同备注", "ProjectID": 3},
        {"TypeCode": "xsxm", "ProjectCode": "N-2", "ProjectName": "N-2", "Remarks": "相同备注", "ProjectID": 4},
        {"TypeCode": "xsxm", "ProjectCode": "P-1", "ProjectName": "P-1", "Remarks": "已经存在", "ProjectID": 5},
        {"TypeCode": "xsxm", "ProjectCode": "E-1", "ProjectName": "E-1", "Remarks": "新备注", "ProjectID": 6},
    ]
    report = preflight_initial_archives(rows, existing_codes={"p-1"})
    assert [row["project_code"] for row in report["ready"]] == ["N-1", "N-2", "E-1"]
    assert {issue["reason"] for issue in report["issues"]} == {
        "duplicate_code", "existing_code",
    }
    assert len(report["issues"]) == 3


def test_archive_model_accepts_null_historical_name_and_records_origin():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.core.database import Base
    from app.models.project import PmsProjectArchive
    import app.models.user  # noqa: F401 - foreign-key metadata
    import app.models.rbac  # noqa: F401 - foreign-key metadata

    columns = PmsProjectArchive.__table__.columns
    assert columns.project_name.nullable
    assert columns.project_name_key.nullable
    assert "data_origin" in columns
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            PmsProjectArchive(project_code="K-1", project_name=None, data_origin="kingdee_initial"),
            PmsProjectArchive(project_code="K-2", project_name=None, data_origin="kingdee_initial"),
        ])
        db.commit()
        assert db.query(PmsProjectArchive).filter(PmsProjectArchive.project_name.is_(None)).count() == 2


def test_archive_allows_repeated_names_but_rejects_repeated_codes():
    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from app.core.database import Base
    from app.models.project import PmsProjectArchive
    import app.models.user  # noqa: F401
    import app.models.rbac  # noqa: F401
    from app.services.project import _ensure_archive_unique_values

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(PmsProjectArchive(project_code="N-1", project_name="同名"))
        db.commit()
        _ensure_archive_unique_values(db, {"project_code": "N-2", "project_name": "同名"})
        db.add(PmsProjectArchive(project_code="N-2", project_name="同名"))
        db.commit()
        assert db.query(PmsProjectArchive).filter_by(project_name="同名").count() == 2
        db.add(PmsProjectArchive(project_code="N-1", project_name="其他名称"))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("项目编码重复必须拒绝")


def test_archive_response_accepts_null_name():
    from app.schemas.project import ArchiveOption, ArchiveResponse

    assert ArchiveResponse.model_fields["project_name"].is_required() is True
    assert ArchiveResponse.model_fields["project_name"].annotation == str | None
    assert ArchiveOption.model_fields["project_name"].annotation == str | None


def test_origin_is_read_only_archive_metadata():
    from app.services.field_policy import MODULE_PROJECT_ARCHIVE, get_business_field_registry

    fields = {item["key"]: item for item in get_business_field_registry(MODULE_PROJECT_ARCHIVE)}
    origin = fields["data_origin"]
    assert origin["label"] == "档案来源"
    assert origin["source_type"] == "system"
    assert origin["default_editable"] is False


def test_nameless_archive_requires_name_before_edit_sync_or_progress():
    from fastapi import HTTPException
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.core.database import Base
    from app.models.project import PmsProjectArchive
    import app.models.user  # noqa: F401 - foreign-key metadata
    import app.models.rbac  # noqa: F401 - foreign-key metadata
    from app.schemas.project import ArchiveUpdate, ProjectCreate
    from app.services.project import (
        create_project,
        update_archive,
        validate_archive_for_business_operation,
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        archive = PmsProjectArchive(
            project_code="K-UNNAMED", project_name=None, data_origin="kingdee_initial"
        )
        db.add(archive)
        db.commit()
        for action in (
            lambda: update_archive(db, archive.id, ArchiveUpdate(customer="新客户"), user_id=1),
            lambda: validate_archive_for_business_operation(db, archive),
            lambda: create_project(
                db,
                ProjectCreate(
                    archive_id=archive.id,
                    project_code="ignored",
                    project_name="ignored",
                    dept_id=1,
                    pm_id=1,
                ),
                operator_id=1,
            ),
        ):
            try:
                action()
            except HTTPException as exc:
                assert exc.status_code == 422
                assert exc.detail["field_key"] == "project_name"
            else:
                raise AssertionError("未补项目名称的期初档案不能进入后续业务")


def test_sqlite_upgrade_preserves_archive_and_allows_multiple_empty_names():
    from sqlalchemy import create_engine, inspect, text

    from app.services.project_archive_initial_migration import upgrade_project_archive_initial

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sys_user (id INTEGER PRIMARY KEY)"))
        connection.execute(text("""
            CREATE TABLE pms_project_archive (
                id INTEGER PRIMARY KEY, project_code NVARCHAR(32) NOT NULL,
                project_code_key NVARCHAR(32) NOT NULL,
                project_name NVARCHAR(128) NOT NULL,
                project_name_key NVARCHAR(128) NOT NULL,
                status INTEGER NOT NULL DEFAULT 1,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                erp_synced INTEGER NOT NULL DEFAULT 0
            )
        """))
        connection.execute(text("""
            CREATE UNIQUE INDEX ux_pms_project_archive_project_name_key
            ON pms_project_archive (project_name_key)
        """))
        connection.execute(text("""
            INSERT INTO pms_project_archive
            (id, project_code, project_code_key, project_name, project_name_key)
            VALUES (1, 'OLD', 'old', '原有项目', '原有项目')
        """))
    upgrade_project_archive_initial(engine)
    upgrade_project_archive_initial(engine)
    columns = {item["name"]: item for item in inspect(engine).get_columns("pms_project_archive")}
    assert columns["project_name"]["nullable"]
    assert columns["project_name_key"]["nullable"]
    assert "data_origin" in columns
    with engine.begin() as connection:
        assert connection.execute(text("SELECT project_name, data_origin FROM pms_project_archive WHERE id=1")).one() == ("原有项目", "pms")
        connection.execute(text("""
            INSERT INTO pms_project_archive
            (project_code, project_code_key, project_name, project_name_key, data_origin, status, erp_synced)
            VALUES ('A', 'a', NULL, NULL, 'kingdee_initial', 1, 0),
                   ('B', 'b', NULL, NULL, 'kingdee_initial', 1, 0)
        """))
        assert connection.execute(text("SELECT COUNT(*) FROM pms_project_archive WHERE project_name IS NULL")).scalar_one() == 2
        connection.execute(text("""
            INSERT INTO pms_project_archive
            (project_code, project_code_key, project_name, project_name_key, data_origin, status, erp_synced)
            VALUES ('C', 'c', '同名', '同名', 'kingdee_initial', 1, 0),
                   ('D', 'd', '同名', '同名', 'kingdee_initial', 1, 0)
        """))
        assert connection.execute(text("SELECT COUNT(*) FROM pms_project_archive WHERE project_name='同名'")).scalar_one() == 2
    assert "ux_pms_project_archive_project_name_key" not in {
        item["name"] for item in inspect(engine).get_indexes("pms_project_archive")
    }


def test_upgrade_drops_legacy_name_index_without_rebuilding_current_table():
    from sqlalchemy import create_engine, inspect, text

    from app.core.database import Base
    from app.models.project import PmsProjectArchive
    import app.models.user  # noqa: F401
    import app.models.rbac  # noqa: F401
    from app.services.project_archive_initial_migration import upgrade_project_archive_initial

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        if "ux_pms_project_archive_project_name_key" not in {
            item["name"] for item in inspect(connection).get_indexes("pms_project_archive")
        }:
            connection.execute(text("""
                CREATE UNIQUE INDEX ux_pms_project_archive_project_name_key
                ON pms_project_archive (project_name_key)
            """))
    upgrade_project_archive_initial(engine)
    upgrade_project_archive_initial(engine)
    assert "ux_pms_project_archive_project_name_key" not in {
        item["name"] for item in inspect(engine).get_indexes("pms_project_archive")
    }
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO pms_project_archive
            (project_code, project_code_key, project_name, project_name_key, data_origin, status, erp_synced)
            VALUES ('X', 'x', '同名', '同名', 'pms', 1, 0),
                   ('Y', 'y', '同名', '同名', 'pms', 1, 0)
        """))


def test_mssql_upgrade_drops_name_index_without_recreating_it():
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.services import project_archive_initial_migration as migration

    statements = []

    class FakeEngine:
        dialect = SimpleNamespace(name="mssql")

        @contextmanager
        def begin(self):
            yield self

        def execute(self, statement):
            statements.append(str(statement))

    class FakeInspector:
        def has_table(self, _table):
            return True

        def get_columns(self, _table):
            return [
                {"name": "project_name", "nullable": False},
                {"name": "project_name_key", "nullable": True},
            ]

        def get_indexes(self, _table):
            return [{"name": migration.NAME_INDEX}]

    engine = FakeEngine()
    with patch.object(migration, "inspect", return_value=FakeInspector()):
        migration.upgrade_project_archive_initial(engine)
    assert any("ADD data_origin" in sql for sql in statements)
    assert any("DROP INDEX ux_pms_project_archive_project_name_key ON pms_project_archive" in sql for sql in statements)
    assert any("ALTER COLUMN project_name NVARCHAR(128) NULL" in sql for sql in statements)
    assert not any("CREATE UNIQUE INDEX ux_pms_project_archive_project_name_key" in sql for sql in statements)


def test_imported_archive_has_provenance_and_audit_without_fake_sync_time():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.core.database import Base
    from app.models.project import PmsProjectArchive
    from app.models.operation_log import SysOperationLog
    import app.models.user  # noqa: F401 - foreign-key metadata
    import app.models.rbac  # noqa: F401 - foreign-key metadata
    from app.services.kingdee_initial_archive import insert_initial_archives

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        inserted = insert_initial_archives(db, [{
            "project_code": "K-1", "project_name": None,
            "source_id": "source-1", "data_origin": "kingdee_initial",
        }], operator_id=None)
        db.commit()
        archive = db.query(PmsProjectArchive).one()
        assert inserted == 1
        assert archive.project_name is None
        assert archive.data_origin == "kingdee_initial"
        assert archive.erp_synced == 0
        assert archive.erp_sync_status == "historical"
        assert archive.erp_sync_time is None
        assert db.query(SysOperationLog).count() == 1

        from app.services.project_archive_lifecycle import get_archive_delete_guard

        guard = get_archive_delete_guard(db, archive.id)
        assert guard["can_delete"] is False
        assert any(blocker["source"] == "kingdee" for blocker in guard["blockers"])

        from fastapi import HTTPException
        from app.services.project import delete_archive

        try:
            delete_archive(db, archive.id)
            raise AssertionError("Kingdee initial archive was deleted")
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail["code"] == "ARCHIVE_DELETE_BLOCKED"
        assert db.get(PmsProjectArchive, archive.id) is not None


def test_preflight_fingerprint_detects_source_or_target_changes():
    from app.services.kingdee_initial_archive import preflight_fingerprint, preflight_initial_archives

    row = {"TypeCode": "xsxm", "ProjectCode": "F-1", "ProjectName": "F-1", "Remarks": "名称", "ProjectID": 1}
    current = preflight_initial_archives([row])
    assert preflight_fingerprint(current) == preflight_fingerprint(preflight_initial_archives([dict(row)]))
    changed_source = preflight_initial_archives([{**row, "Remarks": "改过的名称"}])
    changed_target = preflight_initial_archives([row], existing_codes={"F-1"})
    assert preflight_fingerprint(current) != preflight_fingerprint(changed_source)
    assert preflight_fingerprint(current) != preflight_fingerprint(changed_target)


if __name__ == "__main__":
    test_preflight_maps_only_remark_to_pms_name()
    test_preflight_allows_repeated_names_but_quarantines_repeated_codes()
    test_preflight_quarantines_conflicts_without_substitution()
    test_archive_model_accepts_null_historical_name_and_records_origin()
    test_archive_allows_repeated_names_but_rejects_repeated_codes()
    test_archive_response_accepts_null_name()
    test_origin_is_read_only_archive_metadata()
    test_nameless_archive_requires_name_before_edit_sync_or_progress()
    test_sqlite_upgrade_preserves_archive_and_allows_multiple_empty_names()
    test_upgrade_drops_legacy_name_index_without_rebuilding_current_table()
    test_mssql_upgrade_drops_name_index_without_recreating_it()
    test_imported_archive_has_provenance_and_audit_without_fake_sync_time()
    test_preflight_fingerprint_detects_source_or_target_changes()
    print("kingdee initial archive contract passed")
