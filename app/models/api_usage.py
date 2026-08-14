"""API usage counter for free-tier Roboflow tracking."""

from datetime import datetime, timezone

from beanie import Document
from pydantic import Field


class ApiUsage(Document):
    """Tracks monthly Roboflow (and similar) API call counts."""

    service: str = "roboflow"
    year_month: str  # e.g. "2026-08"
    call_count: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "api_usage"
