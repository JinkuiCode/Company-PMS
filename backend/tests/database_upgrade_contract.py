"""Production database upgrades must not run in the web-service startup."""
import asyncio
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine


ROOT = Path(__file__).resolve().parents[1]


def new_database() -> Path:
    fd, name = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    path = Path(name)
    path.unlink()
    return path


def run_upgrade(path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({
        "PMS_ENV": "development",
        "DB_DIALECT": "sqlite",
        "SQLITE_DB_PATH": str(path),
        "PMS_CONFIG_FILE": str(path.with_suffix(".env")),
    })
    return subprocess.run(
        [sys.executable, "scripts/upgrade_database.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


def test_upgrade_marks_database_ready_and_can_repeat() -> None:
    from app.services.database_revision import check_database_ready

    path = new_database()
    engine = create_engine(f"sqlite:///{path}")
    try:
        for _ in range(2):
            result = run_upgrade(path)
            assert result.returncode == 0, result.stderr or result.stdout
            check_database_ready(engine)
        with sqlite3.connect(path) as connection:
            assert connection.execute("SELECT COUNT(*) FROM pms_database_revision").fetchone()[0] == 1
            assert connection.execute("SELECT COUNT(*) FROM erp_sync_task").fetchone()[0] == 0
            assert connection.execute("SELECT COUNT(*) FROM pms_report_export_job").fetchone()[0] == 0
            assert connection.execute("SELECT COUNT(*) FROM sys_menu WHERE permission_code LIKE 'system:sync:%'").fetchone()[0] == 3
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)


def test_missing_and_outdated_revision_block_startup() -> None:
    from app.services.database_revision import DatabaseUpgradeRequired, check_database_ready

    path = new_database()
    engine = create_engine(f"sqlite:///{path}")
    try:
        try:
            check_database_ready(engine)
        except DatabaseUpgradeRequired:
            pass
        else:
            raise AssertionError("missing revision must block production startup")

        result = run_upgrade(path)
        assert result.returncode == 0, result.stderr or result.stdout
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE pms_database_revision SET revision = 'old'")
        try:
            check_database_ready(engine)
        except DatabaseUpgradeRequired:
            pass
        else:
            raise AssertionError("old revision must block production startup")
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)


def test_production_lifespan_checks_revision_without_running_upgrade() -> None:
    import main

    async def exercise() -> None:
        async with main.lifespan(main.app):
            pass

    with (
        patch.object(main.settings, "PMS_ENV", "production"),
        patch.object(main, "validate_runtime_config"),
        patch.object(main, "init_db") as initialize,
        patch.object(main, "check_database_ready") as check,
        patch('app.services.report_export_jobs.worker'),
    ):
        asyncio.run(exercise())
        check.assert_called_once()
        initialize.assert_not_called()


def test_failed_upgrade_cannot_leave_ready_marker() -> None:
    from app.services.database_revision import (
        DatabaseUpgradeRequired,
        check_database_ready,
        mark_database_ready,
    )
    from scripts import upgrade_database as upgrade_script

    path = new_database()
    engine = create_engine(f"sqlite:///{path}")
    try:
        from app.models.database_revision import PmsDatabaseRevision

        PmsDatabaseRevision.__table__.create(engine)
        mark_database_ready(engine)
        with (
            patch.object(upgrade_script, "engine", engine),
            patch.object(upgrade_script, "validate_runtime_config"),
            patch.object(upgrade_script, "init_db", side_effect=RuntimeError("migration failed")),
        ):
            try:
                upgrade_script.upgrade_database()
            except RuntimeError as exc:
                assert str(exc) == "migration failed"
            else:
                raise AssertionError("upgrade failure must propagate")
        try:
            check_database_ready(engine)
        except DatabaseUpgradeRequired:
            pass
        else:
            raise AssertionError("failed upgrade must not keep the old ready marker")
    finally:
        engine.dispose()
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    test_upgrade_marks_database_ready_and_can_repeat()
    test_missing_and_outdated_revision_block_startup()
    test_production_lifespan_checks_revision_without_running_upgrade()
    test_failed_upgrade_cannot_leave_ready_marker()
    print("database upgrade contract passed")
