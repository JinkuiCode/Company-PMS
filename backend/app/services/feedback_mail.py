"""Durable opt-in SMTP delivery; ambiguous results require administrator review."""
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate
import logging
import re
import smtplib
import ssl
from sqlalchemy import update
from fastapi import HTTPException
from app.models.feedback import FeedbackNotification as Notice, FeedbackReport, FeedbackFollowup
from app.models.parameter import SysParameter
from app.models.user import SysUser
from app.models.rbac import SysRole, SysMenu, SysRoleMenu, SysUserRole
from app.services.authorization import enforce_permission, build_authorization_context
from app.services.feedback import require_report, enum_labels, category_code
from app.services.operation_log import record_operation_log, serialize_model
from app.services.secret_encryption import decrypt_secret, SecretEncryptionError
from app.services.mail_transport_policy import transport_allowed


def configuration(db):
    rows = {row.code.removeprefix('mail.'): row for row in db.query(SysParameter).filter(SysParameter.code.like('mail.%'))}
    values = {key: row.value_text for key, row in rows.items() if key != 'password'}
    if values.get('enabled') != 'true' or not values.get('host') or not values.get('sender'):
        return None
    values['port'] = int(values.get('port') or 465)
    values['security'] = values.get('security') or 'ssl'
    if not transport_allowed(values['host'], values['port'], values['security']):
        return None
    if values.get('username'):
        password = rows.get('password')
        if not password or not password.secret_ciphertext:
            return None
        values['password'] = decrypt_secret(password.secret_ciphertext, 'mail.password')
    return values


def recipients(db, notice, report):
    if notice.audience == 'author':
        users = [db.get(SysUser, report.author_id)]
    else:
        candidates = db.query(SysUser).join(SysUserRole, SysUserRole.user_id == SysUser.id).join(SysRole, SysRole.id == SysUserRole.role_id).join(SysRoleMenu, SysRoleMenu.role_id == SysRole.id).join(SysMenu, SysMenu.id == SysRoleMenu.menu_id).filter(SysUser.status == 1, SysRole.status == 1, SysMenu.status == 1, SysMenu.permission_code == 'feedback:handle').distinct().all()
        users = [user for user in candidates if 'feedback:view' in build_authorization_context(db, user.id)['permissions']]
    return sorted({user.email.strip() for user in users if user and user.status == 1 and user.email and re.fullmatch(r'[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+', user.email.strip())})


def send_mail(config, message, addresses):
    if not transport_allowed(config.get('host'), config.get('port'), config.get('security')):
        raise ValueError('SMTP connection mode or endpoint is not allowed')
    factory = smtplib.SMTP_SSL if config['security'] == 'ssl' else smtplib.SMTP
    kwargs = dict(timeout=20)
    if config['security'] == 'ssl':
        kwargs['context'] = ssl.create_default_context()
    smtp = factory(config['host'], config['port'], **kwargs)
    try:
        if config['security'] == 'starttls':
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        if config.get('username'):
            smtp.login(config['username'], config['password'])
        refused = smtp.send_message(message, from_addr=config['sender'], to_addrs=addresses)
        if refused:
            # send_message returns only when at least one recipient accepted the message.
            raise smtplib.SMTPException('Partial recipient delivery')
    finally:
        # QUIT is cleanup, not the result of DATA. Never turn acceptance into retry.
        try:
            smtp.quit()
        except (OSError, smtplib.SMTPException):
            try:
                smtp.close()
            except (OSError, smtplib.SMTPException):
                pass


def process_one(db):
    now = datetime.utcnow()
    db.execute(update(Notice).where(Notice.status == 'processing', Notice.claimed_at < now - timedelta(minutes=10)).values(status='unknown', error_message='发送进程中断，投递结果需人工核查'))
    db.commit()
    notice = db.query(Notice).filter(Notice.status.in_(['pending', 'waiting']), Notice.next_attempt_at <= now).order_by(Notice.id).first()
    if notice is None:
        return False
    try:
        config = configuration(db)
    except (SecretEncryptionError, ValueError):
        config = None
    if config is None:
        db.execute(update(Notice).where(Notice.id == notice.id, Notice.status.in_(['pending', 'waiting'])).values(status='waiting', error_message='邮件通知未开启或配置不完整', next_attempt_at=now + timedelta(seconds=60)))
        db.commit()
        return True
    claimed = db.execute(update(Notice).where(Notice.id == notice.id, Notice.status.in_(['pending', 'waiting'])).values(status='processing', claimed_at=now, attempts=Notice.attempts + 1))
    db.commit()
    if claimed.rowcount != 1:
        return False
    db.refresh(notice)
    report = db.get(FeedbackReport, notice.report_id)
    addresses = recipients(db, notice, report)
    notice.recipient_count = len(addresses)
    if not addresses:
        notice.status, notice.error_message = 'failed', '无有效收件人，请检查账号、处理权限和邮箱'
        db.commit()
        return True
    event = db.query(FeedbackFollowup).filter_by(report_id=report.id, version=notice.version).first()
    message = EmailMessage()
    message['From'] = config['sender']
    message['To'] = config['sender']
    message['Subject'] = f'PMS提报 {report.report_no}：' + ('处理结果更新' if notice.audience == 'author' else '新提报或补充信息')
    message['Date'] = formatdate(localtime=True)
    message['Message-ID'] = f'<pms-feedback-{notice.report_id}-{notice.version}-{notice.audience}@{config["sender"].split("@")[-1]}>'
    def label(code, value):
        return enum_labels(db, code).get(value, str(value)) if value else ''
    details = [f'提报编号：{report.report_no}', f'标题：{report.title}',
        f'类型：{label("feedback_type", report.type_id)}', f'模块：{label("feedback_module", report.module_id)}',
        f'类别：{label(category_code(report.type_id), report.category_id)}']
    if event:
        details.append(f'状态：{label("feedback_status", event.status_id)}')
        if event.outcome_id:
            details.extend([f'结论：{label("feedback_outcome", event.outcome_id)}', f'归因：{label("feedback_cause", event.cause_id)}'])
    message.set_content('\n'.join(details) + f'\n\n{event.description if event else report.description}\n\n请进入PMS“问题提报”查看详情。')
    try:
        send_mail(config, message, addresses)
        notice.status, notice.sent_at, notice.error_message = 'sent', datetime.utcnow(), None
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused):
        notice.status, notice.error_message = 'failed', '邮件认证或收件地址被拒绝，请核对邮件配置及用户邮箱'
    except smtplib.SMTPResponseException as exc:
        notice.status = 'pending' if 400 <= exc.smtp_code < 500 and notice.attempts < 3 else 'failed'
        notice.error_message = f'邮件服务拒绝本次请求（状态码{exc.smtp_code}）'
        notice.next_attempt_at = now + timedelta(minutes=notice.attempts * 2)
    except (OSError, smtplib.SMTPException):
        notice.status, notice.error_message = 'unknown', '邮件连接中断，投递结果未知；核查收件后再受控重试'
    db.commit()
    return True


def retry(db, context, notice_id, request=None):
    enforce_permission(context, 'feedback:notification:retry')
    enforce_permission(context, 'feedback:handle')
    notice = db.get(Notice, notice_id)
    if not notice:
        raise HTTPException(404, '通知不存在')
    report = require_report(db, context, notice.report_id)
    before = serialize_model(notice)
    changed = db.execute(update(Notice).where(Notice.id == notice_id, Notice.status.in_(['failed', 'unknown', 'waiting'])).values(status='pending', attempts=0, claimed_at=None, next_attempt_at=datetime.utcnow(), error_message=None), execution_options={'synchronize_session': False})
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, '通知已发送或发送中，不能重复触发')
    db.refresh(notice)
    record_operation_log(db, module='问题提报', action='update', entity_type='pms_feedback_notification', entity_id=notice_id, entity_name=report.report_no, operator_id=context['user_id'], request=request, summary='受控重试邮件通知', before_data=before, after_data=serialize_model(notice))
    db.commit()
    return {'message': '通知已重新排队'}


def worker(stop, session_factory):
    while not stop.is_set():
        with session_factory() as db:
            try:
                process_one(db)
            except Exception:
                db.rollback()
                logging.getLogger(__name__).warning('提报通知处理失败，已回滚当前事务')
        stop.wait(5)
