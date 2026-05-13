import datetime

from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SysUser(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="用户名")
    real_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="真实姓名")
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False, comment="密码哈希")
    dept_id: Mapped[int | None] = mapped_column(Integer, default=None, comment="所属部门ID")
    mobile: Mapped[str | None] = mapped_column(String(20), default=None, comment="手机号")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1=启用 0=禁用")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
