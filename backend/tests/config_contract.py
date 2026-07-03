import os

from app.core.config import Settings


def test_sqlite_database_url() -> None:
    os.environ["DB_DIALECT"] = "sqlite"
    os.environ["SQLITE_DB_PATH"] = "data/pms-dev.db"

    settings = Settings()

    assert settings.DATABASE_URL == "sqlite:///data/pms-dev.db"


if __name__ == "__main__":
    test_sqlite_database_url()
    print("config contract passed")
