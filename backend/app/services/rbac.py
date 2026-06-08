"""RBAC CRUD 业务逻辑：用户、角色、菜单、部门"""
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.security import hash_password
from app.models.user import SysUser, RememberToken
from app.models.rbac import SysRole, SysMenu, SysDept, SysUserRole, SysRoleMenu
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.rbac import (
    RoleCreate, RoleUpdate, RoleResponse,
    MenuCreate, MenuUpdate, MenuResponse,
    DeptCreate, DeptUpdate, DeptResponse,
)


# ==================== 用户管理 ====================
def get_user_list(db: Session, page: int = 1, page_size: int = 15):
    """分页查询用户列表，附带角色信息"""
    query = db.query(SysUser)
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


def create_user(db: Session, data: UserCreate):
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
    db.commit()
    return {"msg": "创建成功", "id": user.id}


def update_user(db: Session, user_id: int, data: UserUpdate):
    """更新用户，可重新分配角色。密码变更或账号禁用时清除所有免密令牌"""
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    should_invalidate = False

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

    db.commit()
    return {"msg": "更新成功"}


def delete_user(db: Session, user_id: int):
    """删除用户及角色关联"""
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return {"msg": "删除成功"}


# ==================== 角色管理 ====================
def get_role_list(db: Session):
    """查询所有角色"""
    roles = db.query(SysRole).order_by(SysRole.id).all()
    return [RoleResponse.model_validate(r) for r in roles]


def create_role(db: Session, data: RoleCreate):
    """创建角色"""
    if db.query(SysRole).filter(SysRole.role_code == data.role_code).first():
        raise HTTPException(status_code=400, detail="角色编码已存在")
    role = SysRole(**data.model_dump())
    db.add(role)
    db.commit()
    db.refresh(role)
    return {"msg": "创建成功", "id": role.id}


def update_role(db: Session, role_id: int, data: RoleUpdate):
    """更新角色，可同时分配菜单权限"""
    role = db.query(SysRole).filter(SysRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    update_data = data.model_dump(exclude_unset=True, exclude={"menu_ids"})
    for key, val in update_data.items():
        setattr(role, key, val)

    # 重新分配菜单权限
    if data.menu_ids is not None:
        db.query(SysRoleMenu).filter(SysRoleMenu.role_id == role_id).delete()
        for menu_id in data.menu_ids:
            db.add(SysRoleMenu(role_id=role_id, menu_id=menu_id))

    db.commit()
    return {"msg": "更新成功"}


def delete_role(db: Session, role_id: int):
    """删除角色及关联数据"""
    role = db.query(SysRole).filter(SysRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    db.query(SysUserRole).filter(SysUserRole.role_id == role_id).delete()
    db.query(SysRoleMenu).filter(SysRoleMenu.role_id == role_id).delete()
    db.delete(role)
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


def create_menu(db: Session, data: MenuCreate):
    menu = SysMenu(**data.model_dump())
    db.add(menu)
    db.commit()
    return {"msg": "创建成功", "id": menu.id}


def update_menu(db: Session, menu_id: int, data: MenuUpdate):
    menu = db.query(SysMenu).filter(SysMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(menu, key, val)
    db.commit()
    return {"msg": "更新成功"}


def delete_menu(db: Session, menu_id: int):
    menu = db.query(SysMenu).filter(SysMenu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="菜单不存在")
    # 删除子菜单
    db.query(SysMenu).filter(SysMenu.parent_id == menu_id).update({"parent_id": 0})
    db.query(SysRoleMenu).filter(SysRoleMenu.menu_id == menu_id).delete()
    db.delete(menu)
    db.commit()
    return {"msg": "删除成功"}


# ==================== 部门管理 ====================
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


def create_dept(db: Session, data: DeptCreate):
    dept = SysDept(**data.model_dump())
    db.add(dept)
    db.commit()
    return {"msg": "创建成功", "id": dept.id}


def update_dept(db: Session, dept_id: int, data: DeptUpdate):
    dept = db.query(SysDept).filter(SysDept.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(dept, key, val)
    db.commit()
    return {"msg": "更新成功"}


def delete_dept(db: Session, dept_id: int):
    dept = db.query(SysDept).filter(SysDept.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")
    if db.query(SysUser).filter(SysUser.dept_id == dept_id).first():
        raise HTTPException(status_code=400, detail="部门下仍有用户，无法删除")
    db.query(SysDept).filter(SysDept.parent_id == dept_id).update({"parent_id": 0})
    db.delete(dept)
    db.commit()
    return {"msg": "删除成功"}
