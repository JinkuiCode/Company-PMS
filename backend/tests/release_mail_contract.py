import sys
import unittest
import smtplib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_center_contract as fixture
from app.models.release import PmsReleaseMail, PmsReleaseNotice
from app.services import release_mail


class ReleaseMail(unittest.TestCase):
    actor = fixture.Releases.actor
    setUp = fixture.Releases.setUp
    tearDown = fixture.Releases.tearDown
    publish = fixture.Releases.publish

    def prepare(self):
        self.owner.email = 'fixture@example.invalid'; self.db.commit()
        self.publish()
        notice = self.db.query(PmsReleaseNotice).filter_by(user_id=self.owner.id).one()
        row = self.db.query(PmsReleaseMail).filter_by(notice_id=notice.id).one()
        self.db.query(PmsReleaseMail).filter(PmsReleaseMail.id != row.id).delete(); self.db.commit()
        return notice, row

    def process(self, error=None):
        with patch.object(release_mail, 'configuration', return_value={'sender': 'pms@example.invalid'}), patch.object(release_mail, 'send_mail', side_effect=error) as send:
            self.assertTrue(release_mail.process_one(self.db))
            return send

    def test_server_acceptance_does_not_mark_inapp_notice_read(self):
        notice, row = self.prepare()
        send = self.process(); self.db.refresh(row)
        self.assertEqual(row.status, 'accepted'); self.assertIsNotNone(row.accepted_at)
        self.assertIsNone(notice.read_at); self.assertEqual(send.call_count, 1)
        content = send.call_args.args[1].get_content()
        self.assertIn('v1.0.0', content); self.assertIn('查看字段变化', content)

    def test_unknown_delivery_is_never_automatically_retried(self):
        _, row = self.prepare()
        self.process(OSError('network interrupted')); self.db.refresh(row)
        self.assertEqual(row.status, 'unknown')
        with patch.object(release_mail, 'send_mail') as send:
            self.assertFalse(release_mail.process_one(self.db)); send.assert_not_called()

    def test_known_temporary_refusal_has_bounded_retry(self):
        _, row = self.prepare(); row.attempts = 2; self.db.commit()
        self.process(smtplib.SMTPDataError(451, b'temporary')); self.db.refresh(row)
        self.assertEqual(row.status, 'failed'); self.assertEqual(row.attempts, 3)

    def test_missing_email_preserves_personal_notice(self):
        notice, row = self.prepare(); self.owner.email = None; self.db.commit()
        send = self.process(); self.db.refresh(row)
        self.assertEqual(row.status, 'failed'); send.assert_not_called()
        self.assertIsNotNone(self.db.get(PmsReleaseNotice, notice.id))

    def test_mail_configuration_off_does_not_send(self):
        _, row = self.prepare()
        with patch.object(release_mail, 'configuration', return_value=None), patch.object(release_mail, 'send_mail') as send:
            release_mail.process_one(self.db); send.assert_not_called()
        self.db.refresh(row); self.assertEqual(row.status, 'waiting')


if __name__ == '__main__': unittest.main()
