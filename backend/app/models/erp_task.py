from datetime import datetime
from sqlalchemy import Integer, DateTime, Index
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ErpSyncTask(Base):
    __tablename__ = 'erp_sync_task'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    archive_id: Mapped[int] = mapped_column(Integer, nullable=False, comment='档案ID')
    project_code: Mapped[str] = mapped_column(NVARCHAR(32), comment='保存时项目编号')
    project_name: Mapped[str | None] = mapped_column(NVARCHAR(128), comment='保存时项目名称')
    operator_id: Mapped[int | None] = mapped_column(Integer, comment='保存人ID')
    status: Mapped[str] = mapped_column(NVARCHAR(24), default='queued', comment='同步任务状态')
    attempts: Mapped[int] = mapped_column(Integer, default=0, comment='尝试次数')
    message: Mapped[str | None] = mapped_column(NVARCHAR(1024), comment='执行结果')
    history: Mapped[str] = mapped_column(NVARCHAR(None), default='[]', comment='执行历史JSON')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment='任务时间')
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment='下次执行时间')
    started_at: Mapped[datetime | None] = mapped_column(DateTime, comment='最后开始时间')
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, comment='最后完成时间')
    __table_args__ = (Index('idx_erp_task_schedule', 'status', 'next_attempt_at'), Index('idx_erp_task_archive', 'archive_id', 'id'))
