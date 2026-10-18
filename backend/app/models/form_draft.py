"""Private unfinished forms, never part of business archive queries."""
from datetime import datetime
from sqlalchemy import Integer, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class PmsFormDraft(Base):
    __tablename__ = 'pms_form_draft'
    id: Mapped[str] = mapped_column(NVARCHAR(36), primary_key=True, comment='草稿标识')
    owner_id: Mapped[int] = mapped_column(ForeignKey('sys_user.id'), nullable=False, comment='归属用户')
    resource: Mapped[str] = mapped_column(NVARCHAR(32), nullable=False, comment='表单资源')
    payload_json: Mapped[str] = mapped_column(NVARCHAR(None), nullable=False, comment='受控字段内容')
    product_line_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='产品线')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment='草稿版本')
    status: Mapped[str] = mapped_column(NVARCHAR(16), nullable=False, default='active', comment='草稿状态')
    archive_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='正式档案')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment='创建时间')
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment='保存时间')
    __table_args__ = (
        Index('idx_form_draft_owner', 'owner_id', 'resource', 'status', 'updated_at'),
        CheckConstraint('version > 0', name='ck_form_draft_version'),
        CheckConstraint("status IN ('active','used','deleted')", name='ck_form_draft_status'),
    )
