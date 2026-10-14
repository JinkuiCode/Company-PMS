"""Persistent archive change requests; the formal archive changes only on approval."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ArchiveChange(Base):
    __tablename__ = 'pms_archive_change'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment='变更申请内码')
    archive_id: Mapped[int] = mapped_column(ForeignKey('pms_project_archive.id'), nullable=False, index=True, comment='项目档案')
    active_archive_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='活动申请档案')
    submission_id: Mapped[str] = mapped_column(NVARCHAR(36), nullable=False, comment='提交去重标识')
    request_hash: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment='提交内容指纹')
    author_id: Mapped[int] = mapped_column(ForeignKey('sys_user.id'), nullable=False, comment='提交人')
    approver_id: Mapped[int] = mapped_column(ForeignKey('sys_user.id'), nullable=False, comment='审批人')
    department_id: Mapped[int] = mapped_column(ForeignKey('sys_dept.id'), nullable=False, comment='原负责人部门')
    base_version: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment='原档案业务版本')
    updates_json: Mapped[str] = mapped_column(NVARCHAR(None), nullable=False, comment='申请修改值')
    differences_json: Mapped[str] = mapped_column(NVARCHAR(None), nullable=False, comment='中文字段差异')
    reason: Mapped[str] = mapped_column(NVARCHAR(1024), nullable=False, comment='变更原因')
    opinion: Mapped[str | None] = mapped_column(NVARCHAR(1024), nullable=True, comment='审批意见')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=2, comment='审批状态')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment='申请版本')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment='申请时间')
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment='处理时间')
    __table_args__ = (
        Index('uq_archive_change_submission', 'author_id', 'submission_id', unique=True),
        Index('uq_archive_change_active', 'active_archive_id', unique=True,
              sqlite_where=text('active_archive_id IS NOT NULL'), mssql_where=text('active_archive_id IS NOT NULL')),
    )
