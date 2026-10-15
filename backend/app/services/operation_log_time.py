"""Adapt SQLite's UTC default clock at read time; keep other database clocks."""
from datetime import timezone, timedelta
from sqlalchemy import func, literal_column
from app.core.business_time import business_time

BUSINESS_ZONE = timezone(timedelta(hours=8))


def _sqlite(db):
    return db is not None and db.get_bind().dialect.name == 'sqlite'


def display_time(db, value):
    return business_time(value) if _sqlite(db) and value is not None else value


def query_time(db, value):
    if value is None or not _sqlite(db):
        return value
    local = value.replace(tzinfo=BUSINESS_ZONE) if value.tzinfo is None else value
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def date_column(db, column):
    # Fixed SQL literal also keeps SELECT/GROUP BY expressions identical.
    return func.datetime(column, literal_column("'+8 hours'")) if _sqlite(db) else column
