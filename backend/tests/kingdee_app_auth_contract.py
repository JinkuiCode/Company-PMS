"""应用认证行为契约；仅使用假凭据与 httpx 内存传输，不访问金蝶。"""
import base64
import io
import json
import logging
import os
import runpy
import sys
import subprocess
import tempfile
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = ":memory:"

import httpx
from app.core.config import Settings
from app.services import kingdee


def config(**overrides):
    values = dict(K3_URL="http://kingdee.invalid/k3cloud", K3_ACCT_ID="test-acct",
                  K3_USERNAME="test-user", K3_PASSWORD="test-password",
                  K3_AUTH_MODE="app", K3_APP_ID="123_" + "A" * 32,
                  K3_APP_SECRET="test-app-secret", K3_LCID=2052, K3_ORG_NUM=0, K3_READ_ONLY=False)
    return SimpleNamespace(**(values | overrides))


@contextmanager
def client_with(handler, **overrides):
    with patch.object(kingdee, "settings", config(**overrides)):
        client = kingdee.KingdeeClient()
        client.client.close()
        client.client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            yield client
        finally:
            client.close()


def test_app_connection_makes_signed_read_only_request():
    seen = []
    def handle(req):
        seen.append(req)
        assert "ValidateUser" not in str(req.url)
        assert "ExecuteBillQuery" in str(req.url)
        assert req.headers["X-Kd-Appkey"] == config().K3_APP_ID
        assert req.headers["X-Kd-Signature"]
        assert req.headers["X-Api-Signature"]
        assert base64.b64decode(req.headers["X-Kd-Appdata"]).decode() == "test-acct,test-user,2052,0"
        assert "test-password" not in req.content.decode()
        assert "test-app-secret" not in str(req.headers)
        query = json.loads(json.loads(req.content)["data"])
        assert query["FilterString"] == "1=0"
        assert query["Limit"] == 1
        return httpx.Response(200, json=[])
    with client_with(handle) as client:
        assert client.login() is True
    assert len(seen) == 1


def test_app_rejection_never_falls_back_to_password():
    seen = []
    def handle(req):
        seen.append(req)
        return httpx.Response(200, json={"Result": {"ResponseStatus": {"IsSuccess": False}}})
    with client_with(handle) as client:
        assert client.login() is False
    assert len(seen) == 1
    assert "ValidateUser" not in str(seen[0].url)


def test_missing_or_invalid_auth_config_does_not_send():
    seen = []
    def forbidden(req):
        seen.append(req)
        raise AssertionError("invalid credentials must not send requests")
    for fields in ({"K3_APP_SECRET": ""}, {"K3_APP_ID": ""},
                   {"K3_USERNAME": ""}, {"K3_AUTH_MODE": "unknown"}):
        with client_with(forbidden, **fields) as client:
            assert client.login() is False
    assert seen == []


def test_password_rollback_is_explicit():
    def handle(req):
        assert "ValidateUser" in str(req.url)
        assert "X-Kd-Signature" not in req.headers
        assert json.loads(req.content)["password"] == "test-password"
        return httpx.Response(200, json={"LoginResultType": 1})
    with client_with(handle, K3_AUTH_MODE="password") as client:
        assert client.login() is True


def test_readonly_mode_blocks_save_before_any_network_request():
    requests = []
    def handle(req):
        requests.append(req)
        return httpx.Response(200, json={"Result": {"ResponseStatus": {"IsSuccess": True}}})
    for mode in ("app", "password"):
        with client_with(handle, K3_AUTH_MODE=mode, K3_READ_ONLY=True) as client:
            result = client.save_assistant_data("BOS_ASSISTANTDATA_DETAIL", "xsxm", "TEST", "测试")
            assert result["success"] is False
            assert "只读" in result["message"]
    assert requests == []


def test_query_rejection_is_not_absence():
    for response in ({"Result": {"ResponseStatus": {"IsSuccess": False}}},
                     [{"Result": {"ResponseStatus": {"IsSuccess": False}}}],
                     [[{"Result": {"ResponseStatus": {"IsSuccess": False}}}]], [[1]]):
        with client_with(lambda req: httpx.Response(200, json=response)) as client:
            try:
                client.query_assistant_data("BOS_ASSISTANTDATA_DETAIL", "xsxm", "TEST")
            except RuntimeError:
                pass
            else:
                raise AssertionError("query rejection must stop sync before Save")


def test_signed_query_and_save_preserve_payload_and_never_retry():
    seen = []
    def handle(req):
        seen.append(req)
        assert req.headers["X-Kd-Signature"]
        if "ExecuteBillQuery" in str(req.url):
            return httpx.Response(200, json=[[42, "TEST", "测试"]])
        body = json.loads(req.content)
        assert body["formid"] == "BOS_ASSISTANTDATA_DETAIL"
        data = json.loads(body["data"])
        assert data["Model"]["FEntryID"] == "42"
        assert data["Model"]["FId"]["FNumber"] == "xsxm"
        assert data["NeedUpDateFields"] == ["FDataValue", "FDescription"]
        raise httpx.ReadTimeout("uncertain response")
    with client_with(handle) as client:
        existing = client.query_assistant_data("BOS_ASSISTANTDATA_DETAIL", "xsxm", "TEST")
        assert existing is not None
        assert existing["FEntryID"] == 42
        try:
            client.save_assistant_data("BOS_ASSISTANTDATA_DETAIL", "xsxm", "TEST", "测试", entry_id="42")
        except kingdee.KingdeeSaveOutcomeAmbiguous:
            pass
        else:
            raise AssertionError("save timeout must retain ambiguous result")
    assert len(seen) == 2


def test_auth_exception_does_not_disclose_credentials():
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    kingdee.logger.addHandler(handler)
    def fail(req):
        raise RuntimeError("test-app-secret test-password sensitive-signature")
    try:
        with client_with(fail) as client:
            assert client.login() is False
    finally:
        kingdee.logger.removeHandler(handler)
    assert "test-app-secret" not in output.getvalue()
    assert "test-password" not in output.getvalue()
    assert "sensitive-signature" not in output.getvalue()


def test_save_failures_do_not_disclose_credentials_or_transport_details():
    for response_kind in ("transport", "malformed", "business"):
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        previous_level = kingdee.logger.level
        kingdee.logger.setLevel(logging.INFO)
        kingdee.logger.addHandler(handler)
        leak = "test-app-secret test-password sensitive-signature"
        def handle(req):
            if response_kind == "transport":
                raise httpx.ReadTimeout(leak)
            if response_kind == "malformed":
                return httpx.Response(200, json={"error": leak})
            return httpx.Response(200, json={"Result": {"ResponseStatus": {
                "IsSuccess": False, "Errors": [{"Message": "业务拒绝 test-app-secret test-password"}],
            }}})
        try:
            with client_with(handle) as client:
                try:
                    result = client.save_assistant_data("BOS_ASSISTANTDATA_DETAIL", "xsxm", "TEST", "测试")
                    assert response_kind == "business"
                    assert result["success"] is False and "业务拒绝" in result["message"]
                    public = result["message"]
                except kingdee.KingdeeSaveOutcomeAmbiguous as exc:
                    assert response_kind != "business"
                    public = str(exc)
        finally:
            kingdee.logger.removeHandler(handler)
            kingdee.logger.setLevel(previous_level)
        for secret in ("test-app-secret", "test-password", "sensitive-signature"):
            assert secret not in public + output.getvalue(), "save path leaked sensitive content"


def test_connection_helper_handles_constructor_errors_without_disclosure():
    with patch.object(
        kingdee,
        "KingdeeClient",
        side_effect=RuntimeError("test-app-secret test-password sensitive-signature"),
    ):
        result = kingdee.test_erp_connection()
    assert result == {
        "success": False,
        "message": "金蝶连接异常，请检查认证与连接配置",
    }


def test_environment_overrides_file_and_defaults_have_no_password():
    with patch.dict(os.environ, {}, clear=True):
        defaults = Settings(_env_file=None)
        assert defaults.K3_PASSWORD == ""
        assert defaults.K3_APP_SECRET == ""
        assert defaults.K3_READ_ONLY is True
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env.local"
            env.write_text('K3_AUTH_MODE=app\nK3_USERNAME=file-user\nK3_APP_SECRET=test-file-secret\n')
            assert Settings(_env_file=env).K3_USERNAME == "file-user"
            assert "test-file-secret" not in repr(Settings(_env_file=env))
            os.environ["K3_USERNAME"] = "replacement-user"
            assert Settings(_env_file=env).K3_USERNAME == "replacement-user"


def test_readonly_cli_reports_auth_result_without_save_or_secrets():
    path = Path(__file__).resolve().parents[1] / "scripts/check_kingdee_connection.py"
    assert path.exists(), "missing reproducible read-only verification entry point"
    from app.core import config as config_module
    for ok in (True, False):
        calls = []
        class ReadOnlyClient:
            def login(self):
                calls.append("login")
                return ok
            def close(self):
                calls.append("close")
        output = io.StringIO()
        with patch.object(config_module, "settings", config()), \
             patch.object(kingdee, "KingdeeClient", ReadOnlyClient), \
             patch.object(sys, "argv", [str(path)]), redirect_stdout(output):
            ns = runpy.run_path(str(path))
            assert ns["main"]() == (0 if ok else 1)
        result = json.loads(output.getvalue())
        assert result["success"] is ok and result["read_only"] is True
        assert calls == ["login", "close"]
        assert "test-app-secret" not in output.getvalue()
        assert "test-password" not in output.getvalue()


def test_readonly_cli_does_not_require_a_pms_database_driver():
    path = Path(__file__).resolve().parents[1] / "scripts/check_kingdee_connection.py"
    env = os.environ | {"DB_DIALECT": "pymssql", "K3_AUTH_MODE": "app", "K3_APP_SECRET": ""}
    result = subprocess.run([sys.executable, str(path)], env=env, text=True, capture_output=True)
    assert result.returncode == 1
    assert result.stdout.startswith("{"), "readonly probe must work without PMS database/driver"
    report = json.loads(result.stdout)
    assert report["success"] is False


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            print(f"PASS {name}")
    print("kingdee app auth contract passed")
