"""Role landing preferences never grant access; current permissions remain authoritative."""
from fastapi import HTTPException
from sqlalchemy import inspect, text
from app.models.rbac import SysMenu, SysRole, SysRoleMenu, SysUserRole


PAGE_PERMISSIONS = {
    "/dashboard": "dashboard:view",
    "/project/archive": "project:archive:view",
    "/project/list": "project:list:view",
    "/system/user": "system:user:view",
    "/system/role": "system:role:view",
    "/system/dict": "system:dict:view",
    "/system/enum": "system:enum:view",
    "/system/operation-log": "system:operation-log:view",
    "/system/field-policy": "system:field-policy:view",
    "/system/parameter": "system:parameter:view",
    "/reports/purchase-progress": "report:purchase:view",
    "/reports/inventory": "report:inventory:view",
}


def _available_pages(menus, ids, permissions=None):
    selected = set(ids)
    codes = {m.permission_code for m in menus.values() if m.id in selected and m.status == 1}
    if permissions is not None:
        codes &= set(permissions)

    def visible_chain(menu):
        seen = set()
        while menu:
            if menu.id in seen or menu.status != 1 or menu.visible != 1 or menu.id not in selected:
                return False
            seen.add(menu.id)
            if not menu.parent_id:
                return True
            menu = menus.get(menu.parent_id)
        return False

    return {m.id: m for m in menus.values() if m.menu_type == "C" and m.path in PAGE_PERMISSIONS
            and PAGE_PERMISSIONS.get(m.path) in codes and visible_chain(m)}


def validate_role_home(db, home_menu_id, menu_ids):
    if home_menu_id is None:
        return
    menus = {m.id: m for m in db.query(SysMenu).all()}
    if home_menu_id not in _available_pages(menus, menu_ids):
        raise HTTPException(status_code=422, detail="登录首页必须是本角色有查看权限的有效页面")


def resolve_home_path(db, roles, permissions):
    roles = sorted((r for r in roles if r.status == 1), key=lambda r: (-(r.home_priority or 0), r.id))
    if not roles:
        return "/403"
    menus = {m.id: m for m in db.query(SysMenu).all()}
    assignments = db.query(SysRoleMenu).filter(SysRoleMenu.role_id.in_([r.id for r in roles])).all()
    for role in roles:
        pages = _available_pages(menus, [a.menu_id for a in assignments if a.role_id == role.id], permissions)
        if role.home_menu_id in pages:
            return pages[role.home_menu_id].path
    pages = _available_pages(menus, [a.menu_id for a in assignments], permissions)

    def tree_order(menu):
        order = []
        while menu:
            order.append((menu.sort or 0, menu.id))
            menu = menus.get(menu.parent_id)
        return tuple(reversed(order))

    return min(pages.values(), key=tree_order).path if pages else "/403"


def resolve_user_home(db, user_id, permissions):
    roles = db.query(SysRole).join(SysUserRole, SysUserRole.role_id == SysRole.id).filter(
        SysUserRole.user_id == user_id, SysRole.status == 1).all()
    return resolve_home_path(db, roles, permissions)


def upgrade_role_home(engine):
    if not inspect(engine).has_table("sys_role"):
        return
    columns = {c["name"] for c in inspect(engine).get_columns("sys_role")}
    with engine.begin() as connection:
        if "home_menu_id" not in columns:
            connection.execute(text("ALTER TABLE sys_role ADD home_menu_id INTEGER NULL"))
        if "home_priority" not in columns:
            connection.execute(text("ALTER TABLE sys_role ADD home_priority INTEGER NOT NULL DEFAULT 0"))
