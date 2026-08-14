"""Shared backend utility helpers."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def year_month_key(dt: datetime | None = None) -> str:
    """Return YYYY-MM key for monthly API usage tracking."""
    moment = dt or utc_now()
    return moment.strftime("%Y-%m")
