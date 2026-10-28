"""Single-recipient approval mail; ambiguous SMTP outcomes require human review."""
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formatdate
import logging
import re
import smtplib
from urllib.parse import urlsplit
from fastapi import HTTPException
from sqlalchemy import select, update
from app.core.config import settings
from app.core.business_time import business_time
from app.models.business_notice import BusinessNotice, BusinessNoticeMail as Mail, utc_now
from app.models.archive_change import ArchiveChange
from app.models.project import PmsProjectArchive
from app.models.user import SysUser
from app.services import business_notices as notices
from app.services.authorization import enforce_permission
from app.services.feedback_mail import configuration, send_mail
from app.services.operation_log import record_operation_log


def eligible(db, notice):
    try:
        context = notices.live_context(db, {'user_id':notice.user_id})
        change = notices.visible_changes(db, context).filter(ArchiveChange.id == notice.change_id).first()
        if change is None: return False
        if notice.event == 'submitted':
            return (change.status == 2 and change.approver_id == notice.user_id
                    and 'project:archive:edit' in context['permissions'])
        return change.author_id == notice.user_id and notice.event in ('approved','rejected')
    except HTTPException:
        return False


def build_message(config, notice, mail, archive, recipient):
    event = {'submitted':'等待审批','approved':'申请已通过','rejected':'申请已退回'}[notice.event]
    message = EmailMessage()
    message['From'] = config['sender']; message['To'] = recipient
    message['Subject'] = f'PMS {event}：' + ' '.join(archive.project_code.split())
    message['Date'] = formatdate(localtime=True)
    message['Message-ID'] = f'<pms-archive-notice-{notice.id}@pms.internal>'
    path = f'/project/archive?change_id={notice.change_id}'
    base = settings.PMS_FRONTEND_URL.strip().rstrip('/')
    try:
        url = urlsplit(base)
        trusted = url.scheme in ('https','http') and bool(url.hostname) and not (url.username or url.password or url.query or url.fragment) and url.path in ('','/')
    except ValueError:
        trusted = False
    link = base + path if trusted else path
    message.set_content('\n'.join([f'项目编号：{archive.project_code}',f'项目名称：{archive.project_name}',
        f'事件：{event}',f'时间：{business_time(notice.created_at).isoformat()}', '',
        '请登录 PMS 查看申请：' + link, '审批通过表示档案变更生效，ERP 同步状态请在档案中查看。']))
    return message


def audit(db, mail, *, before=None, action='mail_delivery', actor=None, request=None, extra=None):
    record_operation_log(db,module='业务通知',action=action,entity_type='pms_business_notice_mail',entity_id=mail.id,
        operator_id=actor,request=request,summary='人工确认重试邮件' if action=='retry' else
        ('邮件服务器已接受投递' if mail.status=='accepted' else mail.error_message or '投递状态更新'),
        status='success' if mail.status in ('accepted','pending','waiting','suppressed') else 'failed',
        before_data=before,after_data={'status':mail.status,'attempts':mail.attempts,**(extra or {})})


def recover_expired(db, now):
    rows = db.query(Mail).filter(Mail.status=='processing',Mail.claimed_at<now-timedelta(minutes=10)).limit(100).all()
    for row in rows:
        changed = db.execute(update(Mail).where(Mail.id==row.id,Mail.status=='processing',
            Mail.claimed_at<now-timedelta(minutes=10)).values(status='unknown',error_message='发送进程中断，结果未知；请核查收件情况'))
        if changed.rowcount: audit(db,row,before={'status':'processing'})
    db.commit()


def process_one(db):
    now = utc_now()
    recover_expired(db,now)
    mail = db.query(Mail).filter(Mail.status.in_(['pending','waiting']),Mail.next_attempt_at<=now).order_by(Mail.id).first()
    if mail is None: return False
    claimed = db.execute(update(Mail).where(Mail.id==mail.id,Mail.status.in_(['pending','waiting']),
        Mail.next_attempt_at<=now).values(status='processing',claimed_at=now))
    db.commit()
    if claimed.rowcount != 1: return False
    db.refresh(mail)
    notice = db.get(BusinessNotice,mail.notice_id)
    try: config = configuration(db)
    except (ValueError,RuntimeError): config = None
    # The committed claim and configuration read may outlive permission changes.
    db.expire_all()
    if notice is None or not eligible(db,notice):
        mail.status,mail.error_message='suppressed','当前权限、人员关系或申请状态已失效，停止投递'
    elif not config:
        mail.status,mail.error_message='waiting','邮件通知未开启或配置不完整'
        mail.next_attempt_at=now+timedelta(minutes=1)
    else:
        user = db.get(SysUser,notice.user_id)
        email = (user.email or '').strip()
        if not re.fullmatch(r'[^@\s<>,;:()"\\]+@[^@\s<>,;:()"\\]+\.[^@\s<>,;:()"\\]+',email):
            mail.status,mail.error_message='failed','收件人未维护有效邮箱；站内通知保留'
        else:
            mail.recipient=email;mail.attempts+=1
            db.commit()
            if not eligible(db,notice) or (db.get(SysUser,notice.user_id).email or '').strip()!=email:
                mail.status,mail.error_message='suppressed','发送前收件人或权限已变化，停止投递'
            else:
                change=db.get(ArchiveChange,notice.change_id)
                archive=db.get(PmsProjectArchive,change.archive_id)
                try:
                    send_mail(config,build_message(config,notice,mail,archive,email),[email])
                    mail.status,mail.accepted_at,mail.error_message='accepted',utc_now(),None
                except (smtplib.SMTPAuthenticationError,smtplib.SMTPRecipientsRefused):
                    mail.status,mail.error_message='failed','邮件认证或收件地址被拒绝'
                except smtplib.SMTPResponseException as exc:
                    mail.status='pending' if 400<=exc.smtp_code<500 and mail.attempts<3 else 'failed'
                    mail.next_attempt_at=now+timedelta(minutes=2*mail.attempts)
                    mail.error_message=f'邮件服务拒绝请求（状态码{exc.smtp_code}）'
                except (OSError,smtplib.SMTPException):
                    mail.status,mail.error_message='unknown','连接中断，投递结果未知；核查未收件后受控重试'
                except ValueError:
                    mail.status,mail.error_message='failed','邮件地址或传输配置不合法，未发送'
    audit(db,mail,before={'status':'processing'})
    db.commit()
    return True


def management_context(db, context, change_id):
    from app.services.project import ensure_archive_access
    current=notices.live_context(db,context);enforce_permission(current,notices.MANAGE)
    change=db.get(ArchiveChange,change_id)
    if change is None:raise HTTPException(404,'申请不存在或无权访问')
    ensure_archive_access(db,change.archive_id,current)
    return current


def list_deliveries(db, context, change_id):
    management_context(db,context,change_id)
    rows=db.query(Mail,BusinessNotice,SysUser).join(BusinessNotice,Mail.notice_id==BusinessNotice.id).join(
        SysUser,BusinessNotice.user_id==SysUser.id).filter(BusinessNotice.change_id==change_id).order_by(Mail.id).all()
    return {'total':len(rows),'items':[{'id':mail.id,'event':notice.event,'user_name':user.real_name or user.username,
        'status':mail.status,'attempts':mail.attempts,'read_at':business_time(notice.read_at),
        'accepted_at':business_time(mail.accepted_at),'error_message':mail.error_message} for mail,notice,user in rows]}


def retry(db,context,mail_id,*,reason,checked_not_received=False,request=None):
    try:
        # Check management grants before looking up an arbitrary delivery ID.
        current=notices.live_context(db,context)
        for code in (notices.MANAGE,notices.RETRY):enforce_permission(current,code)
        mail=db.get(Mail,mail_id)
        if mail is None:raise HTTPException(404,'投递记录不存在或无权访问')
        notice=db.get(BusinessNotice,mail.notice_id)
        management_context(db,current,notice.change_id)
        if not 1<=len(reason.strip())<=500:raise HTTPException(422,'请填写不超过500字的重试原因')
        if mail.status=='unknown' and checked_not_received is not True:raise HTTPException(422,'请先核查并确认未收到邮件')
        if not eligible(db,notice):raise HTTPException(409,'收件人当前权限、人员关系或申请状态已失效')
        before={'status':mail.status,'attempts':mail.attempts}
        changed=db.execute(update(Mail).where(Mail.id==mail.id,Mail.status==mail.status,
            Mail.status.in_(['failed','unknown','waiting','suppressed'])).values(status='pending',claimed_at=None,
            next_attempt_at=utc_now(),error_message=None))
        if changed.rowcount!=1:raise HTTPException(409,'投递状态已变化或不可重试，请刷新')
        audit(db,mail,before=before,action='retry',actor=current['user_id'],request=request,
            extra={'reason':reason.strip(),'checked_not_received':checked_not_received})
        db.commit();return {'queued':True}
    except Exception:
        db.rollback();raise


def worker(stop,session_factory):
    while not stop.is_set():
        try:
            with session_factory() as db:processed=process_one(db)
        except Exception:
            logging.getLogger(__name__).warning('业务通知邮件处理失败，请检查服务及存储')
            processed=False
        stop.wait(1 if processed else 10)
