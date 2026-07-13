#!/usr/bin/env python3
"""服务器本地 RBAC 应急恢复工具。

示例：
  python scripts/recover_role_permissions.py --role-code admin --all
  python scripts/recover_role_permissions.py --role-code admin \
    --permissions system:user:view,system:user:edit,system:role:view,system:role:edit
"""
import argparse
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.models.rbac import SysMenu, SysRole, SysRoleMenu, SysUserRole  # noqa: E402
from app.models.user import SysUser  # noqa: E402
from app.services.operation_log import record_operation_log  # noqa: E402
from app.services.rbac import normalize_role_menu_ids  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="恢复指定 PMS 角色的权限")
    parser.add_argument("--role-code", required=True, help="需要恢复的角色编码，例如 admin")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--all", action="store_true", help="恢复全部有效菜单和按钮权限")
    mode.add_argument("--permissions", help="逗号分隔的权限码")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        role = db.query(SysRole).filter(SysRole.role_code == args.role_code).first()
        if not role:
            print(f"角色不存在：{args.role_code}", file=sys.stderr)
            return 2

        before_status = role.status
        before_ids = [
            menu_id for (menu_id,) in db.query(SysRoleMenu.menu_id).filter(
                SysRoleMenu.role_id == role.id
            ).all()
        ]
        if args.all:
            requested_ids = [
                menu_id for (menu_id,) in db.query(SysMenu.id).filter(SysMenu.status == 1).all()
            ]
        else:
            permission_codes = sorted({
                value.strip() for value in (args.permissions or "").split(",") if value.strip()
            })
            menus = db.query(SysMenu).filter(
                SysMenu.permission_code.in_(permission_codes),
                SysMenu.status == 1,
            ).all()
            found_codes = {menu.permission_code for menu in menus}
            missing = sorted(set(permission_codes) - found_codes)
            if missing:
                print(f"权限码不存在或已禁用：{', '.join(missing)}", file=sys.stderr)
                return 2
            requested_ids = [menu.id for menu in menus]

        normalized_ids = normalize_role_menu_ids(db, sorted(set(before_ids + requested_ids)))
        existing_ids = set(before_ids)
        for menu_id in normalized_ids:
            if menu_id not in existing_ids:
                db.add(SysRoleMenu(role_id=role.id, menu_id=menu_id))
        role.status = 1

        active_user_count = (
            db.query(SysUser)
            .join(SysUserRole, SysUserRole.user_id == SysUser.id)
            .filter(SysUserRole.role_id == role.id, SysUser.status == 1)
            .count()
        )
        record_operation_log(
            db,
            module="系统管理",
            action="permission_recovery",
            entity_type="sys_role",
            entity_id=role.id,
            entity_name=role.role_name,
            summary=f"服务器本地恢复角色权限：{role.role_name}",
            before_data={"menu_ids": sorted(before_ids), "status": before_status},
            after_data={"menu_ids": normalized_ids, "status": 1},
        )
        db.commit()
        print(
            f"恢复完成：角色={role.role_code}，权限节点={len(normalized_ids)}，"
            f"有效关联用户={active_user_count}"
        )
        if active_user_count == 0:
            print("提醒：该角色没有关联有效用户，请在数据库或管理页面完成用户角色分配。")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
