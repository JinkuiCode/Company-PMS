"""Published content, personal receipt and SMTP delivery are separate records."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, Index
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class PmsRelease(Base):
    __tablename__ = 'pms_release'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(NVARCHAR(32), unique=True, nullable=False, comment='发布版本')
    title: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, comment='更新标题')
    summary: Mapped[str] = mapped_column(NVARCHAR(500), nullable=False, comment='更新摘要')
    content_json: Mapped[str] = mapped_column(NVARCHAR(None), nullable=False, comment='统一更新内容')
    manifest_sha256: Mapped[str] = mapped_column(NVARCHAR(64), unique=True, nullable=False, comment='构建清单校验值')
    code_commit: Mapped[str] = mapped_column(NVARCHAR(40), nullable=False, comment='代码提交')
    build_id: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment='构建标识')
    database_revision: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, comment='数据库版本')
    published_by: Mapped[int] = mapped_column(Integer, nullable=False, comment='发布操作人')
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment='发布时间')


class PmsReleaseNotice(Base):
    __tablename__ = 'pms_release_notice'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_id: Mapped[int] = mapped_column(ForeignKey('pms_release.id'), nullable=False, comment='发布记录')
    user_id: Mapped[int] = mapped_column(ForeignKey('sys_user.id'), nullable=False, comment='接收用户')
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment='明确已读时间')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment='通知时间')
    __table_args__ = (UniqueConstraint('release_id', 'user_id', name='uq_release_notice_user'),
                     Index('idx_release_notice_personal', 'user_id', 'read_at', 'id'))


class PmsReleaseMail(Base):
    __tablename__ = 'pms_release_mail'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey('pms_release_notice.id'), unique=True, nullable=False, comment='个人通知')
    status: Mapped[str] = mapped_column(NVARCHAR(16), nullable=False, default='pending', comment='邮件投递状态')
    recipient: Mapped[str | None] = mapped_column(NVARCHAR(256), nullable=True, comment='实际投递邮箱')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='尝试次数')
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment='执行领取时间')
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, comment='下次处理时间')
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment='邮件服务器接受时间')
    error_message: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True, comment='投递说明')
    __table_args__ = (Index('idx_release_mail_pending', 'status', 'next_attempt_at'),)
