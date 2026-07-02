import datetime

from sqlalchemy import Integer, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SysRole(Base):
    """角色表"""
    __tablename__ = "sys_role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_name: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment="角色名称")
    role_code: Mapped[str] = mapped_column(NVARCHAR(64), unique=True, nullable=False, comment="角色编码")
    data_scope: Mapped[int] = mapped_column(Integer, default=1, comment="数据权限: 1本人 2本部门 3本部门及子部门 4全部")
    product_lines: Mapped[str | None] = mapped_column(NVARCHAR(256), default=None, comment="允许的产品线，逗号分隔，空=不限制")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1启用 0禁用")
    remark: Mapped[str | None] = mapped_column(NVARCHAR(256), default=None, comment="备注")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SysMenu(Base):
    """菜单/权限表"""
    __tablename__ = "sys_menu"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(Integer, default=0, comment="父菜单ID，0为顶级")
    menu_name: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment="菜单名称")
    menu_type: Mapped[str] = mapped_column(NVARCHAR(1), default="M", comment="类型: M目录 C菜单 B按钮")
    permission_code: Mapped[str | None] = mapped_column(NVARCHAR(128), default=None, comment="权限标识")
    path: Mapped[str | None] = mapped_column(NVARCHAR(256), default=None, comment="前端路由路径")
    component: Mapped[str | None] = mapped_column(NVARCHAR(256), default=None, comment="前端组件路径")
    icon: Mapped[str | None] = mapped_column(NVARCHAR(64), default=None, comment="图标")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    visible: Mapped[int] = mapped_column(Integer, default=1, comment="是否可见: 1是 0否")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1启用 0禁用")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SysDept(Base):
    """部门表"""
    __tablename__ = "sys_dept"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(Integer, default=0, comment="父部门ID，0为顶级")
    dept_name: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment="部门名称")
    leader_id: Mapped[int | None] = mapped_column(Integer, default=None, comment="负责人ID")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1启用 0禁用")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SysUserRole(Base):
    """用户-角色关联表"""
    __tablename__ = "sys_user_role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_role.id"), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uk_user_role"),)


class SysRoleMenu(Base):
    """角色-菜单关联表"""
    __tablename__ = "sys_role_menu"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_role.id"), nullable=False)
    menu_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_menu.id"), nullable=False)

    __table_args__ = (UniqueConstraint("role_id", "menu_id", name="uk_role_menu"),)
