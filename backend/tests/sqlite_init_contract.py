import os
import sqlite3
import tempfile


def test_sqlite_init_db() -> None:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)

    os.environ["DB_DIALECT"] = "sqlite"
    os.environ["SQLITE_DB_PATH"] = path

    from app.models.init_db import init_db

    init_db()

    conn = sqlite3.connect(path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "pms_project_sheet_detail" in tables
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(pms_project_sheet_detail)").fetchall()
        }
        assert {"project_id", "detail_data", "created_by", "updated_by"}.issubset(columns)
        dict_codes = {
            row[0]
            for row in conn.execute("SELECT dict_code FROM sys_dict").fetchall()
        }
        assert {
            "archive_status",
            "project_status",
            "product_line",
            "product_type",
            "task_status",
            "erp_sync_status",
            "data_scope",
        }.issubset(dict_codes)
        assert not {
            "user_manage",
            "role_manage",
            "project_list",
            "project_archive",
            "project_task",
        }.intersection(dict_codes)

        enum_menu = conn.execute(
            "SELECT menu_name, path, permission_code FROM sys_menu WHERE id = 15"
        ).fetchone()
        assert enum_menu == ("枚举管理", "/system/enum", "system:enum:list")
        enum_permissions = {
            row[0]
            for row in conn.execute(
                "SELECT permission_code FROM sys_menu WHERE id IN (151, 152, 153, 154)"
            ).fetchall()
        }
        assert enum_permissions == {
            "system:enum:view",
            "system:enum:add",
            "system:enum:edit",
            "system:enum:delete",
        }
        assert conn.execute("SELECT COUNT(*) FROM sys_menu WHERE id IN (132, 133, 134)").fetchone()[0] == 0
    finally:
        conn.close()


if __name__ == "__main__":
    test_sqlite_init_db()
    print("sqlite init contract passed")
