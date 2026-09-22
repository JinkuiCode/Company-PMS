"""Organization-backed master data; identifiers are not legacy enum values."""
from datetime import datetime
from sqlalchemy import Integer, BigInteger, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, func
from sqlalchemy.dialects.mssql import NVARCHAR, DATETIME2
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class SysProductLine(Base):
    __tablename__ = 'sys_product_line'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(NVARCHAR(32), nullable=False, comment='组织数据源')
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='金蝶组织内码')
    organization_code: Mapped[str] = mapped_column(NVARCHAR(80), nullable=False, comment='金蝶组织编码')
    organization_name: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False, comment='金蝶组织名称')
    display_name: Mapped[str] = mapped_column(NVARCHAR(128), nullable=False, comment='产品线名称')
    name_key: Mapped[str] = mapped_column(NVARCHAR(128), nullable=False)
    is_enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment='启用状态')
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment='排序')
    created_by: Mapped[int | None] = mapped_column(ForeignKey('sys_user.id'), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey('sys_user.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime().with_variant(DATETIME2(precision=6), 'mssql'), default=datetime.now, nullable=False)
    __table_args__ = (
        UniqueConstraint('source_key', 'organization_id', name='uk_product_line_organization'),
        UniqueConstraint('name_key', name='uk_product_line_name'),
        CheckConstraint('organization_id > 0', name='ck_product_line_org'),
        CheckConstraint('is_enabled IN (0,1)', name='ck_product_line_enabled'),
        {'sqlite_autoincrement': True},
    )


class SysRoleProductLine(Base):
    __tablename__ = 'sys_role_product_line'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey('sys_role.id'), nullable=False, index=True)
    product_line_id: Mapped[int] = mapped_column(ForeignKey('sys_product_line.id'), nullable=False, index=True)
    __table_args__ = (UniqueConstraint('role_id', 'product_line_id', name='uk_role_product_line'),)
