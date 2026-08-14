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
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Matches Vercel preview + production hostnames when CORS_ORIGINS is not exhaustive
    cors_origin_regex: str = r"https://.*\.vercel\.app"

    roboflow_monthly_limit: int = 1000
    roboflow_warn_threshold: int = 50

    @property
    def is_production(self) -> bool:
        """True when running on Render or any production host."""
        return self.app_env.lower() in {"production", "prod", "render"}

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list (no trailing slashes)."""
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    def validate_for_hosting(self) -> None:
        """Fail fast on Render if required production secrets are still placeholders."""
        if not self.is_production:
            return
        weak_jwt = self.jwt_secret_key in {
            "change-me-in-production",
            "change-me-to-a-long-random-secret-key",
        }
        if weak_jwt or len(self.jwt_secret_key) < 32:
            raise RuntimeError(
                "Set JWT_SECRET_KEY to a long random value before deploying to Render."
            )
        if "localhost" in self.mongodb_uri or "127.0.0.1" in self.mongodb_uri:
            raise RuntimeError(
                "Set MONGODB_URI to MongoDB Atlas (not localhost) for Render."
            )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
