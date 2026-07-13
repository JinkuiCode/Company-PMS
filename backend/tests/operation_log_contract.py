"""操作日志能力契约测试。

这些测试优先约束结构和关键工具函数，避免后续模块新增写操作时各自为政。
"""
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault("DB_DIALECT", "sqlite")
os.environ.setdefault("SQLITE_DB_PATH", "data/pms-test-operation-log.db")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_operation_log_backend_contract_files_and_routes():
    model = read("app/models/operation_log.py")
    service = read("app/services/operation_log.py")
    api = read("app/api/operation_logs.py")
    main = (ROOT.parent / "backend" / "main.py").read_text(encoding="utf-8")
    init_db = read("app/models/init_db.py")

    for field in [
        "module",
        "action",
        "entity_type",
        "entity_id",
        "entity_name",
        "operator_id",
        "operator_name",
        "ip_address",
        "user_agent",
        "request_path",
        "status",
        "summary",
        "before_data",
        "after_data",
        "diff_data",
        "created_at",
    ]:
        assert field in model

    assert "class SysOperationLog" in model
    assert "SENSITIVE_KEYWORDS" in service
    assert "def sanitize_data" in service
    assert "def diff_data" in service
    assert "def record_operation_log" in service
    assert 'APIRouter(prefix="/api/operation-logs"' in api
    assert "operation_logs.router" in main
    assert "system:operation-log:list" in init_db
    assert "操作日志" in init_db


def test_operation_log_sanitizes_sensitive_fields_and_diffs_values():
    from app.services.operation_log import diff_data, sanitize_data

    masked = sanitize_data(
        {
            "username": "admin",
            "password": "admin123",
            "remember_token": "abc",
            "nested": {"api_key": "secret-key", "safe": "visible"},
        }
    )

    assert masked["username"] == "admin"
    assert masked["password"] == "***"
    assert masked["remember_token"] == "***"
    assert masked["nested"]["api_key"] == "***"
    assert masked["nested"]["safe"] == "visible"

    diff = diff_data({"name": "旧项目", "password_hash": "old"}, {"name": "新项目", "password_hash": "new"})
    assert diff["name"] == {"before": "旧项目", "after": "新项目"}
    assert diff["password_hash"] == {"before": "***", "after": "***"}


def test_operation_log_runtime_write_and_menu():
    from app.core.database import SessionLocal
    from app.models.init_db import init_db
    from app.models.operation_log import SysOperationLog
    from app.models.rbac import SysMenu
    from app.services.operation_log import record_operation_log

    init_db()
    db = SessionLocal()
    try:
        menu = db.query(SysMenu).filter(SysMenu.permission_code == "system:operation-log:list").first()
        assert menu is not None

        log = record_operation_log(
            db,
            module="测试模块",
            action="update",
            entity_type="contract",
            entity_id="1",
            entity_name="契约测试",
            summary="契约测试日志",
            before_data={"name": "旧值", "password": "old"},
            after_data={"name": "新值", "password": "new"},
            commit=True,
        )
        saved = db.query(SysOperationLog).filter(SysOperationLog.id == log.id).first()
        assert saved is not None
        assert '"password": "***"' in saved.after_data
        assert '"name": {"before": "旧值", "after": "新值"}' in saved.diff_data
    finally:
        db.close()


if __name__ == "__main__":
    test_operation_log_backend_contract_files_and_routes()
    test_operation_log_sanitizes_sensitive_fields_and_diffs_values()
    test_operation_log_runtime_write_and_menu()
    print("operation log contract passed")
