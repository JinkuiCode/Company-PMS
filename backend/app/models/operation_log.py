import datetime

from sqlalchemy import DateTime, Index, Integer, func
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SysOperationLog(Base):
    """系统操作日志表。

    日志保留操作者快照，不使用用户表外键，避免用户删除后破坏审计记录。
    """
    __tablename__ = "sys_operation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment="业务模块")
    action: Mapped[str] = mapped_column(NVARCHAR(32), nullable=False, comment="动作")
    entity_type: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment="对象类型")
    entity_id: Mapped[str | None] = mapped_column(NVARCHAR(64), default=None, comment="对象ID")
    entity_name: Mapped[str | None] = mapped_column(NVARCHAR(256), default=None, comment="对象名称")
    operator_id: Mapped[int | None] = mapped_column(Integer, default=None, comment="操作者ID")
    operator_name: Mapped[str | None] = mapped_column(NVARCHAR(64), default=None, comment="操作者名称快照")
    ip_address: Mapped[str | None] = mapped_column(NVARCHAR(64), default=None, comment="客户端IP")
    user_agent: Mapped[str | None] = mapped_column(NVARCHAR(512), default=None, comment="User-Agent")
    request_path: Mapped[str | None] = mapped_column(NVARCHAR(256), default=None, comment="请求路径")
    request_method: Mapped[str | None] = mapped_column(NVARCHAR(16), default=None, comment="请求方法")
    status: Mapped[str] = mapped_column(NVARCHAR(16), nullable=False, default="success", comment="状态")
    summary: Mapped[str] = mapped_column(NVARCHAR(512), nullable=False, comment="摘要")
    error_msg: Mapped[str | None] = mapped_column(NVARCHAR(1024), default=None, comment="错误信息")
    before_data: Mapped[str | None] = mapped_column(NVARCHAR(None), default=None, comment="变更前JSON")
    after_data: Mapped[str | None] = mapped_column(NVARCHAR(None), default=None, comment="变更后JSON")
    diff_data: Mapped[str | None] = mapped_column(NVARCHAR(None), default=None, comment="差异JSON")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_operation_log_created_at", "created_at"),
        Index("idx_operation_log_module", "module"),
        Index("idx_operation_log_action", "action"),
        Index("idx_operation_log_operator", "operator_id"),
        Index("idx_operation_log_entity", "entity_type", "entity_id"),
    )
