import datetime

from sqlalchemy import Integer, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SysDict(Base):
    """数据字典分类表"""
    __tablename__ = "sys_dict"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dict_code: Mapped[str] = mapped_column(NVARCHAR(64), unique=True, nullable=False, comment="字典编码（唯一标识）")
    dict_name: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment="字典名称")
    table_name: Mapped[str | None] = mapped_column(NVARCHAR(64), default=None, comment="对应数据库表名")
    field_name: Mapped[str | None] = mapped_column(NVARCHAR(64), default=None, comment="对应字段名")
    page_name: Mapped[str | None] = mapped_column(NVARCHAR(64), default=None, comment="前端页面名称")
    description: Mapped[str | None] = mapped_column(NVARCHAR(256), default=None, comment="描述")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1启用 0禁用")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SysDictItem(Base):
    """数据字典项（枚举值）表"""
    __tablename__ = "sys_dict_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dict_id: Mapped[int] = mapped_column(Integer, ForeignKey("sys_dict.id"), nullable=False, comment="字典分类ID")
    item_value: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment="数据库字段名")
    item_label: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment="表单字段名")
    field_type: Mapped[str | None] = mapped_column(NVARCHAR(32), default=None, comment="字段类型: text/number/date/enum/select/relation")
    description: Mapped[str | None] = mapped_column(NVARCHAR(256), default=None, comment="备注（枚举引用等）")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="状态: 1启用 0禁用")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("dict_id", "item_value", name="uk_dict_item_value"),
    )
