"""既有数据库升级必须在 ORM 查询前补齐新增列。"""
import os
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "pms-test-legacy-schema-upgrade.db"
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = str(DB_PATH)


def test_existing_role_table_gets_product_lines_before_role_query():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE sys_role (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name NVARCHAR(64) NOT NULL,
                role_code NVARCHAR(64) NOT NULL UNIQUE,
                data_scope INTEGER DEFAULT 1,
                status INTEGER DEFAULT 1,
                remark NVARCHAR(256),
                created_at DATETIME,
                updated_at DATETIME
            )
        """)
        conn.execute(
            "INSERT INTO sys_role (role_name, role_code, data_scope, status) VALUES (?, ?, ?, ?)",
            ("超级管理员", "admin", 4, 1),
        )
        conn.commit()
    finally:
        conn.close()

    from app.models.init_db import init_db

    init_db()

    conn = sqlite3.connect(DB_PATH)
    try:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(sys_role)").fetchall()
        }
        assert "product_lines" in columns
        role = conn.execute(
            "SELECT role_code, product_lines FROM sys_role WHERE role_code = 'admin'"
        ).fetchone()
        assert role == ("admin", None)
    finally:
        conn.close()


if __name__ == "__main__":
    test_existing_role_table_gets_product_lines_before_role_query()
    print("legacy schema upgrade contract passed")
