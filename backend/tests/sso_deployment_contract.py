"""OA-to-PMS production address contract."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PMS_ORIGIN = "http://10.10.1.228"
LEGACY_ORIGIN = "10.10.91.60"


def test_oa_jsp_redirects_to_production_pms() -> None:
    jsp = (ROOT / "OA对接" / "pms_sso.jsp").read_text(encoding="utf-8")

    assert f'{PMS_ORIGIN}/sso/start?sso_login_id=' in jsp
    assert LEGACY_ORIGIN not in jsp


def test_backend_sso_defaults_match_production_pms() -> None:
    config = (ROOT / "backend" / "app" / "core" / "config.py").read_text(encoding="utf-8")

    assert f'PMS_CALLBACK_URL: str = "{PMS_ORIGIN}/sso/callback"' in config
    assert f'PMS_FRONTEND_URL: str = "{PMS_ORIGIN}"' in config
    sso_defaults = "\n".join(
        line for line in config.splitlines()
        if "PMS_CALLBACK_URL" in line or "PMS_FRONTEND_URL" in line
    )
    assert LEGACY_ORIGIN not in sso_defaults


if __name__ == "__main__":
    test_oa_jsp_redirects_to_production_pms()
    test_backend_sso_defaults_match_production_pms()
    print("SSO deployment contract passed")
