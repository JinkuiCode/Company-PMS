"""Explicit database upgrade support; never called by production startup."""
import secrets
from sqlalchemy import inspect, text
from app.core.security import verify_password, hash_password
from app.models.parameter import SysParameter
from app.models.rbac import SysRole, SysMenu, SysRoleMenu


def upgrade_user_security(engine):
    columns = {column["name"] for column in inspect(engine).get_columns("sys_user")}
    is_legacy = "credential_version" not in columns
    definitions = {"email": "NVARCHAR(254) NULL", "must_change_password": "BIT NOT NULL DEFAULT 1",
                   "local_login_enabled": "BIT NOT NULL DEFAULT 1", "credential_version": "INT NOT NULL DEFAULT 0"}
    with engine.begin() as connection:
        # sqlite3 legacy transaction mode does not BEGIN for DDL. A physical
        # transaction keeps column creation and credential enrollment atomic.
        if engine.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")
        if inspect(connection).has_table("sys_parameter"):
            parameter_columns = {column["name"] for column in inspect(connection).get_columns("sys_parameter")}
            if "value_text" not in parameter_columns:
                value_type = "NVARCHAR(MAX)" if engine.dialect.name == "mssql" else "TEXT"
                connection.execute(text(f"ALTER TABLE sys_parameter ADD value_text {value_type} NULL"))
        if inspect(connection).has_table("sys_remember_token"):
            remember_columns = {column["name"] for column in inspect(connection).get_columns("sys_remember_token")}
            if "credential_version" not in remember_columns:
                connection.execute(text("ALTER TABLE sys_remember_token ADD credential_version INT NOT NULL DEFAULT 0"))
        for name, definition in definitions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE sys_user ADD {name} {definition}"))
        if is_legacy:
            rows = connection.execute(text("SELECT id, password_hash FROM sys_user")).all()
            for user_id, digest in rows:
                oa_only = verify_password("sso_placeholder", digest)
                connection.execute(text("UPDATE sys_user SET credential_version=1, must_change_password=:must_change, local_login_enabled=:enabled, password_hash=:digest WHERE id=:id"),
                                   {"id": user_id, "must_change": int(not oa_only), "enabled": int(not oa_only),
                                    "digest": hash_password(secrets.token_hex(32)) if oa_only else digest})
            if inspect(connection).has_table("sys_remember_token"):
                connection.execute(text("DELETE FROM sys_remember_token"))


def initialize_user_security(db, *, grant_existing_admin=True):
    nodes = [
        dict(id=18, parent_id=1, menu_name="参数设置", menu_type="C", path="/system/parameter", icon="Setting", sort=7, permission_code="system:parameter:list"),
        dict(id=181, parent_id=18, menu_name="查看", menu_type="B", permission_code="system:parameter:view", sort=1),
        dict(id=182, parent_id=18, menu_name="编辑", menu_type="B", permission_code="system:parameter:edit", sort=2),
        dict(id=115, parent_id=11, menu_name="重置密码", menu_type="B", permission_code="system:user:reset-password", sort=5),
    ]
    admin = db.query(SysRole).filter_by(role_code="admin").first()
    for node in nodes:
        if db.get(SysMenu, node["id"]) is None:
            db.add(SysMenu(**node))
            if grant_existing_admin and admin and not db.query(SysRoleMenu).filter_by(role_id=admin.id, menu_id=node["id"]).first():
                db.add(SysRoleMenu(role_id=admin.id, menu_id=node["id"]))
    if db.get(SysParameter, "user.initial_password") is None:
        db.add(SysParameter(code="user.initial_password", version=0))
    db.commit()
