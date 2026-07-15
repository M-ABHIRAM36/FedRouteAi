"""Small helpers used across services for hour-of-day bucketing and a
single source of truth for "what time is it right now"."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC datetime — matches this project's plain (non-timezone)
    DateTime columns throughout app/models/. Using datetime.utcnow()
    directly is deprecated in modern Python; this wraps the
    timezone-aware replacement and strips the tzinfo back off so every
    comparison against DB-stored timestamps stays apples-to-apples
    (mixing naive and aware datetimes raises TypeError on comparison)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hour_of_day(ts: datetime) -> int:
    return ts.hour


def is_peak_hour(ts: datetime) -> bool:
    h = ts.hour
    return (8 <= h <= 10) or (17 <= h <= 20)
