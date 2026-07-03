import os
import tempfile


def test_sqlite_init_db() -> None:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)

    os.environ["DB_DIALECT"] = "sqlite"
    os.environ["SQLITE_DB_PATH"] = path

    from app.models.init_db import init_db

    init_db()


if __name__ == "__main__":
    test_sqlite_init_db()
    print("sqlite init contract passed")
