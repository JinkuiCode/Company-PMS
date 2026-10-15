"""Business timestamps are explicitly UTC+8; database UTC values stay unchanged."""
from datetime import timezone, timedelta


def business_time(value):
    if value is None: return None
    utc = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return utc.astimezone(timezone(timedelta(hours=8)))
