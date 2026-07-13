"""RBAC CRUD 业务逻辑：用户、角色、菜单、部门"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, Request

from app.core.security import hash_password
from app.models.user import SysUser, RememberToken
from app.models.rbac import SysRole, SysMenu, SysDept, SysUserRole, SysRoleMenu
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.rbac import (
    RoleCreate, RoleUpdate, RoleResponse,
    MenuCreate, MenuUpdate, MenuResponse,
    DeptCreate, DeptUpdate, DeptResponse,
)
from app.services.operation_log import record_operation_log, serialize_model
from app.services.enum_registry import validate_enum_value


def _split_product_lines(raw_value: str | None) -> list[str]:
    return [value.strip() for value in (raw_value or "").split(",") if value.strip()]


RECOVERY_PERMISSIONS = {
    "system:user:view",
    "system:user:edit",
    "system:role:view",
    "system:role:edit",
}


def normalize_role_menu_ids(db: Session, menu_ids: list[int]) -> list[int]:
    """校验权限节点，并自动补齐动作对应的查看权限和祖先节点。"""
    if len(menu_ids) != len(set(menu_ids)):
        raise HTTPException(status_code=400, detail="权限节点不能重复")
    if not menu_ids:
        return []

    menus = db.query(SysMenu).filter(SysMenu.id.in_(menu_ids)).all()
    if len(menus) != len(menu_ids):
        raise HTTPException(status_code=400, detail="包含不存在的权限节点")
    if any(menu.status != 1 for menu in menus):
        raise HTTPException(status_code=400, detail="不能分配已禁用的权限节点")

    selected = {menu.id for menu in menus}
    for menu in list(menus):
        if menu.menu_type != "C":
            continue
        view_menu = next((
            child for child in db.query(SysMenu).filter(
                SysMenu.parent_id == menu.id,
                SysMenu.menu_type == "B",
                SysMenu.status == 1,
            ).all()
            if child.permission_code and child.permission_code.endswith(":view")
        ), None)
        if view_menu:
            selected.add(view_menu.id)

    for menu in list(menus):
        if menu.menu_type != "B" or not menu.permission_code or menu.permission_code.endswith(":view"):
            continue
        view_menu = db.query(SysMenu).filter(
            SysMenu.parent_id == menu.parent_id,
            SysMenu.menu_type == "B",
            SysMenu.permission_code.like("%:view"),
            SysMenu.status == 1,
        ).first()
        if not view_menu:
            raise HTTPException(status_code=400, detail=f"动作权限缺少查看权限：{menu.permission_code}")
        selected.add(view_menu.id)

    menu_map = {menu.id: menu for menu in db.query(SysMenu).all()}
    pending = list(selected)
    while pending:
        menu = menu_map.get(pending.pop())
        if menu and menu.parent_id and menu.parent_id not in selected:
            parent = menu_map.get(menu.parent_id)
            if not parent or parent.status != 1:
                raise HTTPException(status_code=400, detail="权限节点的上级菜单不存在或已禁用")
            selected.add(parent.id)
            pending.append(parent.id)
    return sorted(selected)


def ensure_recovery_administrator_exists(db: Session) -> None:
    """防止通过角色配置把所有权限管理员同时锁在系统外。"""
    active_users = db.query(SysUser).filter(SysUser.status == 1).all()
    for user in active_users:
        role_ids = [role_id for (role_id,) in db.query(SysUserRole.role_id).join(
            SysRole, SysRole.id == SysUserRole.role_id
        ).filter(
            SysUserRole.user_id == user.id,
            SysRole.status == 1,
        ).all()]
        if not role_ids:
            continue
        permissions = {
            code for (code,) in db.query(SysMenu.permission_code).join(
                SysRoleMenu, SysRoleMenu.menu_id == SysMenu.id
            ).filter(
                SysRoleMenu.role_id.in_(role_ids),
                SysMenu.status == 1,
                SysMenu.permission_code.isnot(None),
            ).all()
            if code
        }
        if RECOVERY_PERMISSIONS.issubset(permissions):
            return
    raise HTTPException(status_code=409, detail="至少保留一名可管理用户和角色权限的有效管理员")


# ==================== 用户管理 ====================
def get_user_list(db: Session, page: int = 1, page_size: int = 15, dept_id: int | None = None):
    """分页查询用户列表，附带角色信息，支持按部门过滤（含子部门）"""
    query = db.query(SysUser)

    # 按部门过滤（含所有子部门）
    if dept_id is not None:
        dept_ids = _get_all_child_dept_ids(db, dept_id)
        dept_ids.append(dept_id)
        query = query.filter(SysUser.dept_id.in_(dept_ids))

    total = query.count()
    users = query.order_by(SysUser.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for u in users:
        role_ids = [ur.role_id for ur in db.query(SysUserRole).filter(SysUserRole.user_id == u.id).all()]
        role_names = [
            r.role_name for r in db.query(SysRole).filter(SysRole.id.in_(role_ids)).all() if role_ids
        ]
        items.append(UserResponse(
            id=u.id, username=u.username, real_name=u.real_name,
            dept_id=u.dept_id, mobile=u.mobile, status=u.status,
            role_ids=role_ids, role_names=role_names,
            created_at=u.created_at, updated_at=u.updated_at,
        ))
    return {"total": total, "items": items}


def get_user_options(db: Session) -> list[dict]:
    """为业务表单提供最小化的有效用户选项。"""
    users = db.query(SysUser).filter(SysUser.status == 1).order_by(SysUser.real_name, SysUser.id).all()
    return [
        {"id": user.id, "real_name": user.real_name, "dept_id": user.dept_id}
        for user in users
    ]


def create_user(db: Session, data: UserCreate, operator_id: int | None = None, request: Request | None = None):
    """创建用户，可同时分配角色"""
    if db.query(SysUser).filter(SysUser.username == data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = SysUser(
        username=data.username,
        real_name=data.real_name,
        password_hash=hash_password(data.password),
        dept_id=data.dept_id,
        mobile=data.mobile,
        status=data.status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 分配角色
    for role_id in data.role_ids:
        db.add(SysUserRole(user_id=user.id, role_id=role_id))
    record_operation_log(
        db,
        module="系统管理",
        action="create",
        entity_type="sys_user",
        entity_id=user.id,
        entity_name=user.real_name,
        operator_id=operator_id,
        request=request,
        summary=f"创建用户：{user.real_name}",
        after_data=serialize_model(user, extra={"role_ids": data.role_ids}),
    )
    db.commit()
    return {"msg": "创建成功", "id": user.id}


def update_user(db: Session, user_id: int, data: UserUpdate, operator_id: int | None = None, request: Request | None = None):
    """更新用户，可重新分配角色。密码变更或账号禁用时清除所有免密令牌"""
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    should_invalidate = False
    before_role_ids = [ur.role_id for ur in db.query(SysUserRole).filter(SysUserRole.user_id == user_id).all()]
    before = serialize_model(user, extra={"role_ids": before_role_ids})

    update_data = data.model_dump(exclude_unset=True, exclude={"role_ids", "password"})

    # 密码变更：哈希后写入，并标记失效免密令牌
    if data.password is not None:
        user.password_hash = hash_password(data.password)
        should_invalidate = True

    # 账号禁用：标记失效免密令牌
    if data.status is not None:
        if data.status == 0 and user.status == 1:
            should_invalidate = True

    for key, val in update_data.items():
        setattr(user, key, val)

    if should_invalidate:
        db.query(RememberToken).filter(RememberToken.user_id == user_id).delete()

    # 重新分配角色
    if data.role_ids is not None:
        db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
        for role_id in data.role_ids:
            db.add(SysUserRole(user_id=user_id, role_id=role_id))

    db.flush()
    ensure_recovery_administrator_exists(db)

    after_role_ids = data.role_ids if data.role_ids is not None else before_role_ids
    record_operation_log(
        db,
        module="系统管理",
        action="update",
        entity_type="sys_user",
        entity_id=user.id,
        entity_name=user.real_name,
        operator_id=operator_id,
        request=request,
        summary=f"更新用户：{user.real_name}",
        before_data=before,
        after_data=serialize_model(user, extra={"role_ids": after_role_ids}),
    )
    db.commit()
    return {"msg": "更新成功"}


def delete_user(db: Session, user_id: int, operator_id: int | None = None, request: Request | None = None):
    """删除用户及角色关联"""
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    role_ids = [ur.role_id for ur in db.query(SysUserRole).filter(SysUserRole.user_id == user_id).all()]
    before = serialize_model(user, extra={"role_ids": role_ids})
    db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
    db.delete(user)
    db.flush()
    ensure_recovery_administrator_exists(db)
    record_operation_log(
        db,
        module="系统管理",
        action="delete",
        entity_type="sys_user",
        entity_id=user_id,
        entity_name=user.real_name,
        operator_id=operator_id,
        request=request,
        summary=f"删除用户：{user.real_name}",
        before_data=before,
    )
    db.commit()
    return {"msg": "删除成功"}


# ==================== 角色管理 ====================
def get_role_list(db: Session):
    """查询所有角色"""
    roles = db.query(SysRole).order_by(SysRole.id).all()
    return [RoleResponse.model_validate(r) for r in roles]


def get_role_options(db: Session) -> list[dict]:
    roles = db.query(SysRole).filter(SysRole.status == 1).order_by(SysRole.id).all()
    return [{"id": role.id, "role_name": role.role_name, "role_code": role.role_code} for role in roles]


def create_role(db: Session, data: RoleCreate, operator_id: int | None = None, request: Request | None = None):
    """创建角色，可同时分配菜单权限"""
    if db.query(SysRole).filter(SysRole.role_code == data.role_code).first():
        raise HTTPException(status_code=400, detail="角色编码已存在")
    normalized_menu_ids = normalize_role_menu_ids(db, data.menu_ids)
    for product_line in _split_product_lines(data.product_lines):
        validate_enum_value(db, "product_line", product_line)
    try:
        role_data = data.model_dump(exclude={"menu_ids"})
        role = SysRole(**role_data)
        db.add(role)
        db.flush()
        for menu_id in normalized_menu_ids:
            db.add(SysRoleMenu(role_id=role.id, menu_id=menu_id))
        db.flush()
        ensure_recovery_administrator_exists(db)
        record_operation_log(
            db,
            module="系统管理",
            action="create",
            entity_type="sys_role",
            entity_id=role.id,
            entity_name=role.role_name,
            operator_id=operator_id,
            request=request,
            summary=f"创建角色：{role.role_name}",
            after_data=serialize_model(role, extra={"menu_ids": normalized_menu_ids}),
        )
        db.commit()
        return {"msg": "创建成功", "id": role.id}
    except Exception:
        db.rollback()
        raise


def update_role(db: Session, role_id: int, data: RoleUpdate, operator_id: int | None = None, request: Request | None = None):
    """更新角色，可同时分配菜单权限"""
    role = db.query(SysRole).filter(SysRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    before_menu_ids = get_role_menu_ids(db, role_id)
    before = serialize_model(role, extra={"menu_ids": before_menu_ids})
    normalized_menu_ids = normalize_role_menu_ids(db, data.menu_ids) if data.menu_ids is not None else before_menu_ids
    try:
        update_data = data.model_dump(exclude_unset=True, exclude={"menu_ids"})
        if "product_lines" in update_data:
            current_lines = _split_product_lines(role.product_lines)
            for product_line in _split_product_lines(update_data["product_lines"]):
                validate_enum_value(
                    db,
                    "product_line",
                    product_line,
                    current_value=product_line if product_line in current_lines else None,
                )
        for key, val in update_data.items():
            setattr(role, key, val)

        if data.menu_ids is not None:
            db.query(SysRoleMenu).filter(SysRoleMenu.role_id == role_id).delete()
            for menu_id in normalized_menu_ids:
                db.add(SysRoleMenu(role_id=role_id, menu_id=menu_id))

        db.flush()
        ensure_recovery_administrator_exists(db)
        record_operation_log(
            db,
            module="系统管理",
            action="update",
            entity_type="sys_role",
            entity_id=role.id,
            entity_name=role.role_name,
            operator_id=operator_id,
            request=request,
            summary=f"更新角色：{role.role_name}",
            before_data=before,
            after_data=serialize_model(role, extra={"menu_ids": normalized_menu_ids}),
        )
        db.commit()
        return {"msg": "更新成功"}
    except Exception:
        db.rollback()
        raise


def delete_role(db: Session, role_id: int, operator_id: int | None = None, request: Request | None = None):
    """删除角色及关联数据"""
    role = db.query(SysRole).filter(SysRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if db.query(SysUserRole).filter(SysUserRole.role_id == role_id).first():
        raise HTTPException(status_code=409, detail="该角色仍关联用户，请先完成用户角色迁移")
    before = serialize_model(role, extra={"menu_ids": get_role_menu_ids(db, role_id)})
    db.query(SysRoleMenu).filter(SysRoleMenu.role_id == role_id).delete()
    db.delete(role)
    db.flush()
    ensure_recovery_administrator_exists(db)
    record_operation_log(
        db,
        module="系统管理",
        action="delete",
        entity_type="sys_role",
        entity_id=role_id,
        entity_name=role.role_name,
        operator_id=operator_id,
        request=request,
        summary=f"删除角色：{role.role_name}",
        before_data=before,
    )
    db.commit()
    return {"msg": "删除成功"}


def get_role_menu_ids(db: Session, role_id: int) -> list[int]:
    """获取角色的菜单权限ID列表"""
    return [rm.menu_id for rm in db.query(SysRoleMenu).filter(SysRoleMenu.role_id == role_id).all()]


# ==================== 菜单管理 ====================
def get_menu_tree(db: Session) -> list[MenuResponse]:
    """获取菜单树"""
    menus = db.query(SysMenu).order_by(SysMenu.parent_id, SysMenu.sort).all()
    menu_dict = {m.id: MenuResponse.model_validate(m) for m in menus}
    tree = []
    for m in menus:
        if m.parent_id == 0:
            tree.append(menu_dict[m.id])
        elif m.parent_id in menu_dict:
            menu_dict[m.parent_id].children.append(menu_dict[m.id])
    return tree


def create_menu(db: Session, data: MenuCreate, operator_id: int | None = None, request: Request | None = None):
    menu = SysMenu(**data.model_dump())
    db.add(menu)
    db.flush()
    record_operation_log(
        db,
        module="系统管理",
        action="create",
        entity_type="sys_menu",
        entity_id=menu.id,
        entity_name=menu.menu_name,
        operator_id=operator_id,
        request=request,
        summary=f"创建菜单：{menu.menu_name}",
        after_data=serialize_model(menu),
    )
    db.commit()
    return {"msg": "创建成功", "id": menu.id}


def update_menu(db: Session, menu_id: int, data: MenuUpdate, operator_id: int | None = None, request: Request | None = None):
    menu = db.query(SysMenu).filter(SysMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单不存在")
    before = serialize_model(menu)
    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(menu, key, val)
    db.flush()
    ensure_recovery_administrator_exists(db)
    record_operation_log(
        db,
        module="系统管理",
        action="update",
        entity_type="sys_menu",
        entity_id=menu.id,
        entity_name=menu.menu_name,
        operator_id=operator_id,
        request=request,
        summary=f"更新菜单：{menu.menu_name}",
        before_data=before,
        after_data=serialize_model(menu),
    )
    db.commit()
    return {"msg": "更新成功"}


def delete_menu(db: Session, menu_id: int, operator_id: int | None = None, request: Request | None = None):
    menu = db.query(SysMenu).filter(SysMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单不存在")
    before = serialize_model(menu)
    # 删除子菜单
    db.query(SysMenu).filter(SysMenu.parent_id == menu_id).update({"parent_id": 0})
    db.query(SysRoleMenu).filter(SysRoleMenu.menu_id == menu_id).delete()
    db.delete(menu)
    db.flush()
    ensure_recovery_administrator_exists(db)
    record_operation_log(
        db,
        module="系统管理",
        action="delete",
        entity_type="sys_menu",
        entity_id=menu_id,
        entity_name=menu.menu_name,
        operator_id=operator_id,
        request=request,
        summary=f"删除菜单：{menu.menu_name}",
        before_data=before,
    )
    db.commit()
    return {"msg": "删除成功"}


# ==================== 部门管理 ====================
def _get_all_child_dept_ids(db: Session, parent_id: int) -> list[int]:
    """递归获取所有子部门ID"""
    children = db.query(SysDept.id).filter(SysDept.parent_id == parent_id).all()
    ids = [c[0] for c in children]
    result = list(ids)
    for cid in ids:
        result.extend(_get_all_child_dept_ids(db, cid))
    return result


def get_dept_tree(db: Session) -> list[DeptResponse]:
    """获取部门树"""
    depts = db.query(SysDept).order_by(SysDept.parent_id, SysDept.sort).all()
    dept_dict = {d.id: DeptResponse.model_validate(d) for d in depts}
    tree = []
    for d in depts:
        if d.parent_id == 0:
            tree.append(dept_dict[d.id])
        elif d.parent_id in dept_dict:
            dept_dict[d.parent_id].children.append(dept_dict[d.id])
    return tree


def get_dept_options(db: Session) -> list[dict]:
    depts = db.query(SysDept).filter(SysDept.status == 1).order_by(SysDept.sort, SysDept.id).all()
    return [
        {"id": dept.id, "parent_id": dept.parent_id, "dept_name": dept.dept_name}
        for dept in depts
    ]


def create_dept(db: Session, data: DeptCreate, operator_id: int | None = None, request: Request | None = None):
    dept = SysDept(**data.model_dump())
    db.add(dept)
    db.flush()
    record_operation_log(
        db,
        module="系统管理",
        action="create",
        entity_type="sys_dept",
        entity_id=dept.id,
        entity_name=dept.dept_name,
        operator_id=operator_id,
        request=request,
        summary=f"创建部门：{dept.dept_name}",
        after_data=serialize_model(dept),
    )
    db.commit()
    return {"msg": "创建成功", "id": dept.id}


def update_dept(db: Session, dept_id: int, data: DeptUpdate, operator_id: int | None = None, request: Request | None = None):
    dept = db.query(SysDept).filter(SysDept.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")
    before = serialize_model(dept)
    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(dept, key, val)
    record_operation_log(
        db,
        module="系统管理",
        action="update",
        entity_type="sys_dept",
        entity_id=dept.id,
        entity_name=dept.dept_name,
        operator_id=operator_id,
        request=request,
        summary=f"更新部门：{dept.dept_name}",
        before_data=before,
        after_data=serialize_model(dept),
    )
    db.commit()
    return {"msg": "更新成功"}


def delete_dept(db: Session, dept_id: int, operator_id: int | None = None, request: Request | None = None):
    dept = db.query(SysDept).filter(SysDept.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")
    if db.query(SysUser).filter(SysUser.dept_id == dept_id).first():
        raise HTTPException(status_code=400, detail="部门下仍有用户，无法删除")
    before = serialize_model(dept)
    db.query(SysDept).filter(SysDept.parent_id == dept_id).update({"parent_id": 0})
    db.delete(dept)
    record_operation_log(
        db,
        module="系统管理",
        action="delete",
        entity_type="sys_dept",
        entity_id=dept_id,
        entity_name=dept.dept_name,
        operator_id=operator_id,
        request=request,
        summary=f"删除部门：{dept.dept_name}",
        before_data=before,
    )
    db.commit()
    return {"msg": "删除成功"}
