"""项目档案生命周期字段与迁移契约测试。"""
import os
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "pms-test-project-archive-lifecycle.db"
LEGACY_DB_PATH = ROOT / "data" / "pms-test-project-archive-lifecycle-legacy.db"

for database_path in (DB_PATH, LEGACY_DB_PATH):
    if database_path.exists():
        database_path.unlink()

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = str(DB_PATH)


def test_archive_enabled_model_and_idempotent_upgrade():
    from sqlalchemy import create_engine, inspect, text

    from app.core.database import Base
    from app.models.project import PmsProjectArchive
    from app.models.rbac import SysDept  # noqa: F401
    from app.models.user import SysUser  # noqa: F401
    from app.services.project_archive_lifecycle_migration import upgrade_project_archive_lifecycle

    assert PmsProjectArchive.__table__.columns.is_enabled.type.python_type is int
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Base.metadata.create_all(bind=engine)
    upgrade_project_archive_lifecycle(engine)
    upgrade_project_archive_lifecycle(engine)
    columns = {item["name"] for item in inspect(engine).get_columns("pms_project_archive")}
    assert "is_enabled" in columns
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO pms_project_archive "
            "(project_code, project_code_key, project_name, project_name_key, status, erp_synced) "
            "VALUES ('LC-001', 'lc-001', '生命周期测试', '生命周期测试', 1, 0)"
        ))
        assert connection.execute(text(
            "SELECT is_enabled FROM pms_project_archive WHERE project_code='LC-001'"
        )).scalar_one() == 1


def test_archive_lifecycle_upgrades_historical_schema():
    from sqlalchemy import create_engine, inspect, text

    from app.services.project_archive_lifecycle_migration import upgrade_project_archive_lifecycle

    with sqlite3.connect(LEGACY_DB_PATH) as connection:
        connection.executescript("""
            CREATE TABLE pms_project_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_code NVARCHAR(32) NOT NULL UNIQUE,
                project_code_key NVARCHAR(32) NOT NULL,
                project_name NVARCHAR(128) NOT NULL,
                project_name_key NVARCHAR(128) NOT NULL,
                status INTEGER DEFAULT 1,
                erp_synced INTEGER DEFAULT 0
            );
            INSERT INTO pms_project_archive (
                project_code, project_code_key, project_name, project_name_key, status, erp_synced
            ) VALUES ('LEGACY-001', 'legacy-001', '历史档案', '历史档案', 1, 0);
        """)

    engine = create_engine(f"sqlite:///{LEGACY_DB_PATH}")
    assert "is_enabled" not in {
        item["name"] for item in inspect(engine).get_columns("pms_project_archive")
    }

    upgrade_project_archive_lifecycle(engine)
    upgrade_project_archive_lifecycle(engine)

    inspector = inspect(engine)
    columns = {item["name"] for item in inspector.get_columns("pms_project_archive")}
    indexes = {item["name"] for item in inspector.get_indexes("pms_project_archive")}
    assert "is_enabled" in columns
    assert "idx_project_archive_enabled" in indexes
    with engine.begin() as connection:
        assert connection.execute(text(
            "SELECT is_enabled FROM pms_project_archive WHERE project_code='LEGACY-001'"
        )).scalar_one() == 1


def test_archive_delete_guards_and_enabled_lifecycle():
    from fastapi import HTTPException
    from sqlalchemy import event

    from app.core.database import Base, SessionLocal, engine
    from app.models.operation_log import SysOperationLog
    from app.models.project import ErpSyncLog, PmsProject, PmsProjectArchive
    from app.models.rbac import SysDept
    from app.models.user import SysUser
    from app.schemas.project import ArchiveDeleteBlocker
    from app.services.project_archive_lifecycle import (
        ensure_archive_enabled,
        get_archive_delete_guard,
        get_archive_delete_guards,
        set_archive_enabled,
    )

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = SysUser(
            username="archive-lifecycle",
            real_name="生命周期测试",
            password_hash="x",
            status=1,
        )
        dept = SysDept(dept_name="生命周期测试部门", status=1)
        db.add_all([user, dept])
        db.commit()

        def create_archive(code: str, *, enabled: int = 1, pending: bool = False) -> PmsProjectArchive:
            archive = PmsProjectArchive(
                project_code=code,
                project_name=f"项目档案 {code}",
                is_enabled=enabled,
                erp_sync_status="pending" if pending else None,
            )
            db.add(archive)
            db.flush()
            return archive

        available = create_archive("LC-AVAILABLE")
        referenced = create_archive("LC-REFERENCED")
        failed_only = create_archive("LC-FAILED")
        historical_success = create_archive("LC-SUCCESS")
        pending = create_archive("LC-PENDING", pending=True)
        disabled = create_archive("LC-DISABLED", enabled=0)
        db.add_all([
            PmsProject(
                archive_id=referenced.id,
                project_code="LC-001",
                project_name="引用项目",
                dept_id=dept.id,
                pm_id=user.id,
                status=1,
            ),
            ErpSyncLog(source_id=failed_only.id, action="sync", status="failed"),
            ErpSyncLog(source_id=historical_success.id, action="sync", status="failed"),
            ErpSyncLog(source_id=historical_success.id, action="sync", status="success"),
        ])
        db.commit()

        assert ArchiveDeleteBlocker(
            type="business_reference",
            source="project_progress",
            label="项目进度",
            count=1,
        ).model_dump() == {
            "type": "business_reference",
            "source": "project_progress",
            "label": "项目进度",
            "count": 1,
        }
        assert get_archive_delete_guard(db, available.id) == {
            "can_delete": True,
            "blockers": [],
        }

        referenced_guard = get_archive_delete_guard(db, referenced.id)
        assert referenced_guard == {
            "can_delete": False,
            "blockers": [{
                "type": "business_reference",
                "source": "project_progress",
                "label": "项目进度",
                "count": 1,
            }],
        }
        assert get_archive_delete_guard(db, failed_only.id) == {
            "can_delete": True,
            "blockers": [],
        }
        assert get_archive_delete_guard(db, historical_success.id) == {
            "can_delete": False,
            "blockers": [{
                "type": "external_sync",
                "source": "kingdee",
                "label": "金蝶 ERP",
                "count": 1,
            }],
        }
        assert get_archive_delete_guard(db, pending.id) == {
            "can_delete": False,
            "blockers": [{
                "type": "operation_pending",
                "source": "kingdee",
                "label": "ERP 同步中",
                "count": 1,
            }],
        }

        select_statements: list[str] = []

        def track_select(_connection, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                select_statements.append(statement)

        event.listen(engine, "before_cursor_execute", track_select)
        try:
            guards = get_archive_delete_guards(
                db,
                [available.id, referenced.id, historical_success.id, pending.id, available.id],
            )
        finally:
            event.remove(engine, "before_cursor_execute", track_select)
        assert set(guards) == {available.id, referenced.id, historical_success.id, pending.id}
        assert len(select_statements) == 3

        try:
            ensure_archive_enabled(disabled, "编辑")
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail == {
                "code": "ARCHIVE_DISABLED",
                "message": "项目档案已禁用，无法编辑，请先重新启用",
            }
        else:
            raise AssertionError("禁用档案必须拒绝编辑")
        ensure_archive_enabled(available, "编辑")

        assert set_archive_enabled(db, disabled, False, user.id, None) == {"msg": "禁用成功"}
        assert db.query(SysOperationLog).filter(SysOperationLog.entity_id == str(disabled.id)).count() == 0
        assert set_archive_enabled(db, disabled, True, user.id, None) == {"msg": "启用成功"}
        assert disabled.is_enabled == 1
        assert [log.action for log in db.query(SysOperationLog).filter(
            SysOperationLog.entity_id == str(disabled.id)
        ).all()] == ["enable"]
        assert set_archive_enabled(db, disabled, True, user.id, None) == {"msg": "启用成功"}
        assert set_archive_enabled(db, disabled, False, user.id, None) == {"msg": "禁用成功"}
        assert disabled.is_enabled == 0
        assert [log.action for log in db.query(SysOperationLog).filter(
            SysOperationLog.entity_id == str(disabled.id)
        ).order_by(SysOperationLog.id).all()] == ["enable", "disable"]

        try:
            set_archive_enabled(db, pending, False, user.id, None)
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail["code"] == "ARCHIVE_OPERATION_PENDING"
        else:
            raise AssertionError("同步中的档案必须拒绝禁用")
        assert pending.is_enabled == 1
    finally:
        db.close()


if __name__ == "__main__":
    test_archive_enabled_model_and_idempotent_upgrade()
    test_archive_lifecycle_upgrades_historical_schema()
    test_archive_delete_guards_and_enabled_lifecycle()
    print("project archive lifecycle contract passed")
