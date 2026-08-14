"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings for the E2M API (free-tier friendly)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    mongodb_uri: str = "mongodb://localhost:27017/e2m_db"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 1440

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    gemini_api_key: str = ""
    roboflow_api_key: str = ""
    roboflow_workspace: str = ""
    roboflow_project: str = ""
    # Public Universe model used when workspace/project are not set
    # Format: project/version  e.g. door-window-detection/1
    roboflow_model: str = "door-window-detection/1"

    app_env: str = "development"
    cors_origins: str = "http://localhost:5173"

    roboflow_monthly_limit: int = 1000
    roboflow_warn_threshold: int = 50

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
