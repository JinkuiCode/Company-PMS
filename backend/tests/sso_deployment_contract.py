"""OA-to-PMS production address contract."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PMS_ORIGIN = "http://10.10.1.228"
LEGACY_ORIGIN = "10.10.91.60"


def test_oa_jsp_redirects_to_production_pms() -> None:
    jsp = (ROOT / "OA对接" / "pms_sso.jsp").read_text(encoding="utf-8")

    assert f'{PMS_ORIGIN}/sso/start?sso_login_id=' in jsp
    assert LEGACY_ORIGIN not in jsp


def test_backend_sso_addresses_require_protected_production_configuration() -> None:
    config = (ROOT / "backend" / "app" / "core" / "config.py").read_text(encoding="utf-8")
    template = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")

    assert 'PMS_CALLBACK_URL: str = "http://127.0.0.1:5174/sso/callback"' in config
    assert 'PMS_FRONTEND_URL: str = "http://127.0.0.1:5174"' in config
    assert "PMS_CALLBACK_URL=" in template
    assert "PMS_FRONTEND_URL=" in template
    assert PMS_ORIGIN not in config
    assert LEGACY_ORIGIN not in config


def test_oa_jsp_reads_shared_secret_from_protected_runtime() -> None:
    jsp = (ROOT / "OA对接" / "pms_sso.jsp").read_text(encoding="utf-8")
    assert 'System.getProperty("PMS_SSO_SECRET")' in jsp
    assert 'System.getenv("PMS_SSO_SECRET")' in jsp
    assert 'String secretKey = "' not in jsp


if __name__ == "__main__":
    test_oa_jsp_redirects_to_production_pms()
    test_backend_sso_addresses_require_protected_production_configuration()
    test_oa_jsp_reads_shared_secret_from_protected_runtime()
    print("SSO deployment contract passed")
