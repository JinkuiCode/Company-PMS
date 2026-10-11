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


def upgrade_database(*, business_export_only: bool = False) -> None:
    validate_runtime_config(settings)
    if business_export_only:
        upgrade_business_export_only()
        check_database_ready(engine)
        return
    mark_database_upgrading(engine)
    init_db()
    mark_database_ready(engine)
    check_database_ready(engine)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-export-only", action="store_true", help="仅从archive-02升级两个业务导出权限，禁止历史初始化")
    upgrade_database(business_export_only=parser.parse_args().business_export_only)
    print("数据库升级完成")
