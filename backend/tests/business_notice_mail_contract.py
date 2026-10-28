"""SMTP is always mocked; include real SQLite CAS competition."""
import unittest
from unittest.mock import patch
from datetime import timedelta
import smtplib
import tempfile
from pathlib import Path
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException
from business_notice_contract import Notices
from app.models.business_notice import BusinessNotice, BusinessNoticeMail as Mail, utc_now
from app.models.operation_log import SysOperationLog
from app.models.rbac import SysMenu, SysRoleMenu
from app.services import business_notice_mail as delivery
from app.services import business_notices as notices
from app.core.config import settings

class NoticeMail(unittest.TestCase):
    setUp = Notices.setUp
    tearDown = Notices.tearDown
    actor = Notices.actor
    snapshot = Notices.snapshot
    payload = Notices.payload
    submit = Notices.submit
    decide = Notices.decide

    def queued(self):
        self.head.email='head@example.invalid';self.owner.email='owner@example.invalid';self.db.commit()
        result=self.submit(project_name='审批中的名称')
        return self.db.query(Mail).one(),result

    def process(self, side_effect=None, config=True):
        with patch.object(delivery,'configuration',return_value={'sender':'pms@example.invalid'} if config else None), patch.object(delivery,'send_mail',side_effect=side_effect) as send:
            processed=delivery.process_one(self.db)
        return processed,send

    def grants(self,*codes):
        for code in codes:
            node=SysMenu(menu_name=code,menu_type='B',permission_code=code);self.db.add(node);self.db.flush()
            self.db.add(SysRoleMenu(role_id=self.roles[self.other.id].id,menu_id=node.id))
        self.db.commit()

    def test_acceptance_is_not_read_and_minimal_body_uses_trusted_url(self):
        mail,result=self.queued()
        with patch.object(settings,'PMS_FRONTEND_URL','https://pms.example.invalid'):
            _,send=self.process()
        self.assertEqual(mail.status,'accepted');self.assertEqual(mail.attempts,1)
        self.assertIsNone(self.db.get(BusinessNotice,mail.notice_id).read_at)
        message=send.call_args.args[1];text=message.get_content()
        self.assertIn(f'/project/archive?change_id={result["id"]}',text)
        self.assertIn('https://pms.example.invalid',text)
        self.assertNotIn('审批中的名称',text) # pending value is not the current project name
        self.assertNotIn('differences',text)
        self.assertEqual(message['Message-ID'],f'<pms-archive-notice-{mail.notice_id}@pms.internal>')
        _,again=self.process();again.assert_not_called()

    def test_no_email_does_not_undo_request(self):
        mail,result=self.queued();self.head.email=None;self.db.commit()
        _,send=self.process();send.assert_not_called()
        self.assertEqual(mail.status,'failed');self.assertEqual(self.db.get(self.Change,result['id']).status,2)
        self.assertEqual(self.db.query(BusinessNotice).count(),1)

    def test_recipient_cannot_contain_address_list_delimiters(self):
        mail,_=self.queued();self.head.email='head,other@example.invalid';self.db.commit()
        _,send=self.process();send.assert_not_called();self.assertEqual(mail.status,'failed')

    def test_config_disabled_retains_queue_without_send_attempt(self):
        mail,_=self.queued();_,send=self.process(config=False)
        self.assertEqual(mail.status,'waiting');self.assertEqual(mail.attempts,0);send.assert_not_called()

    def test_withdrawn_and_completed_pending_mail_are_suppressed(self):
        mail,result=self.queued()
        self.client.post(f"/api/projects/archive-changes/requests/{result['id']}/withdraw",json={'expected_version':1})
        _,send=self.process();self.assertEqual(mail.status,'suppressed');send.assert_not_called()
        self.assertEqual(self.db.query(Mail).count(),1)

    def test_rejection_suppresses_todo_and_sends_author_without_opinion(self):
        mail,result=self.queued();self.decide(result,'reject');_,old=self.process();old.assert_not_called()
        self.assertEqual(mail.status,'suppressed')
        _,send=self.process();self.assertEqual(send.call_args.args[2],['owner@example.invalid'])
        self.assertNotIn('业务意见',send.call_args.args[1].get_content())

    def test_live_role_revocation_and_route_change_stop_mail(self):
        mail,_=self.queued();self.roles[self.head.id].status=0;self.db.commit()
        _,send=self.process();self.assertEqual(mail.status,'suppressed');send.assert_not_called()

    def test_permission_change_during_configuration_is_rechecked(self):
        mail,_=self.queued()
        def changed(db):
            self.dept.leader_id=self.other.id;db.commit();return {'sender':'pms@example.invalid'}
        with patch.object(delivery,'configuration',side_effect=changed),patch.object(delivery,'send_mail') as send:
            delivery.process_one(self.db)
        send.assert_not_called();self.assertEqual(mail.status,'suppressed')

    def test_definite_4xx_is_bounded_to_three_attempts(self):
        mail,_=self.queued()
        for attempt in range(1,4):
            mail.next_attempt_at=utc_now()-timedelta(seconds=1);self.db.commit()
            _,send=self.process(smtplib.SMTPDataError(450,b'refused'))
            send.assert_called_once();self.assertEqual(mail.attempts,attempt)
        self.assertEqual(mail.status,'failed')
        _,send=self.process();send.assert_not_called()

    def test_unknown_outcome_and_interrupted_processing_never_auto_retry(self):
        mail,_=self.queued();_,send=self.process(TimeoutError('not safe to replay'))
        self.assertEqual(mail.status,'unknown');_,send=self.process();send.assert_not_called()
        mail.status='processing';mail.claimed_at=utc_now()-timedelta(minutes=11);self.db.commit()
        _,send=self.process();send.assert_not_called();self.assertEqual(mail.status,'unknown')
        self.assertGreaterEqual(self.db.query(SysOperationLog).filter_by(entity_type='pms_business_notice_mail',action='mail_delivery').count(),2)

    def test_smtp_acceptance_before_log_failure_stays_uncertain(self):
        mail,_=self.queued()
        with patch.object(delivery,'record_operation_log',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):self.process()
        self.db.rollback();self.db.refresh(mail);self.assertEqual(mail.status,'processing')
        _,send=self.process();send.assert_not_called()
        mail.claimed_at=utc_now()-timedelta(minutes=11);self.db.commit()
        _,send=self.process();self.assertEqual(mail.status,'unknown');send.assert_not_called()

    def test_retry_needs_permissions_reason_confirmation_and_live_recipient(self):
        mail,_=self.queued();self.process(TimeoutError())
        context={'user_id':self.other.id}
        with self.assertRaises(HTTPException):delivery.retry(self.db,context,mail.id,reason='核查')
        self.grants(notices.MANAGE,notices.RETRY)
        with self.assertRaises(HTTPException):delivery.retry(self.db,context,mail.id,reason='')
        with self.assertRaises(HTTPException):delivery.retry(self.db,context,mail.id,reason='核查')
        self.assertEqual(delivery.retry(self.db,context,mail.id,reason='已核查未收到',checked_not_received=True),{'queued':True})
        self.assertEqual(self.db.query(Mail).count(),1);self.assertEqual(self.db.query(BusinessNotice).count(),1)
        self.assertEqual(self.db.query(SysOperationLog).filter_by(entity_type='pms_business_notice_mail',action='retry').count(),1)
        self.process();self.assertEqual(mail.status,'accepted')
        with self.assertRaises(HTTPException):delivery.retry(self.db,context,mail.id,reason='不允许重发',checked_not_received=True)

    def test_management_respects_scope_and_retry_rechecks_eligibility(self):
        mail,_=self.queued();self.process(TimeoutError());self.grants(notices.MANAGE,notices.RETRY)
        context={'user_id':self.other.id};self.assertEqual(delivery.list_deliveries(self.db,context,1)['total'],1)
        self.roles[self.other.id].data_scope=1;self.db.commit()
        with self.assertRaises(HTTPException):delivery.list_deliveries(self.db,context,1)
        self.roles[self.other.id].data_scope=4;self.head.status=0;self.db.commit()
        with self.assertRaises(HTTPException):delivery.retry(self.db,context,mail.id,reason='核查',checked_not_received=True)

    def test_untrusted_url_falls_back_to_page_path(self):
        _,_=self.queued()
        with patch.object(settings,'PMS_FRONTEND_URL','https://user:secret@evil.invalid/path?x=token'):
            _,send=self.process()
        text=send.call_args.args[1].get_content();self.assertNotIn('evil.invalid',text);self.assertNotIn('secret',text)
        self.assertIn('/project/archive?change_id=',text)

    def test_two_workers_claim_only_once(self):
        self.queued();self.db.commit()
        with tempfile.TemporaryDirectory() as directory:
            filename=Path(directory)/'cas.db'
            target=sqlite3.connect(filename)
            self.db.connection().connection.driver_connection.backup(target);target.close()
            engine=create_engine(f'sqlite:///{filename}',connect_args={'check_same_thread':False,'timeout':10})
            start=Barrier(2)
            def run():
                start.wait()
                with Session(engine) as db:return delivery.process_one(db)
            with patch.object(delivery,'configuration',return_value={'sender':'pms@example.invalid'}),patch.object(delivery,'send_mail') as send,ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(run) for _ in range(2)]
                [future.result(timeout=15) for future in futures]
                self.assertEqual(send.call_count,1)
            with Session(engine) as db:self.assertEqual(db.query(Mail).one().status,'accepted')
            engine.dispose()

if __name__=='__main__':unittest.main(defaultTest='NoticeMail')
