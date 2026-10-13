#!/usr/bin/env python3
"""Run the existing idempotent database setup as a separate release step."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings, validate_runtime_config
from app.core.database import engine
from app.models.init_db import init_db
from app.services.database_revision import (
    CURRENT_DATABASE_REVISION,
    check_database_ready,
    mark_database_ready,
    mark_database_upgrading,
)


def upgrade_business_export_only() -> None:
    from sqlalchemy import select
    from app.models.database_revision import PmsDatabaseRevision
    from app.models.rbac import SysMenu, SysRole, SysRoleMenu

    target = "2026-10-11-business-export-01"
    if CURRENT_DATABASE_REVISION != target:
        raise RuntimeError("本次限定升级模式不适用于当前程序版本")
    revisions = PmsDatabaseRevision.__table__
    menus, roles, grants = SysMenu.__table__, SysRole.__table__, SysRoleMenu.__table__
    with engine.begin() as connection:
        revision_query = select(revisions.c.revision).where(revisions.c.id == 1).with_hint(
            revisions, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql"
        )
        revision = connection.execute(revision_query).scalar_one_or_none()
        if revision not in ("2026-10-09-archive-02", target):
            raise RuntimeError("本次限定升级需要 archive-02 数据库版本")
        admin = connection.execute(select(roles.c.id, roles.c.status).where(roles.c.role_code == "admin")).one_or_none()
        if admin is None:
            raise RuntimeError("管理员角色缺失，本次升级不会自动重建角色")
        for parent_id, path, permission in (
            (22, "/project/archive", "project:archive:list"),
            (21, "/project/list", "project:list"),
        ):
            parent = connection.execute(select(menus.c.menu_type, menus.c.path, menus.c.permission_code).where(menus.c.id == parent_id)).one_or_none()
            if parent is None or tuple(parent) != ("C", path, permission):
                raise RuntimeError("业务菜单结构不匹配，本次升级不会自动修正")
        for parent_id, code in ((22, "project:archive:export"), (21, "project:list:export")):
            existing = connection.execute(select(menus.c.id, menus.c.parent_id, menus.c.menu_type, menus.c.path).where(menus.c.permission_code == code)).all()
            if len(existing) > 1 or (existing and tuple(existing[0])[1:] != (parent_id, "B", None)):
                raise RuntimeError("业务导出菜单结构冲突，本次升级已回滚")
            if existing:
                continue
            if revision == target:
                raise RuntimeError("数据库版本与业务导出权限不一致")
            inserted = connection.execute(menus.insert().values(
                parent_id=parent_id, menu_name="导出", menu_type="B", permission_code=code, sort=9
            ))
            if admin.status == 1:
                connection.execute(grants.insert().values(role_id=admin.id, menu_id=inserted.inserted_primary_key[0]))
        if revision != target:
            connection.execute(revisions.update().where(revisions.c.id == 1).values(revision=target))


PARAMETER_SECRET_PREVIOUS = "2026-10-11-business-export-01"
PARAMETER_SECRET_REVISION = "2026-10-12-parameter-secret-01"


def upgrade_parameter_secret_storage(connection, *, allow_add=True) -> None:
    from sqlalchemy import String, inspect
    inspector = inspect(connection)
    columns = {column["name"]: column for column in inspector.get_columns("sys_parameter")}
    column = columns.get("secret_ciphertext")
    if column is None:
        if not allow_add:
            raise RuntimeError("参数密文列缺失，数据库版本与结构不一致")
        connection.exec_driver_sql("ALTER TABLE sys_parameter ADD secret_ciphertext NVARCHAR(1024) NULL")
    elif not isinstance(column["type"], String) or not column["nullable"] or (
        column["type"].length is not None and column["type"].length < 1024
    ):
        raise RuntimeError("参数密文列结构不兼容，升级已停止")


def upgrade_parameter_secret_only(*, rollback=False) -> None:
    from sqlalchemy import select
    from app.models.database_revision import PmsDatabaseRevision

    if CURRENT_DATABASE_REVISION != PARAMETER_SECRET_REVISION:
        raise RuntimeError("本次限定升级模式不适用于当前程序版本")
    revisions = PmsDatabaseRevision.__table__
    with engine.begin() as connection:
        # SQLite's legacy driver otherwise auto-commits DDL before the first write.
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN")
        revision = connection.execute(
            select(revisions.c.revision).where(revisions.c.id == 1).with_hint(
                revisions, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql"
            )
        ).scalar_one_or_none()
        if revision not in (PARAMETER_SECRET_PREVIOUS, PARAMETER_SECRET_REVISION):
            raise RuntimeError("初始密码限定升级需要 business-export-01 数据库版本")
        upgrade_parameter_secret_storage(connection, allow_add=not rollback and revision == PARAMETER_SECRET_PREVIOUS)
        target = PARAMETER_SECRET_PREVIOUS if rollback else PARAMETER_SECRET_REVISION
        if revision != target:
            connection.execute(revisions.update().where(revisions.c.id == 1).values(revision=target))


def upgrade_database(*, business_export_only: bool = False, parameter_secret_only: bool = False,
                     parameter_secret_rollback: bool = False, feedback_only: bool = False) -> None:
    if sum((business_export_only, parameter_secret_only, parameter_secret_rollback, feedback_only)) > 1:
        raise RuntimeError("限定升级与回滚模式不能同时使用")
    validate_runtime_config(settings)
    if feedback_only:
        from app.services.feedback_migration import upgrade_feedback
        upgrade_feedback(engine)
        check_database_ready(engine)
        return
    if parameter_secret_only or parameter_secret_rollback:
        upgrade_parameter_secret_only(rollback=parameter_secret_rollback)
        if not parameter_secret_rollback:
            check_database_ready(engine)
        return
    if business_export_only:
        upgrade_business_export_only()
        check_database_ready(engine)
        return
    mark_database_upgrading(engine)
    from sqlalchemy import inspect
    with engine.begin() as connection:
        if inspect(connection).has_table("sys_parameter"):
            upgrade_parameter_secret_storage(connection)
    init_db()
    with engine.begin() as connection:
        upgrade_parameter_secret_storage(connection, allow_add=False)
    mark_database_ready(engine)
    check_database_ready(engine)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--feedback-only", action="store_true", help="仅新增问题提报表、菜单与一次性模板权限")
    modes.add_argument("--business-export-only", action="store_true", help="仅从archive-02升级两个业务导出权限，禁止历史初始化")
    modes.add_argument("--parameter-secret-only", action="store_true", help="仅从business-export-01新增参数认证密文列，不修改权限或历史数据")
    modes.add_argument("--parameter-secret-rollback", action="store_true", help="恢复business-export-01版本，保留新增列及原哈希，配合旧程序回滚")
    args = parser.parse_args()
    upgrade_database(business_export_only=args.business_export_only, parameter_secret_only=args.parameter_secret_only,
                     parameter_secret_rollback=args.parameter_secret_rollback, feedback_only=args.feedback_only)
    print("数据库升级完成")
