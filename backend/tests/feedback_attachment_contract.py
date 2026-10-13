"""Private attachment validation and scoped downloads."""
import importlib
import importlib.util
import tempfile
from pathlib import Path
from unittest.mock import patch
from feedback_service_contract import FeedbackServiceContract
from fastapi import HTTPException


class FeedbackAttachmentContract(FeedbackServiceContract):
    def setUp(self):
        super().setUp()
        self.assertIsNotNone(importlib.util.find_spec('app.services.feedback_attachments'), 'missing private attachment service')
        self.files = importlib.import_module('app.services.feedback_attachments')
        self.directory = tempfile.TemporaryDirectory()
        self.root = patch.object(self.files, 'storage_root', return_value=Path(self.directory.name))
        self.root.start()

    def tearDown(self):
        if hasattr(self, 'root'):
            self.root.stop()
            self.directory.cleanup()
        super().tearDown()

    def test_private_download_and_five_file_limit(self):
        row = self.create()
        for index in range(5):
            item = self.files.attach(self.db, self.owner, row['id'], index + 1, f'附件{index}.pdf', b'%PDF-1.7\nfixture')
            self.assertNotIn('storage_name', item)
        with self.assertRaises(HTTPException):
            self.files.attach(self.db, self.owner, row['id'], 6, '过多.pdf', b'%PDF-1.7\nfixture')
        with self.assertRaises(HTTPException) as denied:
            self.files.download(self.db, self.other, item['id'])
        self.assertEqual(denied.exception.status_code, 404)
        path, filename, mime = self.files.download(self.db, self.owner, item['id'])
        self.assertTrue(path.is_file())
        self.assertEqual(mime, 'application/pdf')

    def test_extension_spoofing_traversal_size_and_conflict_rejected(self):
        row = self.create()
        for filename, body in [('x.png', b'<html>'), ('../x.pdf', b'%PDF-1.7'), ('x.exe', b'MZ'), ('x.pdf', b'x' * (10 * 1024 * 1024 + 1))]:
            with self.subTest(filename=filename), self.assertRaises(HTTPException):
                self.files.attach(self.db, self.owner, row['id'], 1, filename, body)
        with self.assertRaises(HTTPException) as conflict:
            self.files.attach(self.db, self.owner, row['id'], 2, 'x.pdf', b'%PDF-1.7\nfixture')
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_add_only_permission_uploads_only_initial_submission_attachments(self):
        from datetime import datetime, timedelta
        from app.models.feedback import FeedbackReport
        row = self.create()
        creator = {'user_id':1, 'permissions':['feedback:view','feedback:add']}
        with self.assertRaises(HTTPException):
            self.files.attach(self.db, creator, row['id'], 1, 'x.pdf', b'%PDF-1.7\nfixture')
        self.files.attach(self.db, creator, row['id'], 1, 'x.pdf', b'%PDF-1.7\nfixture', submission_id=self.payload.submission_id)
        report = self.db.get(FeedbackReport, row['id'])
        report.created_at = datetime.utcnow() - timedelta(hours=1)
        self.db.commit()
        with self.assertRaises(HTTPException):
            self.files.attach(self.db, creator, row['id'], 2, 'y.pdf', b'%PDF-1.7\nfixture', submission_id=self.payload.submission_id)

    def test_upload_cannot_predict_next_version_to_bypass_authorized_snapshot(self):
        from app.models.feedback import FeedbackReport
        row = self.create()
        creator = {'user_id':1, 'permissions':['feedback:view','feedback:add']}
        original_execute = self.db.execute
        def interleaved_execute(statement, *args, **kwargs):
            if getattr(statement, 'is_update', False):
                report = self.db.get(FeedbackReport, row['id'])
                report.status_id, report.version = 5, 2
                self.db.commit()
            return original_execute(statement, *args, **kwargs)
        with patch.object(self.db, 'execute', side_effect=interleaved_execute), self.assertRaises(HTTPException) as error:
            self.files.attach(self.db, creator, row['id'], 2, 'x.pdf', b'%PDF-1.7\nfixture', submission_id=self.payload.submission_id)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])


if __name__ == '__main__':
    import unittest
    unittest.main()
