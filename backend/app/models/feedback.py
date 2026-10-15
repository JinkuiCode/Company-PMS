"""Independent feedback records; no ERP or project foreign keys."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, Index
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class FeedbackReport(Base):
    __tablename__ = 'pms_feedback_report'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment='提报内码')
    report_no: Mapped[str] = mapped_column(NVARCHAR(40), unique=True, nullable=False, comment='提报编号')
    submission_id: Mapped[str] = mapped_column(NVARCHAR(36), nullable=False, comment='提交去重标识')
    type_id: Mapped[int] = mapped_column(Integer, nullable=False, comment='提报类型')
    module_id: Mapped[int] = mapped_column(Integer, nullable=False, comment='涉及模块')
    category_id: Mapped[int] = mapped_column(Integer, nullable=False, comment='具体类别')
    impact_id: Mapped[int] = mapped_column(Integer, nullable=False, comment='影响程度')
    title: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False, comment='标题')
    description: Mapped[str] = mapped_column(NVARCHAR(None), nullable=False, comment='详细说明')
    expected_result: Mapped[str] = mapped_column(NVARCHAR(None), nullable=False, comment='期望结果')
    steps: Mapped[str] = mapped_column(NVARCHAR(None), nullable=False, default='', comment='复现步骤')
    status_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True, comment='处理状态')
    author_id: Mapped[int] = mapped_column(ForeignKey('sys_user.id'), nullable=False, index=True, comment='提报人')
    handler_id: Mapped[int | None] = mapped_column(ForeignKey('sys_user.id'), nullable=True, comment='最后处理人')
    outcome_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='处理结论')
    cause_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='处理归因')
    opinion: Mapped[str | None] = mapped_column(NVARCHAR(None), nullable=True, comment='最新处理意见')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment='记录版本')
    runtime_version: Mapped[str | None] = mapped_column(NVARCHAR(32), nullable=True, comment='提报时运行版本')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment='提报时间')
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment='最后更新时间')
    __table_args__ = (Index('uq_feedback_submission', 'author_id', 'submission_id', unique=True),)


class FeedbackFollowup(Base):
    __tablename__ = 'pms_feedback_followup'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment='跟进内码')
    report_id: Mapped[int] = mapped_column(ForeignKey('pms_feedback_report.id'), nullable=False, index=True, comment='提报')
    actor_id: Mapped[int] = mapped_column(ForeignKey('sys_user.id'), nullable=False, comment='操作人')
    action: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, comment='跟进动作')
    description: Mapped[str] = mapped_column(NVARCHAR(None), nullable=False, comment='跟进说明')
    status_id: Mapped[int] = mapped_column(Integer, nullable=False, comment='处理状态')
    outcome_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='处理结论')
    cause_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment='处理归因')
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment='记录版本')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment='跟进时间')
    __table_args__ = (UniqueConstraint('report_id', 'version', name='uq_feedback_followup_version'),)


class FeedbackAttachment(Base):
    __tablename__ = 'pms_feedback_attachment'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment='附件内码')
    report_id: Mapped[int] = mapped_column(ForeignKey('pms_feedback_report.id'), nullable=False, index=True, comment='提报')
    uploader_id: Mapped[int] = mapped_column(ForeignKey('sys_user.id'), nullable=False, comment='上传人')
    filename: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False, comment='附件名称')
    storage_name: Mapped[str] = mapped_column(NVARCHAR(80), unique=True, nullable=False, comment='内部存储名')
    content_type: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, comment='文件类型')
    size: Mapped[int] = mapped_column(Integer, nullable=False, comment='文件字节数')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment='上传时间')


class FeedbackNotification(Base):
    __tablename__ = 'pms_feedback_notification'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment='通知内码')
    report_id: Mapped[int] = mapped_column(ForeignKey('pms_feedback_report.id'), nullable=False, index=True, comment='提报')
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment='提报事件版本')
    audience: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, comment='通知对象：管理员或提报人')
    status: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, default='pending', index=True, comment='通知状态')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='发送尝试次数')
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True, comment='下次发送时间')
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment='领取时间')
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment='发送时间')
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='有效收件人数')
    error_message: Mapped[str | None] = mapped_column(NVARCHAR(300), nullable=True, comment='脱敏失败原因')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment='入队时间')
    __table_args__ = (UniqueConstraint('report_id', 'version', 'audience', name='uq_feedback_notification_event'),)
