import datetime
from sqlalchemy import DateTime, Integer, func
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class SysParameter(Base):
    __tablename__ = "sys_parameter"
    code: Mapped[str] = mapped_column(NVARCHAR(64), primary_key=True, comment="参数编码")
    secret_hash: Mapped[str | None] = mapped_column(NVARCHAR(256), nullable=True, comment="参数密文")
    value_text: Mapped[str | None] = mapped_column(NVARCHAR(None), nullable=True, comment="参数值")
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="参数版本")
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
