import datetime

from sqlalchemy import Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SysUser(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(NVARCHAR(64), unique=True, nullable=False, comment="用户名")
    real_name: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment="真实姓名")
    password_hash: Mapped[str] = mapped_column(NVARCHAR(256), nullable=False, comment="密码哈希")
    dept_id: Mapped[int | None] = mapped_column(Integer, default=None, comment="所属部门ID")
    mobile: Mapped[str | None] = mapped_column(NVARCHAR(20), default=None, comment="手机号")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1=启用 0=禁用")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RememberToken(Base):
    """免密登录令牌表，存储长期有效的记住我令牌哈希"""
    __tablename__ = "sys_remember_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=False, index=True, comment="关联用户ID")
    token_hash: Mapped[str] = mapped_column(NVARCHAR(256), nullable=False, comment="令牌 SHA256 哈希")
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment="过期时间")
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="最近使用时间")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
