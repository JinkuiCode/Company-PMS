"""Batch-one API contracts, isolated SQLite only; no application lifespan."""
import os
import unittest
from unittest.mock import patch

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SECRET_KEY"] = "isolated-contract-secret-at-least-32-characters"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.models.user import SysUser, RememberToken
from app.models.rbac import SysRole, SysMenu, SysRoleMenu, SysUserRole
from main import app


class UserSecurityContract(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool,
                                    connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.admin = SysUser(username="owner", real_name="管理员", password_hash=hash_password("Lunar.Sky.852"))
        self.db.add(self.admin)
        self.db.flush()
        role = SysRole(role_name="测试", role_code="test", data_scope=4)
        self.db.add(role)
        self.db.flush()
        for code in ("system:user:view", "system:user:add", "system:user:edit", "system:user:reset-password",
                     "system:parameter:view", "system:parameter:edit"):
            menu = SysMenu(menu_name=code, menu_type="B", permission_code=code)
            self.db.add(menu)
            self.db.flush()
            self.db.add(SysRoleMenu(role_id=role.id, menu_id=menu.id))
        self.db.add(SysUserRole(user_id=self.admin.id, role_id=role.id))
        self.db.commit()
        self.role_id = role.id
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        # OA sessions are not subject to local-password enrollment.
        from jose import jwt
        from app.core.config import settings
        payload = jwt.decode(create_access_token(self.admin.id), settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        payload.update(auth_method="oa", credential_version=getattr(self.admin, "credential_version", 0), scope="full")
        self.headers = {"Authorization": "Bearer " + jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def configure(self, value="initial", version=0):
        return self.client.put("/api/parameters/user.initial_password", json={"value": value, "version": version}, headers=self.headers)

    def create(self, **extra):
        return self.client.post("/api/users", json={"username": "E100", "real_name": "员工", **extra}, headers=self.headers)

    def test_parameters_secret_version_and_audit(self):
        response = self.client.get("/api/parameters", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["value"], None)
        self.assertFalse(response.json()["items"][0]["configured"])
        self.assertEqual(self.configure().status_code, 200)
        self.assertEqual(self.configure("other").status_code, 409)
        item = self.client.get("/api/parameters", headers=self.headers).json()["items"][0]
        self.assertEqual((item["version"], item["configured"], item["value"]), (1, True, None))
        from app.models.operation_log import SysOperationLog
        logs = repr([vars(row) for row in self.db.query(SysOperationLog).all()])
        self.assertNotIn("$argon2", logs)
        self.assertNotIn('"value": "initial"', logs)

    def test_create_requires_parameter_and_validates_contract(self):
        self.assertEqual(self.create().status_code, 409)
        self.assertEqual(self.configure().status_code, 200)
        self.assertEqual(self.create(email="bad@").status_code, 422)
        self.assertEqual(self.create(password="disallowed").status_code, 422)
        result = self.create(email="employee@example.com", role_ids=[self.role_id])
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.create().status_code, 409)
        self.assertEqual(self.client.put(f"/api/users/{result.json()['id']}", json={"password": "ignored?"}, headers=self.headers).status_code, 422)
        self.assertEqual(self.db.query(SysUserRole).filter_by(user_id=result.json()["id"]).count(), 1)
        items = self.client.get("/api/users", headers=self.headers).json()["items"]
        self.assertEqual(next(i for i in items if i["username"] == "E100")["email"], "employee@example.com")

    def test_force_change_and_reset_revoke_all_sessions(self):
        self.configure()
        user_id = self.create().json()["id"]
        result = self.client.post("/api/auth/login", json={"username": "E100", "password": "initial", "remember_me": True})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json().get("must_change_password"))
        self.assertIsNone(result.json()["remember_token"])
        limited = {"Authorization": "Bearer " + result.json()["access_token"]}
        self.assertEqual(self.client.get("/api/auth/me", headers=limited).json()["permissions"], [])
        self.assertEqual(self.client.get("/api/my-menus", headers=limited).status_code, 403)
        for weak in ("12345678", "password", "aelsystem", "initial"):
            self.assertEqual(self.client.post("/api/auth/change-password", headers=limited,
                json={"new_password": weak, "confirm_password": weak}).status_code, 422)
        changed = self.client.post("/api/auth/change-password", headers=limited,
            json={"new_password": "Moon852!", "confirm_password": "Moon852!"})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertFalse(changed.json()["must_change_password"])
        normal = {"Authorization": "Bearer " + changed.json()["access_token"]}
        self.assertEqual(self.client.get("/api/auth/me", headers=limited).status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me", headers=normal).status_code, 200)
        reset = self.client.post(f"/api/users/{user_id}/reset-password", headers=self.headers)
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertIn("message", reset.json())
        self.assertEqual(self.client.get("/api/auth/me", headers=normal).status_code, 401)
        old = {"Authorization": "Bearer " + create_access_token(user_id)}
        self.assertEqual(self.client.get("/api/auth/me", headers=old).status_code, 401)

    def test_oa_only_and_password_sso_share_policy(self):
        from app.services.sso import find_or_create_user
        self.db.add(SysRole(role_name="操作员", role_code="operator"))
        self.db.commit()
        with patch("app.services.sso.settings.SSO_AUTO_CREATE_USER", True):
            user = find_or_create_user(self.db, "oa-only", "OA", "")
        self.assertEqual(getattr(user, "local_login_enabled", None), False)
        response = self.client.post("/api/auth/login", json={"username": "oa-only", "password": "sso_placeholder"})
        self.assertEqual(response.status_code, 401)
        self.configure()
        self.create()
        response = self.client.post("/api/sso/oa-password-login", json={"loginid": "E100", "password": "initial", "remember_me": True})
        self.assertTrue(response.json().get("must_change_password"), response.text)
        self.assertIsNone(response.json().get("remember_token"))

    def test_rate_limit_and_oa_options_sqlite(self):
        for _ in range(5):
            self.assertEqual(self.client.post("/api/auth/login", json={"username": "unknown-limit", "password": "bad"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json={"username": "unknown-limit", "password": "bad"}).status_code, 429)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get("/api/users/oa-options", headers=self.headers).status_code, 503)

    def test_legacy_migration_is_idempotent_and_revokes_remember(self):
        from app.models import init_db
        self.assertTrue(hasattr(init_db, "upgrade_user_security"), "security schema migration missing")
        from sqlalchemy import text, inspect
        from app.core.security import verify_password
        legacy = create_engine("sqlite://")
        with legacy.begin() as conn:
            conn.execute(text("CREATE TABLE sys_user (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT)"))
            conn.execute(text("CREATE TABLE sys_remember_token (id INTEGER PRIMARY KEY, user_id INTEGER)"))
            conn.execute(text("INSERT INTO sys_user VALUES (1, 'old-local', :hash), (2, 'old-oa', :oa)"),
                         {"hash": hash_password("legacy-test-password"), "oa": hash_password("sso_placeholder")})
            conn.execute(text("INSERT INTO sys_remember_token VALUES (1, 1)"))
        init_db.upgrade_user_security(legacy)
        init_db.upgrade_user_security(legacy)
        with legacy.connect() as conn:
            rows = conn.execute(text("SELECT must_change_password, local_login_enabled, credential_version, password_hash FROM sys_user ORDER BY id")).all()
            self.assertEqual(rows[0][:3], (1, 1, 1))
            self.assertEqual(rows[1][:3], (0, 0, 1))
            self.assertFalse(verify_password("sso_placeholder", rows[1][3]))
            self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM sys_remember_token")).scalar(), 0)
        legacy.dispose()

    def test_new_permissions_grant_admin_once_only(self):
        from app.models import init_db
        self.assertTrue(hasattr(init_db, "initialize_user_security"), "one-time permissions migration missing")
        admin = SysRole(role_name="管理员", role_code="admin")
        business = SysRole(role_name="业务管理员", role_code="business_admin")
        self.db.add_all([admin, business])
        self.db.commit()
        init_db.initialize_user_security(self.db)
        ids = {row.menu_id for row in self.db.query(SysRoleMenu).filter_by(role_id=admin.id)}
        self.assertEqual(ids, {18, 181, 182, 115})
        self.assertEqual(self.db.get(SysMenu, 18).menu_name, "参数设置")
        self.assertEqual(self.db.query(SysRoleMenu).filter_by(role_id=business.id).count(), 0)
        self.db.query(SysRoleMenu).filter_by(role_id=admin.id, menu_id=182).delete()
        self.db.commit()
        init_db.initialize_user_security(self.db)
        self.assertEqual(self.db.query(SysRoleMenu).filter_by(role_id=admin.id, menu_id=182).count(), 0)
        from app.services.database_revision import CURRENT_DATABASE_REVISION
        self.assertEqual(CURRENT_DATABASE_REVISION, "2026-09-18-03")

    def test_atomic_create_and_reset_log_failure(self):
        self.configure()
        with patch("app.services.rbac.record_operation_log", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.create(role_ids=[self.role_id])
        self.assertIsNone(self.db.query(SysUser).filter_by(username="E100").first())
        user_id = self.create().json()["id"]
        user = self.db.get(SysUser, user_id)
        version = user.credential_version
        with patch("app.services.rbac.record_operation_log", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.client.post(f"/api/users/{user_id}/reset-password", headers=self.headers)
        self.db.refresh(user)
        self.assertEqual(user.credential_version, version)

    def test_reset_permission_disabled_and_remember_revocation(self):
        self.configure()
        user_id = self.create().json()["id"]
        user = self.db.get(SysUser, user_id)
        from datetime import datetime, timedelta
        user.status = 0
        self.db.add(RememberToken(user_id=user_id, token_hash="old", expires_at=datetime.utcnow() + timedelta(days=1)))
        self.db.commit()
        self.assertEqual(self.client.post(f"/api/users/{user_id}/reset-password", headers=self.headers).status_code, 200)
        self.db.refresh(user)
        self.assertEqual(user.status, 0)
        self.assertEqual(self.db.query(RememberToken).filter_by(user_id=user_id).count(), 0)
        self.assertEqual(self.client.post("/api/auth/login", json={"username": "E100", "password": "initial"}).status_code, 403)
        menu = self.db.query(SysMenu).filter_by(permission_code="system:user:reset-password").one()
        self.db.query(SysRoleMenu).filter_by(menu_id=menu.id).delete()
        self.db.commit()
        self.assertEqual(self.client.post(f"/api/users/{user_id}/reset-password", headers=self.headers).status_code, 403)

    def test_argon_unicode_and_bcrypt_legacy(self):
        from app.core.security import verify_password
        import bcrypt
        password = "密" * 40
        digest = hash_password(password)
        self.assertTrue(digest.startswith("$argon2id$"))
        self.assertTrue(verify_password(password, digest))
        self.assertFalse(verify_password(password[:-1] + "码", digest))
        old = bcrypt.hashpw(b"Legacy.123", bcrypt.gensalt()).decode()
        self.assertTrue(verify_password("Legacy.123", old))

    def test_remember_token_is_bound_to_credential_version(self):
        from datetime import datetime, timedelta
        from app.core.security import hash_remember_token
        self.assertIn("credential_version", RememberToken.__table__.columns)
        self.admin.must_change_password = False
        self.admin.credential_version = 2
        self.db.add(RememberToken(user_id=self.admin.id, token_hash=hash_remember_token("stale-token"),
                                 expires_at=datetime.utcnow() + timedelta(days=1), credential_version=1))
        self.db.commit()
        response = self.client.post("/api/auth/auto-login", json={"remember_token": "stale-token"})
        self.assertEqual(response.status_code, 401)

    def test_validation_never_echoes_password_values(self):
        value = "sensitive-" * 10
        result = self.configure(value)
        self.assertEqual(result.status_code, 422)
        self.assertNotIn(value, result.text)

    def test_email_and_labels_in_field_catalog(self):
        from app.services.field_catalog import build_field_catalog
        fields = {row["field_code"]: row for row in build_field_catalog() if row["module"] == "user"}
        self.assertEqual(fields["username"]["field_name"], "账号（工号）")
        self.assertEqual(fields["real_name"]["field_name"], "员工姓名")
        self.assertIn("email", fields)
        self.assertNotIn("password", fields)
        parameters = [row for row in build_field_catalog() if row["module"] == "parameter"]
        self.assertTrue(parameters)

    def test_password_policy_exact_identifiers_not_substrings(self):
        from app.services.password_policy import validate_new_password
        self.admin.username = "a"
        validate_new_password(self.db, self.admin, "Casual82", "Casual82")
        validate_new_password(self.db, self.admin, "金银河test85", "金银河test85")
        validate_new_password(self.db, self.admin, "aelsystem.extra", "aelsystem.extra")
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            validate_new_password(self.db, self.admin, "aelsystem", "aelsystem")

    def test_oa_session_cannot_activate_local_password(self):
        self.admin.local_login_enabled = False
        self.db.commit()
        response = self.client.post("/api/auth/change-password", headers=self.headers,
                                    json={"new_password": "Moon852!", "confirm_password": "Moon852!"})
        self.assertEqual(response.status_code, 403)
        self.db.refresh(self.admin)
        self.assertFalse(self.admin.local_login_enabled)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.headers).status_code, 200)
        self.assertFalse(self.client.get("/api/auth/me", headers=self.headers).json()["must_change_password"])

    def test_limited_session_can_logout(self):
        self.configure()
        self.create()
        response = self.client.post("/api/auth/login", json={"username": "E100", "password": "initial"})
        headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def test_new_audit_fields_have_chinese_labels(self):
        from app.services.operation_log import build_operation_log_diff_items, diff_data
        items = build_operation_log_diff_items(diff_data({"version": 0}, {"version": 1, "configured": True}), entity_type="sys_parameter")
        self.assertEqual({item["field_label"] for item in items}, {"参数版本", "已配置"})
        items = build_operation_log_diff_items(diff_data({}, {"credentials_changed": True}), entity_type="sys_user")
        self.assertEqual(items[0]["field_label"], "凭据已变更")

    def test_registered_nonsecret_parameters_use_storage_and_validator(self):
        from app.models.parameter import SysParameter
        from app.services.parameter import PARAMETERS
        from fastapi import HTTPException
        self.assertIn("value_text", SysParameter.__table__.columns)
        def number(value):
            if not value.isdecimal() or not 1 <= int(value) <= 100:
                raise HTTPException(422, "请输入 1-100 的数字")
            return str(int(value))
        definition = dict(name="测试数量", group="测试", description="仅测试注册", sensitive=False,
                          value_type="number", validator=number)
        with patch.dict(PARAMETERS, {"test.count": definition}):
            url = "/api/parameters/test.count"
            invalid = self.client.put(url, json={"value": "abc", "version": 0}, headers=self.headers)
            self.assertEqual(invalid.status_code, 422)
            saved = self.client.put(url, json={"value": "007", "version": 0}, headers=self.headers)
            self.assertEqual(saved.status_code, 200)
            row = self.db.get(SysParameter, "test.count")
            self.assertEqual(row.value_text, "7")
            self.assertIsNone(row.secret_hash)
            item = next(item for item in self.client.get("/api/parameters", headers=self.headers).json()["items"] if item["code"] == "test.count")
            self.assertEqual(item["value"], "7")
            self.assertTrue(item["configured"])
            self.assertFalse(item["sensitive"])
            self.assertNotIn("validator", item)
        self.assertEqual(self.client.put("/api/parameters/unregistered", json={"value": "a", "version": 0}, headers=self.headers).status_code, 404)

    def test_parameter_storage_additive_upgrade(self):
        from sqlalchemy import text, inspect
        from app.models.init_db import upgrade_user_security
        legacy = create_engine("sqlite://")
        with legacy.begin() as conn:
            conn.execute(text("CREATE TABLE sys_user (id INTEGER PRIMARY KEY, password_hash TEXT, credential_version INTEGER)"))
            conn.execute(text("CREATE TABLE sys_parameter (code TEXT PRIMARY KEY, secret_hash TEXT, version INTEGER)"))
            conn.execute(text("INSERT INTO sys_parameter VALUES ('user.initial_password', 'preserved', 5)"))
        upgrade_user_security(legacy)
        upgrade_user_security(legacy)
        self.assertIn("value_text", {column["name"] for column in inspect(legacy).get_columns("sys_parameter")})
        with legacy.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT secret_hash, version, value_text FROM sys_parameter")).one(), ("preserved", 5, None))
        legacy.dispose()

    def test_parameter_page_is_valid_role_home(self):
        from app.services.role_home import validate_role_home, resolve_home_path
        from fastapi import HTTPException
        root = SysMenu(id=100, menu_name="系统管理", menu_type="M", parent_id=0)
        page = SysMenu(id=101, menu_name="参数设置", menu_type="C", parent_id=100, path="/system/parameter")
        view = SysMenu(id=102, menu_name="查看", menu_type="B", parent_id=101, permission_code="system:parameter:view")
        self.db.add_all([root, page, view])
        role = self.db.get(SysRole, self.role_id)
        role.home_menu_id = 101
        for menu_id in (100, 101, 102):
            self.db.add(SysRoleMenu(role_id=role.id, menu_id=menu_id))
        self.db.commit()
        validate_role_home(self.db, 101, [100, 101, 102])
        self.assertEqual(resolve_home_path(self.db, [role], ["system:parameter:view"]), "/system/parameter")
        with self.assertRaises(HTTPException):
            validate_role_home(self.db, 101, [100, 101])

    def test_signed_redirect_preserves_existing_employee_name(self):
        import time
        from app.services import sso
        self.configure()
        user_id = self.create().json()["id"]
        timestamp = int(time.time())
        with patch.object(sso.settings, "SSO_SECRET_KEY", "isolated-sso-contract-secret"):
            signature = sso._make_sign("E100", "", "", timestamp)
            response = sso.sso_login_by_oa_redirect(self.db, "E100", timestamp, signature)
        self.assertTrue(response["access_token"])
        self.db.expire_all()
        self.assertEqual(self.db.get(SysUser, user_id).real_name, "员工")
        sso.find_or_create_user(self.db, "E100", "", "")
        self.assertEqual(self.db.get(SysUser, user_id).real_name, "员工")
        sso.find_or_create_user(self.db, "E100", "已验证姓名", "")
        self.assertEqual(self.db.get(SysUser, user_id).real_name, "已验证姓名")

    def test_user_input_boundaries_and_trim(self):
        self.configure()
        for invalid in ({"username": "  "}, {"real_name": "  "}, {"username": "x" * 65},
                        {"real_name": "x" * 65}, {"real_name": None}, {"mobile": "1" * 21},
                        {"status": 2}, {"status": None}, {"email": "a" * 250 + "@example.com"}):
            self.assertEqual(self.create(**invalid).status_code, 422, repr(invalid))
        created = self.create(username=" E100 ", real_name=" 员工 ", dept_id=None, mobile=None, email=None)
        self.assertEqual(created.status_code, 200, created.text)
        user_id = created.json()["id"]
        user = self.db.get(SysUser, user_id)
        self.assertEqual((user.username, user.real_name), ("E100", "员工"))
        for invalid in ({"real_name": None}, {"real_name": " "}, {"real_name": "x" * 65},
                        {"mobile": "1" * 21}, {"status": 2}, {"status": None},
                        {"email": "a" * 250 + "@example.com"}):
            result = self.client.put(f"/api/users/{user_id}", json=invalid, headers=self.headers)
            self.assertEqual(result.status_code, 422, repr(invalid))
        # Update schema must retain explicit clearing of optional fields.
        from app.schemas.user import UserUpdate
        update = UserUpdate(real_name=" 新姓名 ", dept_id=None, mobile=None, email=None, status=0)
        self.assertEqual(update.real_name, "新姓名")
        self.assertIsNone(update.dept_id)

    def test_oa_query_is_fixed_parameterized_and_excludes_before_pagination(self):
        from app.services.oa_user_options import get_oa_options, OA_EMPLOYEES
        from unittest.mock import MagicMock
        db = MagicMock()
        db.get_bind.return_value.dialect.name = "mssql"
        db.execute.return_value.scalar_one.return_value = 1
        db.execute.return_value.mappings.return_value.all.return_value = [{"username": "E002", "real_name": "员工"}]
        self.assertEqual(get_oa_options(db, "a%_[~'", 2, 20)["total"], 1)
        sql, params = db.execute.call_args.args
        self.assertEqual(params["pattern"], "%a~%~_~[~~'%")
        self.assertIn("NOT EXISTS", OA_EMPLOYEES)
        self.assertIn("GROUP BY", OA_EMPLOYEES)
        self.assertIn("ecology.dbo.Jinky_Employee", str(sql))
        self.assertEqual(params["department"], "总经理")
        self.assertEqual(params["offset"], 20)


class SecurityReviewContract(unittest.TestCase):
    """Real independent sessions with explicitly scheduled request interleavings."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from app.models.parameter import SysParameter
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.temp.name) / 'review.db'}")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.sessions()
        self.sequence = 0
        self.db.add(SysParameter(code="user.initial_password", secret_hash=hash_password("initial"), version=1))
        admin = SysUser(username="recovery", real_name="恢复管理员", password_hash=hash_password("Recovery.852"))
        role = SysRole(role_name="恢复管理", role_code="recovery", data_scope=4)
        self.db.add_all([admin, role])
        self.db.flush()
        from app.services.rbac import RECOVERY_PERMISSIONS
        for code in RECOVERY_PERMISSIONS:
            menu = SysMenu(menu_name=code, menu_type="B", permission_code=code)
            self.db.add(menu)
            self.db.flush()
            self.db.add(SysRoleMenu(role_id=role.id, menu_id=menu.id))
        self.db.add(SysUserRole(user_id=admin.id, role_id=role.id))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def target(self):
        from app.core.security import user_access_token
        self.sequence += 1
        user = SysUser(username=f"review{self.sequence}", real_name="审查员工", password_hash=hash_password("initial"))
        self.db.add(user)
        self.db.commit()
        return user.id, user_access_token(user)

    def authenticate(self, db, token):
        from app.services.authorization import authenticate_session
        from fastapi.security import HTTPAuthorizationCredentials
        return authenticate_session(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db, allow_change=True)

    def mutate(self, action, user_id):
        from app.services import rbac, auth
        from app.schemas.user import UserUpdate
        with self.sessions() as db:
            if action == "reset":
                rbac.reset_user_password(db, user_id)
            elif action == "logout":
                auth.invalidate_user_tokens(db, user_id)
            elif action == "disable":
                rbac.update_user(db, user_id, UserUpdate(status=0))
            elif action == "disable_local":
                db.query(SysUser).filter_by(id=user_id).update({"local_login_enabled": False})
                db.commit()

    def change(self, db, session):
        from starlette.requests import Request
        from app.api.auth import change_password
        from app.schemas.user import ChangePasswordRequest
        request = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 0),
                           "method": "POST", "path": "/api/auth/change-password", "query_string": b""})
        return change_password(ChangePasswordRequest(new_password="Moon852!", confirm_password="Moon852!"),
                               request, session=session, db=db)

    def test_r2_authenticated_generation_cannot_adopt_prewrite_mutation(self):
        from fastapi import HTTPException
        from app.core.security import verify_password
        for action in ("reset", "logout", "disable", "disable_local"):
            with self.subTest(action=action), self.sessions() as pending:
                user_id, token = self.target()
                session = self.authenticate(pending, token)
                pending.expunge_all()
                self.mutate(action, user_id)
                with self.assertRaises(HTTPException):
                    self.change(pending, session)
                with self.sessions() as check:
                    user = check.get(SysUser, user_id)
                    self.assertFalse(verify_password("Moon852!", user.password_hash))

    def test_r2_update_predicate_checks_enabled_and_local_login(self):
        from fastapi import HTTPException
        from app.services import auth
        original_hash = auth.hash_password
        for action in ("reset", "logout", "disable", "disable_local"):
            with self.subTest(action=action), self.sessions() as pending:
                user_id, token = self.target()
                session = self.authenticate(pending, token)
                def interleave(password):
                    self.mutate(action, user_id)
                    return original_hash(password)
                with patch.object(auth, "hash_password", side_effect=interleave), self.assertRaises(HTTPException):
                    self.change(pending, session)

    def test_r2_token_uses_only_successfully_committed_generation(self):
        from jose import jwt
        from app.core.config import settings
        from fastapi import HTTPException
        for action in ("reset", "logout"):
            with self.subTest(action=action), self.sessions() as pending:
                user_id, token = self.target()
                session = self.authenticate(pending, token)
                original_commit = pending.commit
                def interleave():
                    original_commit()
                    self.mutate(action, user_id)
                with patch.object(pending, "commit", side_effect=interleave):
                    response = self.change(pending, session)
                claims = jwt.decode(response.access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                self.assertEqual(claims["credential_version"], 1)
                self.assertEqual(claims["scope"], "full")
                with self.sessions() as check, self.assertRaises(HTTPException):
                    self.authenticate(check, response.access_token)

    def test_r2_password_update_compiles_for_mssql(self):
        from sqlalchemy.dialects import mssql
        from sqlalchemy.sql.dml import Update
        user_id, token = self.target()
        statements = []
        with self.sessions() as pending:
            session = self.authenticate(pending, token)
            execute = pending.execute
            def capture(statement, *args, **kwargs):
                if isinstance(statement, Update) and statement.table.name == "sys_user":
                    statements.append(str(statement.compile(dialect=mssql.dialect())))
                return execute(statement, *args, **kwargs)
            with patch.object(pending, "execute", side_effect=capture):
                self.change(pending, session)
        self.assertEqual(len(statements), 1)
        self.assertNotRegex(statements[0], r"\bIS\s+1\b")
        self.assertIn("sys_user.local_login_enabled = 1", statements[0])
        self.assertIn("sys_user.credential_version =", statements[0])
        self.assertIn("sys_user.status =", statements[0])

    def test_r3_stale_disable_never_revives_revoked_token(self):
        from app.services import rbac
        from app.schemas.user import UserUpdate
        from app.core.security import user_access_token
        from fastapi import HTTPException
        user_id, _ = self.target()
        with self.sessions() as pending:
            retained = pending.get(SysUser, user_id)
            self.mutate("reset", user_id)
            with self.sessions() as check:
                revoked = user_access_token(check.get(SysUser, user_id), "oa")
            self.mutate("reset", user_id)
            self.assertEqual(retained.credential_version, 0)
            rbac.update_user(pending, user_id, UserUpdate(status=0))
        with self.sessions() as check:
            self.assertEqual(check.get(SysUser, user_id).credential_version, 3)
            rbac.update_user(check, user_id, UserUpdate(status=1))
        with self.sessions() as check, self.assertRaises(HTTPException):
            self.authenticate(check, revoked)

    def test_r3_disable_audit_failure_rolls_back_status_generation_and_tokens(self):
        from app.services import rbac
        from app.schemas.user import UserUpdate
        from datetime import datetime, timedelta
        user_id, _ = self.target()
        self.db.add(RememberToken(user_id=user_id, token_hash="review-remember", expires_at=datetime.utcnow() + timedelta(days=1)))
        self.db.commit()
        with self.sessions() as pending:
            with patch.object(rbac, "record_operation_log", side_effect=RuntimeError("audit interrupted")), self.assertRaises(RuntimeError):
                rbac.update_user(pending, user_id, UserUpdate(status=0))
            # Failure must leave the caller's session reusable, not pending writes.
            self.assertEqual(pending.get(SysUser, user_id).status, 1)
            self.assertEqual(pending.get(SysUser, user_id).credential_version, 0)
            self.assertEqual(pending.query(RememberToken).filter_by(user_id=user_id).count(), 1)

    def test_r3_stale_disabled_object_overrides_concurrent_enable_and_login(self):
        from app.services import rbac, auth
        from app.schemas.user import UserUpdate, LoginRequest
        from fastapi import HTTPException
        user_id, _ = self.target()
        with self.sessions() as setup:
            user = setup.get(SysUser, user_id)
            user.status = 0
            user.must_change_password = False
            setup.commit()
        with self.sessions() as pending:
            stale = pending.get(SysUser, user_id)
            self.assertEqual(stale.status, 0)
            with self.sessions() as concurrent:
                rbac.update_user(concurrent, user_id, UserUpdate(status=1))
                user = concurrent.get(SysUser, user_id)
                logged_in = auth.login(concurrent, LoginRequest(username=user.username, password="initial", remember_me=True))
                self.assertTrue(logged_in.remember_token)
                generation = user.credential_version
            self.assertEqual(stale.status, 0)
            rbac.update_user(pending, user_id, UserUpdate(status=0))
        with self.sessions() as check:
            user = check.get(SysUser, user_id)
            self.assertEqual(user.status, 0)
            self.assertEqual(user.credential_version, generation + 1)
            self.assertEqual(check.query(RememberToken).filter_by(user_id=user_id).count(), 0)
            with self.assertRaises(HTTPException):
                self.authenticate(check, logged_in.access_token)
            with self.assertRaises(HTTPException):
                auth.auto_login(check, logged_in.remember_token)
            rbac.update_user(check, user_id, UserUpdate(status=1))
        with self.sessions() as check, self.assertRaises(HTTPException):
            self.authenticate(check, logged_in.access_token)

    def test_r3_stale_disabled_object_audit_failure_restores_concurrent_login(self):
        from app.services import rbac, auth
        from app.schemas.user import UserUpdate, LoginRequest
        user_id, _ = self.target()
        with self.sessions() as setup:
            user = setup.get(SysUser, user_id)
            user.status = 0
            user.must_change_password = False
            setup.commit()
        with self.sessions() as pending:
            stale = pending.get(SysUser, user_id)
            with self.sessions() as concurrent:
                rbac.update_user(concurrent, user_id, UserUpdate(status=1))
                user = concurrent.get(SysUser, user_id)
                logged_in = auth.login(concurrent, LoginRequest(username=user.username, password="initial", remember_me=True))
                generation = user.credential_version
            self.assertEqual(stale.status, 0)
            original_log = rbac.record_operation_log
            def interrupted(*args, **kwargs):
                self.assertEqual(pending.get(SysUser, user_id).status, 0)
                self.assertEqual(pending.get(SysUser, user_id).credential_version, generation + 1)
                self.assertEqual(pending.query(RememberToken).filter_by(user_id=user_id).count(), 0)
                original_log(*args, **kwargs)
                raise RuntimeError("audit interrupted after write")
            with patch.object(rbac, "record_operation_log", side_effect=interrupted), self.assertRaises(RuntimeError):
                rbac.update_user(pending, user_id, UserUpdate(status=0))
            self.assertEqual(pending.get(SysUser, user_id).status, 1)
            self.assertEqual(pending.get(SysUser, user_id).credential_version, generation)
            self.assertEqual(pending.query(RememberToken).filter_by(user_id=user_id).count(), 1)
        with self.sessions() as check:
            self.assertEqual(self.authenticate(check, logged_in.access_token)["credential_version"], generation)
            self.assertTrue(auth.auto_login(check, logged_in.remember_token).access_token)

    def test_r4_sqlite_interrupted_enrollment_retries_atomically(self):
        from sqlalchemy import text, inspect
        from app.services import user_security_migration as migration
        from app.core.security import verify_password
        for fail_at in (1, 2):
            with self.subTest(fail_at=fail_at):
                legacy = create_engine("sqlite://")
                placeholder = hash_password("sso_placeholder")
                with legacy.begin() as conn:
                    conn.execute(text("CREATE TABLE sys_user (id INTEGER PRIMARY KEY, password_hash TEXT)"))
                    conn.execute(text("CREATE TABLE sys_remember_token (id INTEGER PRIMARY KEY, user_id INTEGER)"))
                    conn.execute(text("INSERT INTO sys_user VALUES (1, :digest), (2, :digest)"), {"digest": placeholder})
                    conn.execute(text("INSERT INTO sys_remember_token VALUES (1, 1), (2, 2)"))
                calls = 0
                def interrupt(value):
                    nonlocal calls
                    calls += 1
                    if calls == fail_at:
                        raise RuntimeError("simulated enrollment interruption")
                    return hash_password(value)
                with patch.object(migration, "hash_password", side_effect=interrupt), self.assertRaises(RuntimeError):
                    migration.upgrade_user_security(legacy)
                migration.upgrade_user_security(legacy)
                with legacy.connect() as conn:
                    rows = conn.execute(text("SELECT local_login_enabled, credential_version, password_hash FROM sys_user ORDER BY id")).all()
                    for enabled, version, digest in rows:
                        self.assertEqual((enabled, version), (0, 1))
                        self.assertFalse(verify_password("sso_placeholder", digest))
                    self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM sys_remember_token")).scalar(), 0)
                # Already-enrolled accounts and fresh generation-0 users are not
                # enrollment candidates on ordinary repeat upgrades.
                with legacy.begin() as conn:
                    conn.execute(text("UPDATE sys_user SET credential_version=7, must_change_password=0 WHERE id=1"))
                    conn.execute(text("INSERT INTO sys_user (id, password_hash, credential_version, must_change_password, local_login_enabled) VALUES (3, :digest, 0, 0, 1)"), {"digest": hash_password("New.Valid.852")})
                    conn.execute(text("INSERT INTO sys_remember_token (id, user_id, credential_version) VALUES (3, 1, 7)"))
                migration.upgrade_user_security(legacy)
                with legacy.connect() as conn:
                    self.assertEqual(conn.execute(text("SELECT credential_version, must_change_password FROM sys_user WHERE id=1")).one(), (7, 0))
                    self.assertEqual(conn.execute(text("SELECT credential_version, must_change_password FROM sys_user WHERE id=3")).one(), (0, 0))
                    self.assertEqual(conn.execute(text("SELECT COUNT(*) FROM sys_remember_token")).scalar(), 1)
                legacy.dispose()

    def test_r6_retained_disabled_roles_allow_edits_disable_and_removal(self):
        from app.services import rbac
        from app.services.authorization import build_authorization_context
        from app.schemas.user import UserUpdate
        from fastapi import HTTPException
        user_id, _ = self.target()
        retained = SysRole(role_name="停用旧角色", role_code="retained", status=0)
        unassigned = SysRole(role_name="停用新角色", role_code="unassigned", status=0)
        self.db.add_all([retained, unassigned])
        self.db.flush()
        self.db.add(SysUserRole(user_id=user_id, role_id=retained.id))
        self.db.commit()
        try:
            rbac.update_user(self.db, user_id, UserUpdate(email="changed@example.com", role_ids=[retained.id]))
        except HTTPException as exc:
            self.fail(f"Unchanged disabled role blocked an unrelated email edit: {exc.status_code}")
        self.assertEqual(self.db.get(SysUser, user_id).email, "changed@example.com")
        self.assertEqual(build_authorization_context(self.db, user_id)["role_codes"], [])
        for ids in ([retained.id, unassigned.id], [99999], [retained.id, retained.id]):
            with self.subTest(ids=ids), self.assertRaises(HTTPException):
                rbac.update_user(self.db, user_id, UserUpdate(role_ids=ids))
        rbac.update_user(self.db, user_id, UserUpdate(status=0, role_ids=[retained.id]))
        self.assertEqual(self.db.get(SysUser, user_id).status, 0)
        self.assertEqual(self.db.query(SysUserRole).filter_by(user_id=user_id).one().role_id, retained.id)
        rbac.update_user(self.db, user_id, UserUpdate(role_ids=[]))
        self.assertEqual(self.db.query(SysUserRole).filter_by(user_id=user_id).count(), 0)
        with self.assertRaises(HTTPException):
            rbac.update_user(self.db, user_id, UserUpdate(role_ids=[retained.id]))

    def test_r5_oa_token_diagnostics_do_not_expose_upstream_body(self):
        import asyncio
        import httpx
        from unittest.mock import AsyncMock
        from app.services import sso
        from fastapi import HTTPException
        canary = "synthetic-oa-credential-canary"
        with patch.object(sso.httpx, "AsyncClient") as constructor, self.assertLogs("app.services.sso", level="INFO") as logs:
            client = constructor.return_value.__aenter__.return_value
            client.post = AsyncMock(return_value=httpx.Response(200, text=canary))
            self.assertEqual(asyncio.run(sso.oa_get_token("review")), canary)
            self.assertEqual(client.post.await_args.kwargs["data"]["loginid"], "review")
            client.post.return_value = httpx.Response(500, text=canary)
            with self.assertRaises(HTTPException) as failure:
                asyncio.run(sso.oa_get_token("review"))
            self.assertEqual(failure.exception.status_code, 401)
            client.post.return_value = httpx.Response(200, text=canary)
            checked = asyncio.run(sso.oa_check_token(canary))
            self.assertEqual(checked, {"valid": False, "raw": canary, "status_code": 200})
            self.assertEqual(client.post.await_args.kwargs["data"]["token"], canary)
            client.get = AsyncMock(return_value=httpx.Response(200, text=canary))
            self.assertEqual(asyncio.run(sso.oa_validate_cas_ticket(canary, "https://example.invalid/callback")),
                             {"raw": canary, "status_code": 200})
            self.assertEqual(client.get.await_args.kwargs["params"]["ticket"], canary)
        self.assertNotIn(canary, str(failure.exception.detail))
        self.assertNotIn(canary, "\n".join(logs.output))

    def test_r5_rest_soap_body_and_exception_diagnostics_are_private(self):
        import asyncio
        import httpx
        from unittest.mock import AsyncMock
        from app.services import sso
        canary = "synthetic-password-canary"
        with patch.object(sso.httpx, "AsyncClient") as constructor, self.assertLogs("app.services.sso", level="INFO") as logs:
            client = constructor.return_value.__aenter__.return_value
            client.post = AsyncMock(return_value=httpx.Response(200, json={"success": True, "credential": canary}))
            self.assertTrue(asyncio.run(sso.oa_verify_password("review", canary)))
            self.assertEqual(client.post.await_args.kwargs["data"]["password"], canary)
            client.post.side_effect = [httpx.Response(200, text=canary),
                                       httpx.Response(200, text=f"<checkUserReturn>true</checkUserReturn>{canary}")]
            self.assertTrue(asyncio.run(sso.oa_verify_password("review", canary)))
            self.assertIn(canary, client.post.await_args.kwargs["content"])
            client.post.side_effect = RuntimeError(canary)
            self.assertFalse(asyncio.run(sso.oa_verify_password("review", canary)))
        self.assertNotIn(canary, "\n".join(logs.output))

    def test_r5_callback_log_hides_ticket_without_changing_call(self):
        import asyncio
        from unittest.mock import AsyncMock
        from app.api import sso
        canary = "synthetic-callback-ticket"
        result = {"access_token": "synthetic-result"}
        with patch.object(sso.sso_service, "handle_oa_callback", new=AsyncMock(return_value=result)) as callback:
            with self.assertLogs("app.api.sso", level="INFO") as logs:
                actual = asyncio.run(sso.sso_oa_callback(ticket=canary, token="", loginid="review", username="review", db=self.db))
            self.assertEqual(actual, result)
            self.assertEqual(callback.await_args.kwargs["ticket"], canary)
            self.assertEqual(callback.await_args.kwargs["loginid"], "review")
        self.assertNotIn(canary, "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
