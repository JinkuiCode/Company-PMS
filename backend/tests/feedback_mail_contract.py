"""SMTP is opt-in; queues remain durable when settings or recipients are missing."""
import importlib
import importlib.util
import json
from unittest.mock import patch
from feedback_service_contract import FeedbackServiceContract
from app.models.feedback import FeedbackNotification
from app.models.parameter import SysParameter
from app.models.rbac import SysRole, SysUserRole
from app.services.parameter import PARAMETERS, list_parameters, update_parameter


class FeedbackMailContract(FeedbackServiceContract):
    def setUp(self):
        super().setUp()
        self.assertIsNotNone(importlib.util.find_spec('app.services.feedback_mail'), 'feedback mail worker is missing')
        self.mail = importlib.import_module('app.services.feedback_mail')

    def configure(self):
        for code, value in {'mail.enabled':'true', 'mail.host':'smtp.example.invalid', 'mail.port':'465', 'mail.security':'ssl', 'mail.sender':'pms@example.invalid'}.items():
            self.db.add(SysParameter(code=code, value_text=value, version=1))
        role = self.db.query(SysRole).filter_by(role_code='admin').first()
        if not role:
            role = SysRole(role_code='admin', role_name='管理员', status=1)
            self.db.add(role)
            self.db.flush()
            # Fixture installed before this role existed; grant it explicitly.
            from app.models.rbac import SysMenu, SysRoleMenu
            for node in self.db.query(SysMenu).filter(SysMenu.permission_code.in_(['feedback:view','feedback:handle'])):
                self.db.add(SysRoleMenu(role_id=role.id, menu_id=node.id))
        self.db.add(SysUserRole(user_id=2, role_id=role.id))
        self.db.commit()

    def test_missing_configuration_does_not_fail_submission_or_claim_success(self):
        row = self.create()
        self.mail.process_one(self.db)
        notice = self.db.query(FeedbackNotification).one()
        self.assertEqual(notice.status, 'waiting')
        self.assertEqual(notice.attempts, 0)
        self.assertEqual(self.service.get_report(self.db, self.owner, row['id'])['status_id'], 1)

    def test_delivery_uses_effective_permission_and_sender_is_called_once(self):
        self.configure()
        self.create()
        with patch.object(self.mail, 'send_mail') as send:
            self.mail.process_one(self.db)
            self.mail.process_one(self.db)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(send.call_args.args[2], ['user2@example.invalid'])
        self.assertEqual(self.db.query(FeedbackNotification).one().status, 'sent')

    def test_missing_recipient_fails_without_transport_and_retry_requires_permission(self):
        self.configure()
        self.create()
        from app.models.rbac import SysMenu, SysRoleMenu
        node = self.db.query(SysMenu).filter_by(permission_code='feedback:handle').one()
        self.db.query(SysRoleMenu).filter_by(menu_id=node.id).delete()
        self.db.commit()
        with patch.object(self.mail, 'send_mail') as send:
            self.mail.process_one(self.db)
            send.assert_not_called()
        notice = self.db.query(FeedbackNotification).one()
        self.assertEqual(notice.status, 'failed')
        with self.assertRaises(Exception):
            self.mail.retry(self.db, self.owner, notice.id)

    def test_password_parameter_is_encrypted_not_returned_or_logged(self):
        self.assertIn('mail.password', PARAMETERS)
        with patch('app.services.secret_encryption.settings') as settings:
            settings.PARAMETER_ENCRYPTION_KEY = 'x' * 48
            settings.SECRET_KEY = 'y' * 48
            update_parameter(self.db, 'mail.password', 'synthetic-mail-credential', 0, 1)
            row = self.db.get(SysParameter, 'mail.password')
            self.assertIsNone(row.value_text)
            self.assertIsNone(row.secret_hash)
            self.assertTrue(row.secret_ciphertext.startswith('v1:'))
            self.assertNotIn('synthetic-mail-credential', list_parameters(self.db).body.decode())
            from app.models.operation_log import SysOperationLog
            logs = self.db.query(SysOperationLog).all()
            self.assertNotIn('synthetic-mail-credential', json.dumps([log.after_data for log in logs]))

    def test_partial_delivery_is_unknown_and_never_automatically_retried(self):
        import smtplib
        self.configure()
        self.create()
        with patch.object(self.mail, 'send_mail', side_effect=smtplib.SMTPException('partial delivery')) as send:
            self.mail.process_one(self.db)
            self.mail.process_one(self.db)
            self.assertEqual(send.call_count, 1)
        self.assertEqual(self.db.query(FeedbackNotification).one().status, 'unknown')

    def test_quit_error_after_acceptance_never_requeues_delivery(self):
        import smtplib
        from unittest.mock import MagicMock
        self.configure()
        self.create()
        smtp = MagicMock()
        smtp.send_message.return_value = {}
        smtp.quit.side_effect = smtplib.SMTPResponseException(451, b'fixture')
        smtp.__enter__.return_value = smtp
        smtp.__exit__.side_effect = smtplib.SMTPResponseException(451, b'fixture')
        with patch.object(self.mail.smtplib, 'SMTP_SSL', return_value=smtp):
            self.mail.process_one(self.db)
            self.mail.process_one(self.db)
        self.assertEqual(smtp.send_message.call_count, 1)
        self.assertEqual(self.db.query(FeedbackNotification).one().status, 'sent')

    def test_approved_internal_transport_can_be_configured_and_loaded(self):
        for code, value in [('mail.host', '10.10.1.150'), ('mail.port', '25'),
                            ('mail.security', 'internal'), ('mail.sender', 'pms@example.invalid'),
                            ('mail.enabled', 'true')]:
            update_parameter(self.db, code, value, 0, 1)
        config = self.mail.configuration(self.db)
        self.assertIsNotNone(config)
        self.assertEqual((config['host'], config['port'], config['security']), ('10.10.1.150', 25, 'internal'))
        options = json.loads(list_parameters(self.db).body)['items']
        security = next(item for item in options if item['code'] == 'mail.security')
        self.assertIn('internal', [item['value'] for item in security['options']])

    def test_internal_transport_parameter_changes_cannot_expand_approved_endpoint(self):
        from fastapi import HTTPException
        for code, value in [('mail.host', '10.10.1.150'), ('mail.port', '25'), ('mail.security', 'internal')]:
            update_parameter(self.db, code, value, 0, 1)
        for code, value in [('mail.host', 'smtp.example.invalid'), ('mail.port', '587')]:
            with self.subTest(code=code), self.assertRaises(HTTPException) as error:
                update_parameter(self.db, code, value, 1, 1)
            self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(self.db.get(SysParameter, 'mail.host').value_text, '10.10.1.150')
        self.assertEqual(self.db.get(SysParameter, 'mail.port').value_text, '25')

    def test_unconfigured_internal_endpoint_is_rejected_before_save(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:
            update_parameter(self.db, 'mail.security', 'internal', 0, 1)
        self.assertEqual(error.exception.status_code, 422)
        self.assertIsNone(self.db.get(SysParameter, 'mail.security'))

    def test_internal_transport_uses_smtp_without_starttls_only_for_approved_endpoint(self):
        from email.message import EmailMessage
        from unittest.mock import MagicMock
        config = {'host':'10.10.1.150', 'port':25, 'security':'internal', 'sender':'pms@example.invalid',
                  'username':'synthetic-user', 'password':'synthetic-credential'}
        smtp = MagicMock()
        smtp.send_message.return_value = {}
        with patch.object(self.mail.smtplib, 'SMTP', return_value=smtp) as plain, patch.object(self.mail.smtplib, 'SMTP_SSL') as secure:
            self.mail.send_mail(config, EmailMessage(), ['user1@example.invalid'])
            plain.assert_called_once_with('10.10.1.150', 25, timeout=20)
            secure.assert_not_called()
            smtp.starttls.assert_not_called()
            smtp.login.assert_called_once_with('synthetic-user', 'synthetic-credential')
            self.assertEqual(smtp.send_message.call_count, 1)

    def test_runtime_policy_rejects_invalid_internal_endpoint_before_network_or_decryption(self):
        from email.message import EmailMessage
        self.configure()
        self.db.get(SysParameter, 'mail.security').value_text = 'internal'
        self.db.get(SysParameter, 'mail.port').value_text = '25'
        self.db.commit()
        with patch.object(self.mail, 'decrypt_secret') as decrypt:
            self.assertIsNone(self.mail.configuration(self.db))
            decrypt.assert_not_called()
        with patch.object(self.mail.smtplib, 'SMTP') as plain, patch.object(self.mail.smtplib, 'SMTP_SSL') as secure:
            with self.assertRaises(ValueError):
                self.mail.send_mail({'host':'smtp.example.invalid', 'port':25, 'security':'internal',
                                     'sender':'pms@example.invalid'}, EmailMessage(), ['user1@example.invalid'])
            plain.assert_not_called()
            secure.assert_not_called()

    def test_starttls_failure_never_falls_back_to_plain_authentication(self):
        import smtplib
        from email.message import EmailMessage
        from unittest.mock import MagicMock
        smtp = MagicMock()
        smtp.starttls.side_effect = smtplib.SMTPNotSupportedError('fixture')
        config = {'host':'smtp.example.invalid', 'port':587, 'security':'starttls',
                  'sender':'pms@example.invalid', 'username':'synthetic-user', 'password':'synthetic-credential'}
        with patch.object(self.mail.smtplib, 'SMTP', return_value=smtp), self.assertRaises(smtplib.SMTPNotSupportedError):
            self.mail.send_mail(config, EmailMessage(), ['user1@example.invalid'])
        smtp.login.assert_not_called()
        smtp.send_message.assert_not_called()


if __name__ == '__main__':
    import unittest
    unittest.main()
