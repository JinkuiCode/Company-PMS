"""Independent report-only connection; never falls back to PMS/admin credentials."""
from contextlib import contextmanager
import os

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class PurchaseUnavailable(RuntimeError):
    def __init__(self):
        super().__init__('采购报表数据源不可用，请联系管理员检查只读连接配置')


class PurchaseDatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra='ignore', hide_input_in_errors=True)

    PURCHASE_DB_HOST: str = ''
    PURCHASE_DB_NAME: str = ''
    PURCHASE_DB_USER: str = ''
    PURCHASE_DB_PASSWORD: SecretStr = Field(default=SecretStr(''), repr=False)
    PURCHASE_DB_PORT: int = Field(default=1433, ge=1, le=65535)
    PURCHASE_DB_TIMEOUT: int = Field(default=20, ge=1, le=30)


@contextmanager
def purchase_connection(config=None, *, connector=None):
    """All connection failures are sanitized; all sessions close without commit.

    PMS_PURCHASE_CONFIG_FILE must be set explicitly by the launcher/deployment.
    Merely having a private credential file does not enable production access.
    Database-granted column permissions, not read_only intent, enforce read-only.
    """
    connection = None
    try:
        if config is None:
            config = PurchaseDatabaseSettings(_env_file=os.environ.get('PMS_PURCHASE_CONFIG_FILE'))
        if (not config.PURCHASE_DB_HOST.strip() or not config.PURCHASE_DB_NAME.strip()
                or config.PURCHASE_DB_USER != 'pms_purchase_reader'
                or not config.PURCHASE_DB_PASSWORD.get_secret_value()):
            raise PurchaseUnavailable()
        if connector is None:
            import pymssql
            connector = pymssql.connect
        connection = connector(server=config.PURCHASE_DB_HOST, port=config.PURCHASE_DB_PORT,
            database=config.PURCHASE_DB_NAME, user=config.PURCHASE_DB_USER,
            password=config.PURCHASE_DB_PASSWORD.get_secret_value(),
            as_dict=True, encryption='require', read_only=True, autocommit=False,
            login_timeout=10, timeout=config.PURCHASE_DB_TIMEOUT, appname='PMS-Purchase-Report')
        cursor = connection.cursor()
        cursor.execute('SET LOCK_TIMEOUT 3000')
        cursor.execute('SELECT DB_NAME() AS database_name, SUSER_SNAME() AS login_name')
        identity = cursor.fetchone()
        if identity['database_name'] != config.PURCHASE_DB_NAME or identity['login_name'] != config.PURCHASE_DB_USER:
            raise PurchaseUnavailable()
    except Exception:
        if connection is not None:
            connection.close()
        raise PurchaseUnavailable() from None
    try:
        yield connection
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
