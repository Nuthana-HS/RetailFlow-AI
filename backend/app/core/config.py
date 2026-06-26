"""
RetailFlow AI — Application Configuration

Uses pydantic-settings to load configuration from environment variables.
All settings are typed and validated at startup.
"""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All fields map to environment variables defined in .env.example.
    Pydantic validates types at startup — misconfigured environments
    will fail immediately with a clear error message.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # Ignore unknown env vars
    )

    # -------------------------------------------------------------------------
    # App Metadata
    # -------------------------------------------------------------------------
    APP_NAME: str = "RetailFlow AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "testing", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    DATABASE_URL: str
    TEST_DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 20

    # -------------------------------------------------------------------------
    # JWT Authentication
    # -------------------------------------------------------------------------
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 900       # 15 minutes
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Allow CORS_ORIGINS as a comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    ALLOWED_HOSTS: list[str] = ["*"]

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------
    RATE_LIMIT_UNAUTHENTICATED: int = 100   # Requests per minute
    RATE_LIMIT_AUTHENTICATED: int = 1000

    # -------------------------------------------------------------------------
    # AI Service Integration
    # -------------------------------------------------------------------------
    AI_SERVICE_URL: AnyHttpUrl = "http://localhost:8001"  # type: ignore[assignment]
    AI_SERVICE_API_KEY: str = "dev-ai-service-key"
    AI_SERVICE_TIMEOUT: int = 30

    # -------------------------------------------------------------------------
    # Email (SMTP)
    # -------------------------------------------------------------------------
    SMTP_HOST: str = "smtp.sendgrid.net"
    SMTP_PORT: int = 587
    SMTP_USER: str = "apikey"
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@retailflow.ai"
    SMTP_FROM_NAME: str = "RetailFlow AI"
    SEND_EMAILS: bool = False

    # -------------------------------------------------------------------------
    # Business Logic Defaults
    # -------------------------------------------------------------------------
    DEFAULT_ALERT_COOLDOWN_MINUTES: int = 30
    DEFAULT_QUEUE_ALERT_THRESHOLD: int = 8
    DEFAULT_AVG_SERVICE_TIME_SECONDS: int = 180  # 3 minutes per customer
    CV_UPDATE_INTERVAL_SECONDS: int = 5
    ML_PREDICTION_CACHE_TTL_SECONDS: int = 30

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"

    @property
    def active_database_url(self) -> str:
        """Return test database URL during testing, else production URL."""
        if self.ENVIRONMENT == "testing" and self.TEST_DATABASE_URL:
            return self.TEST_DATABASE_URL
        return self.DATABASE_URL


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns cached application settings.

    Using lru_cache ensures settings are loaded from environment only once
    per process. Cache can be cleared in tests to reset settings.
    """
    return Settings()


# Module-level settings instance for convenience
settings = get_settings()
