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


def create_role(db: Session, data: RoleCreate, operator_id: int | None = None, request: Request | None = None):
    """创建角色，可同时分配菜单权限"""
    if db.query(SysRole).filter(SysRole.role_code == data.role_code).first():
        raise HTTPException(status_code=400, detail="角色编码已存在")
    role_data = data.model_dump(exclude={"menu_ids"})
    role = SysRole(**role_data)
    db.add(role)
    db.commit()
    db.refresh(role)
    # 分配菜单权限
    for menu_id in data.menu_ids:
        db.add(SysRoleMenu(role_id=role.id, menu_id=menu_id))
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
        after_data=serialize_model(role, extra={"menu_ids": data.menu_ids}),
    )
    db.commit()
    return {"msg": "创建成功", "id": role.id}


def update_role(db: Session, role_id: int, data: RoleUpdate, operator_id: int | None = None, request: Request | None = None):
    """更新角色，可同时分配菜单权限"""
    role = db.query(SysRole).filter(SysRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    before_menu_ids = get_role_menu_ids(db, role_id)
    before = serialize_model(role, extra={"menu_ids": before_menu_ids})
    update_data = data.model_dump(exclude_unset=True, exclude={"menu_ids"})
    for key, val in update_data.items():
        setattr(role, key, val)

    # 重新分配菜单权限
    if data.menu_ids is not None:
        db.query(SysRoleMenu).filter(SysRoleMenu.role_id == role_id).delete()
        for menu_id in data.menu_ids:
            db.add(SysRoleMenu(role_id=role_id, menu_id=menu_id))

    after_menu_ids = data.menu_ids if data.menu_ids is not None else before_menu_ids
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
        after_data=serialize_model(role, extra={"menu_ids": after_menu_ids}),
    )
    db.commit()
    return {"msg": "更新成功"}


def delete_role(db: Session, role_id: int, operator_id: int | None = None, request: Request | None = None):
    """删除角色及关联数据"""
    role = db.query(SysRole).filter(SysRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    before = serialize_model(role, extra={"menu_ids": get_role_menu_ids(db, role_id)})
    db.query(SysUserRole).filter(SysUserRole.role_id == role_id).delete()
    db.query(SysRoleMenu).filter(SysRoleMenu.role_id == role_id).delete()
    db.delete(role)
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
