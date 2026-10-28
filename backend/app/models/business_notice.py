"""Personal approval events and their separate SMTP delivery records."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, Index
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BusinessNotice(Base):
    __tablename__ = 'pms_business_notice'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey('pms_archive_change.id'), nullable=False, comment='档案变更申请')
    event: Mapped[str] = mapped_column(NVARCHAR(16), nullable=False, comment='通知事件')
    request_version: Mapped[int] = mapped_column(Integer, nullable=False, comment='申请事件版本')
    user_id: Mapped[int] = mapped_column(ForeignKey('sys_user.id'), nullable=False, comment='接收用户')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, comment='通知时间')
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment='明确已读时间')
    __table_args__ = (
        UniqueConstraint('change_id','event','request_version','user_id',name='uq_business_notice_event'),
        Index('idx_business_notice_personal','user_id','read_at','id'),
    )


class BusinessNoticeMail(Base):
    __tablename__ = 'pms_business_notice_mail'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey('pms_business_notice.id'), nullable=False, comment='个人业务通知')
    status: Mapped[str] = mapped_column(NVARCHAR(16), nullable=False, default='pending', comment='邮件投递状态')
    recipient: Mapped[str | None] = mapped_column(NVARCHAR(256), nullable=True, comment='实际投递邮箱')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='尝试次数')
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment='执行领取时间')
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, comment='下次处理时间')
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment='邮件服务器接受时间')
    error_message: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True, comment='投递说明')
    __table_args__ = (
        UniqueConstraint('notice_id',name='uq_business_notice_mail'),
        Index('idx_business_notice_mail_pending','status','next_attempt_at'),
    )
