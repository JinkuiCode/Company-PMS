import os
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from app.core.config import RuntimeConfigurationError, Settings, validate_runtime_config


def make_settings(**overrides) -> Settings:
    values = {
        "PMS_ENV": "development",
        "DB_DIALECT": "sqlite",
        "SECRET_KEY": "local-test-secret-with-at-least-32-characters",
        "SSO_ENABLED": False,
        "K3_AUTH_MODE": "app",
        "K3_READ_ONLY": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_sensitive_defaults_are_empty_and_hidden() -> None:
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)

    for field_name in (
        "DB_PASSWORD",
        "SECRET_KEY",
        "SSO_SECRET_KEY",
        "OA_APP_SECRET",
        "K3_APP_SECRET",
        "K3_PASSWORD",
    ):
        assert getattr(settings, field_name) == ""
        assert field_name not in repr(settings)


def test_safe_development_defaults_do_not_target_company_services() -> None:
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)

    assert settings.PMS_ENV == "development"
    assert settings.DEBUG is False
    assert settings.DB_DIALECT == "sqlite"
    assert settings.SSO_ENABLED is False
    assert settings.DB_HOST == ""
    assert settings.OA_BASE_URL == ""
    assert settings.K3_URL == ""


def test_development_sqlite_accepts_launcher_managed_secret() -> None:
    validate_runtime_config(make_settings())


def test_production_rejects_missing_or_unsafe_settings_without_values() -> None:
    settings = make_settings(
        PMS_ENV="production",
        SECRET_KEY="",
        DEBUG=True,
        DB_DIALECT="pymssql",
        DB_HOST="db.internal",
        DB_USER="pms",
        DB_PASSWORD="",
        SSO_ENABLED=True,
        SSO_SECRET_KEY="",
        OA_APP_ID="",
        OA_APP_SECRET="",
        K3_APP_ID="",
        K3_APP_SECRET="",
        K3_ACCT_ID="",
        K3_USERNAME="",
        K3_URL="",
    )

    try:
        validate_runtime_config(settings)
    except RuntimeConfigurationError as exc:
        message = str(exc)
    else:
        raise AssertionError("production configuration should fail closed")

    for field_name in (
        "DEBUG",
        "DB_PASSWORD",
        "SSO_SECRET_KEY",
        "OA_APP_ID",
        "OA_APP_SECRET",
        "K3_APP_ID",
        "K3_APP_SECRET",
        "K3_ACCT_ID",
        "K3_USERNAME",
        "K3_URL",
    ):
        assert field_name in message
    assert "db.internal" not in message


def test_explicit_config_file_can_be_shared_by_runtime_worktrees(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "DB_DIALECT=sqlite\n"
        "SECRET_KEY=shared-runtime-secret-with-at-least-32-characters\n",
        encoding="utf-8",
    )
    with patch.dict(os.environ, {"PMS_CONFIG_FILE": str(env_file)}, clear=True):
        settings = Settings()

    assert settings.SECRET_KEY.startswith("shared-runtime")
    assert str(env_file) not in repr(settings)


def test_external_service_configuration_cannot_bypass_secret_checks() -> None:
    settings = Settings(
        _env_file=None,
        PMS_ENV="development",
        DB_DIALECT="pymssql",
        DB_HOST="db.internal",
        DB_USER="pms",
        DB_PASSWORD="",
        SECRET_KEY="",
    )
    try:
        validate_runtime_config(settings)
    except RuntimeConfigurationError as exc:
        assert "SECRET_KEY" in exc.issues
        assert "DB_PASSWORD" in exc.issues
    else:
        raise AssertionError("external services must activate runtime secret checks")


def test_local_config_preparation_is_private_idempotent_and_quiet(tmp_path: Path) -> None:
    config_path = tmp_path / ".env.local"
    script = Path(__file__).resolve().parents[1] / "scripts" / "prepare_local_config.py"
    env = os.environ.copy()
    env["PMS_CONFIG_FILE"] = str(config_path)
    first = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True)
    assert first.returncode == 0
    content = config_path.read_text(encoding="utf-8")
    secret_line = next(line for line in content.splitlines() if line.startswith("SECRET_KEY="))
    secret_value = secret_line.split("=", 1)[1]
    assert secret_value and secret_value not in first.stdout + first.stderr
    assert config_path.stat().st_mode & 0o777 == 0o600

    second = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True)
    assert second.returncode == 0
    assert config_path.read_text(encoding="utf-8") == content


def test_runtime_config_checker_runs_as_standalone_script(tmp_path: Path) -> None:
    config_path = tmp_path / ".env.local"
    config_path.write_text(
        "PMS_ENV=development\n"
        "DB_DIALECT=sqlite\n"
        "SECRET_KEY=standalone-check-secret-with-at-least-32-characters\n",
        encoding="utf-8",
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_runtime_config.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PMS_CONFIG_FILE"] = str(config_path)
    result = subprocess.run(
        [sys.executable, str(script), "--expect", "development"],
        cwd=script.parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload == {"valid": True, "environment": "development", "issues": []}


if __name__ == "__main__":
    test_sensitive_defaults_are_empty_and_hidden()
    test_safe_development_defaults_do_not_target_company_services()
    test_development_sqlite_accepts_launcher_managed_secret()
    test_production_rejects_missing_or_unsafe_settings_without_values()
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_explicit_config_file_can_be_shared_by_runtime_worktrees(Path(tmp))
    test_external_service_configuration_cannot_bypass_secret_checks()
    with tempfile.TemporaryDirectory() as tmp:
        test_local_config_preparation_is_private_idempotent_and_quiet(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_runtime_config_checker_runs_as_standalone_script(Path(tmp))
    print("runtime security contract passed")
