"""Explicit, idempotent schema upgrade; never run from application startup."""
from sqlalchemy import inspect, text
from app.services.offline_archive_fields import OFFLINE_FIELDS
def upgrade_offline_archive(engine):
    with engine.begin() as c:
        inspector=inspect(c)
        if not inspector.has_table("pms_project_archive"):return
        existing={v["name"] for v in inspector.get_columns("pms_project_archive")}
        for key,meta in OFFLINE_FIELDS.items():
            if key not in existing:
                c.execute(text(f"ALTER TABLE pms_project_archive ADD {key} {meta['sql_type']} NULL"))
        if "erp_sync_policy" not in existing:
            c.execute(text("ALTER TABLE pms_project_archive ADD erp_sync_policy NVARCHAR(16) NOT NULL DEFAULT 'auto'"))
