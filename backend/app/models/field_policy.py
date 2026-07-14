import datetime

from sqlalchemy import Boolean, DateTime, Integer, UniqueConstraint, func
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SysBusinessFieldPolicy(Base):
    """全系统统一的业务字段展示与录入规则。"""

    __tablename__ = "sys_business_field_policy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module_code: Mapped[str] = mapped_column(NVARCHAR(32), nullable=False)
    field_key: Mapped[str] = mapped_column(NVARCHAR(128), nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    list_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    required_effective_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=None)
    created_by: Mapped[int | None] = mapped_column(Integer, default=None)
    updated_by: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("module_code", "field_key", name="uk_business_field_policy"),
    )
