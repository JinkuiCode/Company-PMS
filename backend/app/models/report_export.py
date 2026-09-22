from datetime import datetime
from sqlalchemy import Integer, DateTime, Index
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ReportExportJob(Base):
    __tablename__ = 'pms_report_export_job'
    id: Mapped[str] = mapped_column(NVARCHAR(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    report: Mapped[str] = mapped_column(NVARCHAR(24), nullable=False)
    parameters: Mapped[str] = mapped_column(NVARCHAR(None), nullable=False)
    columns: Mapped[str] = mapped_column(NVARCHAR(None), nullable=False)
    scope_hash: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False)
    status: Mapped[str] = mapped_column(NVARCHAR(24), default='queued', nullable=False)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(NVARCHAR(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (Index('idx_report_export_schedule', 'status', 'created_at'),)
