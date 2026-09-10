"""Fresh-database administrator bootstrap security contract."""
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_init_result(
    db_path: str,
    username: str | None = None,
    password: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DB_DIALECT"] = "sqlite"
    env["SQLITE_DB_PATH"] = db_path
    env.pop("PMS_BOOTSTRAP_ADMIN_USERNAME", None)
    env.pop("PMS_BOOTSTRAP_ADMIN_PASSWORD", None)
    if username is not None:
        env["PMS_BOOTSTRAP_ADMIN_USERNAME"] = username
    if password is not None:
        env["PMS_BOOTSTRAP_ADMIN_PASSWORD"] = password

    return subprocess.run(
        [sys.executable, "-c", "from app.models.init_db import init_db; init_db()"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def run_init(db_path: str, username: str | None = None, password: str | None = None) -> None:
    result = run_init_result(db_path, username, password)
    assert result.returncode == 0, result.stderr or result.stdout


def new_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return path


def test_no_hardcoded_bootstrap_account() -> None:
    path = new_db_path()
    try:
        run_init(path)
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM sys_user").fetchone()[0] == 0
    finally:
        Path(path).unlink(missing_ok=True)


def test_environment_bootstrap_account() -> None:
    path = new_db_path()
    try:
        run_init(path, "local_rescue_admin", "Temporary-Strong-Password-2026")
        with sqlite3.connect(path) as conn:
            user = conn.execute(
                "SELECT id, username, password_hash, status FROM sys_user"
            ).fetchone()
            assert user is not None
            assert user[1] == "local_rescue_admin"
            assert user[2] != "Temporary-Strong-Password-2026"
            assert user[3] == 1
            role_codes = {
                row[0]
                for row in conn.execute(
                    "SELECT r.role_code FROM sys_user_role ur "
                    "JOIN sys_role r ON r.id = ur.role_id WHERE ur.user_id = ?",
                    (user[0],),
                ).fetchall()
            }
            assert role_codes == {"admin"}
    finally:
        Path(path).unlink(missing_ok=True)


def test_incomplete_or_weak_bootstrap_credentials_fail_closed() -> None:
    for username, password, expected_message in [
        ("local_rescue_admin", None, "必须同时配置"),
        ("local_rescue_admin", "short", "至少需要 12 个字符"),
    ]:
        path = new_db_path()
        try:
            result = run_init_result(path, username, password)
            assert result.returncode != 0
            assert expected_message in (result.stderr + result.stdout)
            with sqlite3.connect(path) as conn:
                assert conn.execute("SELECT COUNT(*) FROM sys_user").fetchone()[0] == 0
        finally:
            Path(path).unlink(missing_ok=True)


def test_bootstrap_after_roles_already_exist() -> None:
    path = new_db_path()
    try:
        run_init(path)
        run_init(path, "local_rescue_admin", "Temporary-Strong-Password-2026")
        with sqlite3.connect(path) as conn:
            user_role = conn.execute(
                "SELECT u.username, r.role_code FROM sys_user_role ur "
                "JOIN sys_user u ON u.id = ur.user_id "
                "JOIN sys_role r ON r.id = ur.role_id"
            ).fetchone()
            assert user_role == ("local_rescue_admin", "admin")
    finally:
        Path(path).unlink(missing_ok=True)


def test_health_route_is_public_and_credential_free() -> None:
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '@app.get("/api/health"' in main
    health_block = main.split('@app.get("/api/health"', 1)[1].split("@app.", 1)[0]
    assert "Depends(" not in health_block


if __name__ == "__main__":
    test_no_hardcoded_bootstrap_account()
    test_environment_bootstrap_account()
    test_incomplete_or_weak_bootstrap_credentials_fail_closed()
    test_bootstrap_after_roles_already_exist()
    test_health_route_is_public_and_credential_free()
    print("bootstrap admin contract passed")
