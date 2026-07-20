"""默认角色模板。

模板只用于角色首次创建，运行时仍完全由数据库 RBAC 结果授权。
"""

ROLE_TEMPLATES = {
    "admin": {
        "role_name": "系统管理员",
        "data_scope": 4,
        "remark": "默认拥有全部权限，可在角色管理中调整",
        "permissions": "*",
    },
    "business_admin": {
        "role_name": "业务管理员",
        "data_scope": 4,
        "remark": "负责项目业务、枚举、字段规则和操作日志",
        "permissions": {
            "dashboard:view",
            "project:list",
            "project:list:view",
            "project:list:add",
            "project:list:edit",
            "project:list:delete",
            "project:archive:list",
            "project:archive:view",
            "project:archive:add",
            "project:archive:edit",
            "project:archive:delete",
            "project:archive:sync",
            "project:archive:toggle",
            "system:dict:list",
            "system:dict:view",
            "system:enum:list",
            "system:enum:view",
            "system:enum:add",
            "system:enum:edit",
            "system:enum:delete",
            "system:operation-log:list",
            "system:operation-log:view",
            "system:field-policy:list",
            "system:field-policy:view",
            "system:field-policy:edit",
        },
    },
    "operator": {
        "role_name": "操作员",
        "data_scope": 3,
        "remark": "维护本部门及子部门项目，不含删除、同步和系统配置权限",
        "permissions": {
            "dashboard:view",
            "project:list",
            "project:list:view",
            "project:list:add",
            "project:list:edit",
            "project:archive:list",
            "project:archive:view",
            "project:archive:add",
            "project:archive:edit",
        },
    },
}


def permission_ids_for_template(db, role_code: str) -> set[int]:
    """解析模板权限，并补齐目录祖先节点。"""
    from app.models.rbac import SysMenu

    template = ROLE_TEMPLATES[role_code]
    permissions = template["permissions"]
    menus = db.query(SysMenu).filter(SysMenu.status == 1).all()
    if permissions == "*":
        return {menu.id for menu in menus}

    by_id = {menu.id: menu for menu in menus}
    selected = {menu.id for menu in menus if menu.permission_code in permissions}
    pending = list(selected)
    while pending:
        menu = by_id.get(pending.pop())
        if menu and menu.parent_id and menu.parent_id not in selected:
            selected.add(menu.parent_id)
            pending.append(menu.parent_id)
    return selected
