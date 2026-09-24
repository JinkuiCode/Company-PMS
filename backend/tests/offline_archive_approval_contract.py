import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.services import offline_archive_approval as approval
from app.schemas.offline_archive import ApprovedImportPayload
class ApprovalContract(unittest.TestCase):
    def setUp(self):
        self.key=patch.object(approval.settings,"SECRET_KEY","isolated-test-key-not-a-real-secret-000");self.key.start()
        self.count=patch.object(approval,"APPROVED_ROW_COUNT",1);self.count.start()
        self.payload={"rows":[{"source_id":"test-row","source_sheet":"test","source_row":2,"values":{"project_code":"TEST","project_name":None}}]}
    def tearDown(self):self.count.stop();self.key.stop()
    def test_signed_payload_roundtrip(self):
        data=ApprovedImportPayload.model_validate(approval.approve_payload(self.payload,approval.APPROVED_FILE_HASH))
        self.assertEqual(approval.verify_payload(data)["rows"][0]["source_id"],"test-row")
    def test_tampering_rejected(self):
        signed=approval.approve_payload(self.payload,approval.APPROVED_FILE_HASH)
        signed["rows"][0]["values"]["project_name"]="tampered"
        with self.assertRaises(HTTPException):approval.verify_payload(ApprovedImportPayload.model_validate(signed))
    def test_other_file_rejected(self):
        with self.assertRaises(HTTPException):approval.approve_payload(self.payload,"0"*64)
    def test_missing_server_key_fails_closed(self):
        with patch.object(approval.settings,"SECRET_KEY",""):
            with self.assertRaises(HTTPException):approval.approve_payload(self.payload,approval.APPROVED_FILE_HASH)
if __name__=="__main__":unittest.main()
