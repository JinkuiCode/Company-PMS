"""Per-user release delivery. Unknown SMTP outcome is never an automatic retry."""
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate
import json
import re
import smtplib
from fastapi import HTTPException
from sqlalchemy import update
from app.models.release import PmsRelease, PmsReleaseNotice, PmsReleaseMail as Mail
from app.models.user import SysUser
from app.services.feedback_mail import configuration, send_mail
from app.services.authorization import enforce_permission, build_authorization_context
from app.services.operation_log import record_operation_log, serialize_model


def build_message(config, release, mail, recipient):
    message = EmailMessage()
    message['From'] = config['sender']; message['To'] = recipient
    message['Subject'] = f'PMS升级通知 {release.version}：{release.title}'
    message['Date'] = formatdate(localtime=True)
    message['Message-ID'] = f'<pms-release-{release.id}-{mail.id}@{config["sender"].split("@")[-1]}>'
    lines = [f'{release.version} {release.title}', release.summary, '']
    for change in json.loads(release.content_json):
        lines.extend([f'{change["kind"]}：{change["title"]}', change['description'], ''])
    lines.append('请进入PMS“升级通知”查看详情和相关页面说明；站内已读需本人确认。')
    message.set_content('\n'.join(lines))
    return message


def process_one(db):
    now = datetime.utcnow()
    db.execute(update(Mail).where(Mail.status == 'processing', Mail.claimed_at < now-timedelta(minutes=10)).values(
        status='unknown', error_message='发送进程中断，结果未知；请核查收件情况'))
    db.commit()
    mail = db.query(Mail).filter(Mail.status.in_(['pending', 'waiting']), Mail.next_attempt_at <= now).order_by(Mail.id).first()
    if mail is None: return False
    try: config = configuration(db)
    except (ValueError, RuntimeError): config = None
    if not config:
        db.execute(update(Mail).where(Mail.id == mail.id, Mail.status.in_(['pending', 'waiting'])).values(
            status='waiting', next_attempt_at=now+timedelta(minutes=1), error_message='邮件通知未开启或配置不完整'))
        db.commit(); return True
    claim = db.execute(update(Mail).where(Mail.id == mail.id, Mail.status.in_(['pending', 'waiting'])).values(
        status='processing', claimed_at=now, attempts=Mail.attempts+1))
    db.commit()
    if claim.rowcount != 1: return False
    db.refresh(mail)
    notice = db.get(PmsReleaseNotice, mail.notice_id)
    user = db.get(SysUser, notice.user_id)
    release = db.get(PmsRelease, notice.release_id)
    email = (user.email or '').strip() if user else ''
    if not user or user.status != 1 or not re.fullmatch(r'[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+', email):
        mail.status, mail.error_message = 'failed', '用户已停用或未维护有效邮箱；站内通知保留'
    else:
        mail.recipient = email
        try:
            send_mail(config, build_message(config, release, mail, email), [email])
            mail.status, mail.accepted_at, mail.error_message = 'accepted', datetime.utcnow(), None
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused):
            mail.status, mail.error_message = 'failed', '邮件认证或收件地址被拒绝'
        except smtplib.SMTPResponseException as exc:
            mail.status = 'pending' if 400 <= exc.smtp_code < 500 and mail.attempts < 3 else 'failed'
            mail.next_attempt_at = now+timedelta(minutes=2*mail.attempts)
            mail.error_message = f'邮件服务拒绝请求（状态码{exc.smtp_code}）'
        except (OSError, smtplib.SMTPException):
            mail.status, mail.error_message = 'unknown', '连接中断，投递结果未知；核查未收件后受控重试'
    record_operation_log(db, module='版本通知', action='mail_delivery', entity_type='pms_release_mail',
        entity_id=mail.id, entity_name=release.version, status='success' if mail.status == 'accepted' else 'failed',
        summary='邮件服务器已接受投递' if mail.status == 'accepted' else mail.error_message,
        after_data={'status': mail.status, 'attempts': mail.attempts})
    db.commit(); return True


def list_deliveries(db, context, release_id, *, page=1, page_size=50):
    enforce_permission(context, 'system:release:manage')
    query = db.query(Mail, PmsReleaseNotice, SysUser).join(PmsReleaseNotice, Mail.notice_id == PmsReleaseNotice.id).join(
        SysUser, PmsReleaseNotice.user_id == SysUser.id).filter(PmsReleaseNotice.release_id == release_id)
    return {'total': query.count(), 'items': [dict(id=mail.id, user_name=user.real_name or user.username,
        read_at=notice.read_at, status=mail.status, attempts=mail.attempts, accepted_at=mail.accepted_at,
        error_message=mail.error_message) for mail, notice, user in query.order_by(Mail.id).offset((page-1)*page_size).limit(page_size)]}


def retry(db, context, mail_id, *, reason, checked_not_received=False, request=None):
    live = build_authorization_context(db, context['user_id'])
    for code in ('system:release:manage', 'system:release:retry'): enforce_permission(live, code)
    row = db.get(Mail, mail_id)
    if not row: raise HTTPException(404, '投递记录不存在')
    if not reason.strip(): raise HTTPException(422, '请填写重试原因')
    if row.status == 'unknown' and not checked_not_received: raise HTTPException(422, '请先人工核查收件，确认未收到后再重试')
    before = serialize_model(row)
    changed = db.execute(update(Mail).where(Mail.id == row.id, Mail.status == row.status,
        Mail.status.in_(['unknown', 'failed', 'waiting'])).values(status='pending', attempts=0,
        claimed_at=None, next_attempt_at=datetime.utcnow(), error_message=None))
    if changed.rowcount != 1: raise HTTPException(409, '投递状态已变化，当前不可重试')
    record_operation_log(db, module='版本通知', action='retry', entity_type='pms_release_mail',
        entity_id=row.id, operator_id=context['user_id'], request=request, summary='人工确认重试邮件',
        before_data=before, after_data={'reason': reason, 'checked_not_received': checked_not_received, 'status': 'pending'})
    db.commit(); return {'queued': True}


def worker(stop, session_factory):
    import logging
    while not stop.is_set():
        try:
            with session_factory() as db: processed = process_one(db)
        except Exception:
            logging.getLogger(__name__).warning('版本通知邮件处理失败，请检查服务及存储')
            processed = False
        stop.wait(1 if processed else 10)
