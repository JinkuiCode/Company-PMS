#!/usr/bin/env python3
"""Run the existing idempotent database setup as a separate release step."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings, validate_runtime_config
from app.core.database import engine
from app.models.init_db import init_db
from app.services.database_revision import (
    check_database_ready,
    mark_database_ready,
    mark_database_upgrading,
)


def upgrade_database() -> None:
    validate_runtime_config(settings)
    mark_database_upgrading(engine)
    init_db()
    mark_database_ready(engine)
    check_database_ready(engine)


if __name__ == "__main__":
    upgrade_database()
    print("数据库升级完成")
