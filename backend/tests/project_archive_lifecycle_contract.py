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


if __name__ == "__main__":
    test_archive_enabled_model_and_idempotent_upgrade()
    test_archive_lifecycle_upgrades_historical_schema()
    print("project archive lifecycle contract passed")
