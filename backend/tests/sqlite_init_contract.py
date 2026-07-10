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
    finally:
        conn.close()


if __name__ == "__main__":
    test_sqlite_init_db()
    print("sqlite init contract passed")
