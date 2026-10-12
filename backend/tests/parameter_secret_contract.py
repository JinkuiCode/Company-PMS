"""Initial-password reveal contracts; synthetic keys and isolated SQLite only."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
import app.models.init_db
from app.api.parameters import router
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import hash_password, verify_password
from app.models.operation_log import SysOperationLog
from app.models.parameter import SysParameter
from app.services.authorization import get_current_user_context
from app.services.parameter import INITIAL_PASSWORD, PARAMETERS, initial_password_hash

FIXTURE = "synthetic-only-initial-82"


class ParameterSecretContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.context = {"user_id": 1, "permissions": ["system:parameter:view", "system:parameter:edit"]}
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user_context] = lambda: self.context
        self.client = TestClient(app)
        self.key = patch.object(settings, "SECRET_KEY", "synthetic-key-for-contract-at-least-32-characters")
        self.key.start()
        self.addCleanup(self.key.stop)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def save(self, value=FIXTURE, version=0, code=INITIAL_PASSWORD):
        return self.client.put(f"/api/parameters/{code}", json={"value": value, "version": version})

    def item(self, code=INITIAL_PASSWORD):
        response = self.client.get("/api/parameters")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        return next(item for item in response.json()["items"] if item["code"] == code)

    def test_new_value_reveals_but_database_and_audit_never_store_plaintext(self):
        response = self.save()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(FIXTURE, response.text)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        item = self.item()
        self.assertEqual((item["value"], item["reveal_status"]), (FIXTURE, "available"))
        self.assertNotIn("secret_ciphertext", item)
        row = self.db.get(SysParameter, INITIAL_PASSWORD)
        self.assertIsNone(row.value_text)
        self.assertNotIn(FIXTURE, row.secret_ciphertext)
        self.assertTrue(verify_password(FIXTURE, initial_password_hash(self.db)))
        logs = repr([vars(row) for row in self.db.query(SysOperationLog).all()])
        self.assertNotIn(FIXTURE, logs)
        self.assertNotIn(row.secret_ciphertext, logs)
        self.assertNotIn(row.secret_hash, logs)

    def test_legacy_hash_is_preserved_and_explicitly_requires_resave(self):
        hashed = hash_password(FIXTURE)
        self.db.add(SysParameter(code=INITIAL_PASSWORD, secret_hash=hashed, version=7))
        self.db.commit()
        item = self.item()
        self.assertEqual((item["value"], item["reveal_status"], item["configured"]), (None, "legacy", True))
        self.assertIn("重新保存", item["reveal_message"])
        self.assertEqual(initial_password_hash(self.db), hashed)
        self.assertEqual(self.save(version=7).status_code, 200)
        self.assertEqual(self.item()["value"], FIXTURE)

    def test_edit_permission_does_not_grant_read_and_revocation_blocks_next_request(self):
        self.assertEqual(self.save().status_code, 200)
        self.context["permissions"] = ["system:parameter:edit", "business:data:all"]
        response = self.client.get("/api/parameters")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(FIXTURE, response.text)
        self.context["permissions"] = ["system:parameter:view"]
        self.assertEqual(self.item()["value"], FIXTURE)
        self.assertEqual(self.save(version=1).status_code, 403)
        self.context["permissions"] = []
        self.assertEqual(self.client.get("/api/parameters").status_code, 403)

    def test_other_sensitive_parameters_stay_hash_only(self):
        definition = dict(name="Synthetic", group="Test", description="Fixture", sensitive=True, value_type="text")
        with patch.dict(PARAMETERS, {"test.secret": definition}):
            self.assertEqual(self.save(code="test.secret").status_code, 200)
            item = self.item("test.secret")
            self.assertIsNone(item["value"])
            self.assertEqual(item["reveal_status"], "hidden")
            self.assertIsNone(self.db.get(SysParameter, "test.secret").secret_ciphertext)

    def test_tampered_or_rotated_key_fails_closed_without_breaking_hash_consumers(self):
        self.assertEqual(self.save().status_code, 200)
        with patch.object(settings, "SECRET_KEY", "other-synthetic-key-at-least-32-characters"):
            item = self.item()
            self.assertEqual((item["value"], item["reveal_status"]), (None, "unavailable"))
            self.assertTrue(verify_password(FIXTURE, initial_password_hash(self.db)))
        row = self.db.get(SysParameter, INITIAL_PASSWORD)
        row.secret_ciphertext = "v1:shared:not-valid-ciphertext"
        self.db.commit()
        self.assertEqual(self.item()["reveal_status"], "unavailable")

    def test_missing_key_refuses_save_without_partial_hash_or_audit(self):
        with patch.object(settings, "SECRET_KEY", ""), patch.dict(settings.__dict__, {"PARAMETER_ENCRYPTION_KEY": ""}):
            response = self.save()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(FIXTURE, response.text)
        self.assertIsNone(self.db.get(SysParameter, INITIAL_PASSWORD))
        self.assertEqual(self.db.query(SysOperationLog).count(), 0)

    def test_conflict_preserves_both_hash_and_encrypted_value(self):
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(self.save("synthetic-next-value", 0).status_code, 409)
        self.assertEqual(self.item()["value"], FIXTURE)
        self.assertTrue(verify_password(FIXTURE, initial_password_hash(self.db)))

    def test_old_binary_password_update_does_not_reveal_stale_ciphertext(self):
        self.assertEqual(self.save().status_code, 200)
        row = self.db.get(SysParameter, INITIAL_PASSWORD)
        row.secret_hash = hash_password("synthetic-changed-during-rollback")
        row.version += 1
        self.db.commit()
        item = self.item()
        self.assertEqual((item["value"], item["reveal_status"]), (None, "unavailable"))
        self.assertIn("重新保存", item["reveal_message"])
        self.assertTrue(verify_password("synthetic-changed-during-rollback", initial_password_hash(self.db)))
        self.assertEqual(self.save(version=2).status_code, 200)
        self.assertEqual(self.item()["value"], FIXTURE)

    def test_authenticated_encryption_randomizes_and_binds_parameter_identity(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec("app.services.secret_encryption"), "Missing authenticated encryption helper")
        from app.services import secret_encryption
        first = secret_encryption.encrypt_secret(FIXTURE, INITIAL_PASSWORD)
        second = secret_encryption.encrypt_secret(FIXTURE, INITIAL_PASSWORD)
        self.assertNotEqual(first, second)
        self.assertEqual(secret_encryption.decrypt_secret(first, INITIAL_PASSWORD), FIXTURE)
        with self.assertRaises(secret_encryption.SecretEncryptionError):
            secret_encryption.decrypt_secret(first, "other.parameter")
        with patch.dict(settings.__dict__, {"PARAMETER_ENCRYPTION_KEY": "dedicated-synthetic-key-at-least-32-characters"}):
            dedicated = secret_encryption.encrypt_secret(FIXTURE, INITIAL_PASSWORD)
            with patch.object(settings, "SECRET_KEY", "changed-jwt-synthetic-key-at-least-32-characters"):
                self.assertEqual(secret_encryption.decrypt_secret(dedicated, INITIAL_PASSWORD), FIXTURE)
        with self.assertRaises(secret_encryption.SecretEncryptionError):
            secret_encryption.decrypt_secret(dedicated, INITIAL_PASSWORD)

    def test_ciphertext_field_is_in_readonly_catalog(self):
        from app.services.field_catalog import build_field_catalog
        fields = {row["field_code"]: row for row in build_field_catalog() if row["module"] == "parameter"}
        self.assertIn("secret_ciphertext", fields)
        self.assertFalse(fields["secret_ciphertext"]["editable"])
        self.assertEqual(fields["secret_ciphertext"]["field_name"], "参数认证密文")


if __name__ == "__main__":
    unittest.main()
