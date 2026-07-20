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
        assert "sys_business_field_policy" in tables
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
            "product_category",
            "equipment_series",
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
        field_policy_menu = conn.execute(
            "SELECT menu_name, path, permission_code FROM sys_menu WHERE id = 17"
        ).fetchone()
        assert field_policy_menu == ("字段规则", "/system/field-policy", "system:field-policy:list")
        archive_toggle_menu = conn.execute(
            "SELECT parent_id, menu_name, permission_code, sort FROM sys_menu WHERE id = 226"
        ).fetchone()
        assert archive_toggle_menu == (22, "启用/禁用", "project:archive:toggle", 6)
        role_templates = {
            row[0]: (row[1], row[2])
            for row in conn.execute(
                "SELECT role_code, role_name, data_scope FROM sys_role "
                "WHERE role_code IN ('admin', 'business_admin', 'operator')"
            ).fetchall()
        }
        assert role_templates == {
            "admin": ("系统管理员", 4),
            "business_admin": ("业务管理员", 4),
            "operator": ("操作员", 3),
        }
        template_permissions = {
            role_code: {
                row[0]
                for row in conn.execute(
                    "SELECT m.permission_code FROM sys_role_menu rm "
                    "JOIN sys_role r ON r.id = rm.role_id "
                    "JOIN sys_menu m ON m.id = rm.menu_id "
                    "WHERE r.role_code = ? AND m.permission_code IS NOT NULL",
                    (role_code,),
                ).fetchall()
            }
            for role_code in ("admin", "business_admin", "operator")
        }
        assert "system:field-policy:edit" in template_permissions["admin"]
        assert {
            "project:archive:sync",
            "project:archive:toggle",
            "system:enum:edit",
            "system:operation-log:view",
            "system:field-policy:edit",
        }.issubset(template_permissions["business_admin"])
        assert {
            "project:list:view",
            "project:list:add",
            "project:list:edit",
            "project:archive:view",
            "project:archive:add",
            "project:archive:edit",
        }.issubset(template_permissions["operator"])
        assert not {
            "project:list:delete",
            "project:archive:delete",
            "project:archive:sync",
            "project:archive:toggle",
            "system:operation-log:view",
            "system:field-policy:edit",
        }.intersection(template_permissions["operator"])
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

        conn.execute(
            "DELETE FROM sys_role_menu WHERE menu_id IN (172, 226) AND role_id IN "
            "(SELECT id FROM sys_role WHERE role_code IN ('admin', 'business_admin'))"
        )
        conn.commit()
        init_db()
        assert conn.execute(
            "SELECT COUNT(*) FROM sys_role_menu rm JOIN sys_role r ON r.id = rm.role_id "
            "WHERE rm.menu_id IN (172, 226) AND r.role_code IN ('admin', 'business_admin')"
        ).fetchone()[0] == 0
    finally:
        conn.close()


if __name__ == "__main__":
    test_sqlite_init_db()
    print("sqlite init contract passed")
