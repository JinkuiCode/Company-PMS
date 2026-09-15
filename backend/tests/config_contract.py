import os

from app.core.config import Settings


def test_sqlite_database_url() -> None:
    os.environ["DB_DIALECT"] = "sqlite"
    os.environ["SQLITE_DB_PATH"] = "data/pms-dev.db"

    settings = Settings()

    assert settings.DATABASE_URL == "sqlite:///data/pms-dev.db"


def test_pyodbc_database_url_disables_implicit_driver_encryption() -> None:
    settings = Settings(
        DB_DIALECT="pyodbc",
        DB_HOST="db.internal",
        DB_PORT=1433,
        DB_NAME="PMS",
        DB_USER="pms_app",
        DB_PASSWORD="secret",
        DB_DRIVER="ODBC Driver 18 for SQL Server",
    )

    assert "Encrypt=no" in settings.DATABASE_URL
    assert "TrustServerCertificate=yes" in settings.DATABASE_URL


if __name__ == "__main__":
    test_sqlite_database_url()
    test_pyodbc_database_url_disables_implicit_driver_encryption()
    print("config contract passed")
