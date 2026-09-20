import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_CONFIG_FILE = Path(__file__).resolve().parents[2] / ".env.local"


class RuntimeConfigurationError(RuntimeError):
    def __init__(self, issues: list[str]):
        self.issues = tuple(issues)
        super().__init__("PMS runtime configuration is invalid: " + ", ".join(issues))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **values):
        if "_env_file" not in values:
            values["_env_file"] = os.environ.get("PMS_CONFIG_FILE", DEFAULT_CONFIG_FILE)
        super().__init__(**values)

    PMS_ENV: Literal["development", "production"] = "development"
    APP_NAME: str = "PMS 项目管理系统"
    DEBUG: bool = False
    # Explicitly enabled at deployment; development never writes ERP in the background by default.
    ERP_SYNC_WORKER_ENABLED: bool = False

    # Safe local defaults never target company infrastructure.
    DB_HOST: str = ""
    DB_PORT: int = 1433
    DB_USER: str = ""
    DB_PASSWORD: str = Field(default="", repr=False)
    DB_NAME: str = "PMS"
    DB_DIALECT: Literal["sqlite", "pyodbc", "pymssql"] = "sqlite"
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"
    SQLITE_DB_PATH: str = "data/pms-dev.db"

    @property
    def DATABASE_URL(self) -> str:
        if self.DB_DIALECT == "sqlite":
            db_path = Path(self.SQLITE_DB_PATH)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{db_path}"
        if self.DB_DIALECT == "pymssql":
            return (
                f"mssql+pymssql://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
                "?charset=utf8"
            )
        driver = self.DB_DRIVER.replace(" ", "+")
        return (
            f"mssql+pyodbc://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?driver={driver}"
            "&Encrypt=no"
            "&TrustServerCertificate=yes"
            "&charset=utf8"
        )

    # JWT and local bootstrap credentials.
    SECRET_KEY: str = Field(default="", repr=False)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    PMS_BOOTSTRAP_ADMIN_USERNAME: str = ""
    PMS_BOOTSTRAP_ADMIN_PASSWORD: str = Field(default="", repr=False)
    REMEMBER_TOKEN_EXPIRE_DAYS: int = 180

    # Weaver OA SSO. Production values belong in protected configuration only.
    SSO_ENABLED: bool = False
    SSO_SECRET_KEY: str = Field(default="", repr=False)
    SSO_AUTO_CREATE_USER: bool = True
    SSO_TOKEN_EXPIRE_SECONDS: int = 300
    SSO_OA_DOMAIN: str = ""
    OA_BASE_URL: str = ""
    OA_APP_ID: str = ""
    OA_APP_SECRET: str = Field(default="", repr=False)
    OA_GET_TOKEN_URL: str = ""
    OA_CHECK_TOKEN_URL: str = ""
    OA_LOGIN_URL: str = ""
    PMS_CALLBACK_URL: str = "http://127.0.0.1:5174/sso/callback"
    PMS_FRONTEND_URL: str = "http://127.0.0.1:5174"
    OA_SERVICE_VALIDATE_URL: str = ""
    OA_CHECK_USER_PWD_URL: str = ""
    OA_HRM_SERVICE_URL: str = ""

    # Kingdee K3Cloud. Business writes remain disabled by default.
    K3_AUTH_MODE: Literal["app", "password"] = "password"
    K3_READ_ONLY: bool = True
    K3_APP_ID: str = ""
    K3_APP_SECRET: str = Field(default="", repr=False)
    K3_LCID: int = 2052
    K3_ORG_NUM: int = 0
    K3_URL: str = ""
    K3_ACCT_ID: str = ""
    K3_USERNAME: str = ""
    K3_PASSWORD: str = Field(default="", repr=False)


def _missing(settings: Settings, names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not str(getattr(settings, name, "")).strip()]


def validate_runtime_config(settings: Settings) -> None:
    issues: list[str] = []
    external_services = settings.DB_DIALECT != "sqlite" or settings.SSO_ENABLED or bool(settings.K3_URL.strip())
    if settings.PMS_ENV == "production" or external_services:
        secret_key = settings.SECRET_KEY.strip()
        if len(secret_key) < 32 or "change-in-production" in secret_key.lower():
            issues.append("SECRET_KEY")

    if settings.DB_DIALECT != "sqlite":
        issues.extend(_missing(settings, ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")))

    if settings.SSO_ENABLED:
        issues.extend(
            _missing(
                settings,
                (
                    "SSO_SECRET_KEY",
                    "SSO_OA_DOMAIN",
                    "OA_APP_ID",
                    "OA_APP_SECRET",
                    "OA_LOGIN_URL",
                    "PMS_CALLBACK_URL",
                    "PMS_FRONTEND_URL",
                ),
            )
        )

    if settings.K3_URL.strip():
        if settings.K3_AUTH_MODE == "app":
            issues.extend(_missing(settings, ("K3_APP_ID", "K3_APP_SECRET", "K3_ACCT_ID", "K3_USERNAME")))
        else:
            issues.extend(_missing(settings, ("K3_ACCT_ID", "K3_USERNAME", "K3_PASSWORD")))

    if settings.PMS_ENV == "production":
        if settings.DEBUG:
            issues.append("DEBUG")
        if settings.DB_DIALECT == "sqlite":
            issues.append("DB_DIALECT")
        if not settings.K3_URL.strip():
            issues.append("K3_URL")
        if settings.K3_AUTH_MODE == "app" and not settings.K3_URL.strip():
            issues.extend(
                _missing(
                    settings,
                    ("K3_APP_ID", "K3_APP_SECRET", "K3_ACCT_ID", "K3_USERNAME"),
                )
            )
        elif settings.K3_AUTH_MODE == "password" and not settings.K3_URL.strip():
            issues.extend(_missing(settings, ("K3_ACCT_ID", "K3_USERNAME", "K3_PASSWORD")))

    if issues:
        raise RuntimeConfigurationError(list(dict.fromkeys(issues)))


settings = Settings()
