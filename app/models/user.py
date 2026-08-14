"""User Beanie document model."""

from datetime import datetime, timezone

from beanie import Document, Indexed
from pydantic import EmailStr, Field


class User(Document):
    """Registered homeowner account."""

    full_name: str
    email: Indexed(EmailStr, unique=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"
        indexes = ["email"]
