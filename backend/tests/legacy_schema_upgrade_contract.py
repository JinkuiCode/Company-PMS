"""既有数据库必须在 ORM 查询前完成项目档案语义化升级。"""
import os
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "pms-test-legacy-schema-upgrade.db"
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = str(DB_PATH)


def create_legacy_schema() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript("""
            CREATE TABLE sys_role (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name NVARCHAR(64) NOT NULL,
                role_code NVARCHAR(64) NOT NULL UNIQUE,
                data_scope INTEGER DEFAULT 1,
                product_lines NVARCHAR(256),
                status INTEGER DEFAULT 1,
                remark NVARCHAR(256),
                created_at DATETIME,
                updated_at DATETIME
            );
            CREATE TABLE sys_dict (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dict_code NVARCHAR(64) NOT NULL UNIQUE,
                dict_name NVARCHAR(64) NOT NULL,
                table_name NVARCHAR(64),
                field_name NVARCHAR(64),
                page_name NVARCHAR(64),
                description NVARCHAR(256),
                sort INTEGER DEFAULT 0,
                status INTEGER DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME
            );
            CREATE TABLE sys_dict_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dict_id INTEGER NOT NULL,
                item_value NVARCHAR(64) NOT NULL,
                item_label NVARCHAR(64) NOT NULL,
                field_type NVARCHAR(32),
                description NVARCHAR(256),
                sort INTEGER DEFAULT 0,
                status INTEGER DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                UNIQUE(dict_id, item_value)
            );
            CREATE TABLE pms_project_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_code NVARCHAR(32) NOT NULL UNIQUE,
                project_name NVARCHAR(128) NOT NULL,
                status INTEGER DEFAULT 1,
                manager_id INTEGER,
                product_type NVARCHAR(64),
                product_line NVARCHAR(32),
                plan_start_date DATETIME,
                plan_end_date DATETIME,
                created_by INTEGER,
                updated_by INTEGER,
                erp_synced INTEGER DEFAULT 0,
                erp_sync_time DATETIME,
                erp_sync_by INTEGER,
                erp_sync_status NVARCHAR(32),
                erp_error_msg NVARCHAR(512),
                created_at DATETIME,
                updated_at DATETIME
            );
            CREATE TABLE pms_project (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                archive_id INTEGER,
                project_code NVARCHAR(32) NOT NULL UNIQUE,
                project_name NVARCHAR(128) NOT NULL,
                dept_id INTEGER NOT NULL,
                pm_id INTEGER NOT NULL,
                product_line NVARCHAR(32),
                status INTEGER DEFAULT 1,
                start_date DATETIME,
                end_date DATETIME,
                budget DECIMAL(12, 2),
                design_progress INTEGER,
                order_progress INTEGER,
                kit_progress INTEGER,
                frame_progress INTEGER,
                dryer_progress INTEGER,
                assembly_progress INTEGER,
                test_progress INTEGER,
                description NVARCHAR(2048),
                created_at DATETIME,
                updated_at DATETIME
            );
            CREATE TABLE pms_project_sheet_detail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL UNIQUE,
                detail_data TEXT,
                created_by INTEGER,
                updated_by INTEGER,
                created_at DATETIME,
                updated_at DATETIME
            );
        """)
        conn.execute(
            "INSERT INTO sys_role (role_name, role_code, data_scope, product_lines, status) VALUES (?, ?, ?, ?, ?)",
            ("超级管理员", "admin", 4, "Bench,Single", 1),
        )
        conn.execute("INSERT INTO sys_dict (id, dict_code, dict_name, sort, status) VALUES (1, 'product_line', '产品线', 1, 1)")
        conn.execute("INSERT INTO sys_dict (id, dict_code, dict_name, sort, status) VALUES (2, 'product_type', '产品类型', 2, 1)")
        for item_id, value, sort in ((1, "Bench", 1), (2, "光伏", 2), (3, "Single", 3), (4, "HOTSPM", 4)):
            conn.execute(
                "INSERT INTO sys_dict_item (id, dict_id, item_value, item_label, sort, status) VALUES (?, 1, ?, ?, ?, 1)",
                (item_id, value, value, sort),
            )
        for item_id, value, label, sort in ((11, "20", "链式", 1), (12, "21", "槽式", 2)):
            conn.execute(
                "INSERT INTO sys_dict_item (id, dict_id, item_value, item_label, sort, status) VALUES (?, 2, ?, ?, ?, 1)",
                (item_id, value, label, sort),
            )
        conn.execute(
            "INSERT INTO pms_project_archive (id, project_code, project_name, status, product_line, product_type) VALUES (1, ' ARCH-001 ', ' 旧档案 ', 1, 'Bench', '20')"
        )
        conn.execute(
            "INSERT INTO pms_project (id, archive_id, project_code, project_name, dept_id, pm_id, product_line, status) VALUES (1, 1, ' ARCH-OLD ', '历史项目别名', 1, 1, 'Bench', 1)"
        )
        conn.execute(
            "INSERT INTO pms_project_sheet_detail (project_id, detail_data) VALUES (?, ?)",
            (1, '{"customer":"旧客户","equipment_series":"20","serial_no":" OLD-SN-001 ","configuration":"保留配置"}'),
        )
        conn.commit()
    finally:
        conn.close()

def test_legacy_business_fields_are_upgraded_before_orm_queries():
    create_legacy_schema()

    from app.models.init_db import init_db

    init_db()

    conn = sqlite3.connect(DB_PATH)
    try:
        role_columns = {row[1] for row in conn.execute("PRAGMA table_info(sys_role)")}
        archive_columns = {row[1] for row in conn.execute("PRAGMA table_info(pms_project_archive)")}
        project_columns = {row[1] for row in conn.execute("PRAGMA table_info(pms_project)")}
        dict_columns = {row[1] for row in conn.execute("PRAGMA table_info(sys_dict)")}
        assert "product_category_ids" in role_columns
        assert {
            "customer",
            "product_category",
            "equipment_series",
            "serial_no",
            "project_code_key",
            "project_name_key",
            "serial_no_key",
        }.issubset(archive_columns)
        assert "product_category" in project_columns
        assert "next_value" in dict_columns

        archive = conn.execute(
            "SELECT project_code, project_name, customer, product_category, equipment_series, serial_no, project_code_key, project_name_key "
            "FROM pms_project_archive WHERE id = 1"
        ).fetchone()
        assert archive == ("ARCH-001", "旧档案", "旧客户", 1, 1, "OLD-SN-001", "arch-001", "旧档案")
        project = conn.execute(
            "SELECT project_code, project_name, product_category FROM pms_project WHERE id = 1"
        ).fetchone()
        assert project == ("ARCH-001", "旧档案", 1)
        assert conn.execute("SELECT product_category_ids FROM sys_role WHERE role_code = 'admin'").fetchone()[0] == "1,3"

        enum_items = conn.execute(
            "SELECT d.dict_code, i.item_value, i.item_label FROM sys_dict d "
            "JOIN sys_dict_item i ON i.dict_id = d.id "
            "WHERE d.dict_code IN ('product_category', 'equipment_series') "
            "ORDER BY d.dict_code, CAST(i.item_value AS INTEGER)"
        ).fetchall()
        assert ("product_category", "1", "Bench") in enum_items
        assert ("product_category", "4", "HOTSPM") in enum_items
        assert ("equipment_series", "1", "链式") in enum_items

        detail_data = conn.execute(
            "SELECT detail_data FROM pms_project_sheet_detail WHERE project_id = 1"
        ).fetchone()[0]
        assert "保留配置" in detail_data
        assert "customer" not in detail_data
        assert "equipment_series" not in detail_data
        assert "serial_no" not in detail_data

        unique_indexes = {
            row[1]
            for row in conn.execute("PRAGMA index_list(pms_project_archive)").fetchall()
            if row[2] == 1
        }
        assert "ux_pms_project_archive_project_code_key" in unique_indexes
        assert "ux_pms_project_archive_project_name_key" in unique_indexes
        assert "ux_pms_project_archive_serial_no_key" in unique_indexes
    finally:
        conn.close()

    conn = sqlite3.connect(DB_PATH)
    try:
        category_id = conn.execute(
            "SELECT id FROM sys_dict WHERE dict_code = 'product_category'"
        ).fetchone()[0]
        conn.execute(
            "DELETE FROM sys_dict_item WHERE dict_id = ? AND item_value = '4'",
            (category_id,),
        )
        conn.execute(
            "UPDATE sys_dict SET next_value = 100 WHERE dict_code = 'product_category'"
        )
        conn.commit()
    finally:
        conn.close()

    init_db()

    conn = sqlite3.connect(DB_PATH)
    try:
        next_value = conn.execute(
            "SELECT next_value FROM sys_dict WHERE dict_code = 'product_category'"
        ).fetchone()[0]
        assert next_value == 100, "重复执行旧库迁移不得回收已经使用过的枚举流水"
        restored = conn.execute(
            "SELECT COUNT(*) FROM sys_dict_item i JOIN sys_dict d ON d.id = i.dict_id "
            "WHERE d.dict_code = 'product_category' AND i.item_value = '4'"
        ).fetchone()[0]
        assert restored == 0, "重复执行旧库迁移不得恢复管理员已经删除的可配置枚举值"
    finally:
        conn.close()


if __name__ == "__main__":
    test_legacy_business_fields_are_upgraded_before_orm_queries()
    print("legacy schema upgrade contract passed")
