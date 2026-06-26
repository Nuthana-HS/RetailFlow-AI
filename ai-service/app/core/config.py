"""
RetailFlow AI — AI Service Configuration
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AIServiceSettings(BaseSettings):
    """Settings for the AI Service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"

    # YOLO Configuration
    YOLO_MODEL_SIZE: str = "n"              # n, s, m, l, x
    YOLO_CONFIDENCE_THRESHOLD: float = 0.5
    YOLO_MIN_CONFIDENCE: float = 0.4
    CV_FRAME_INTERVAL_MS: int = 500

    # ML Configuration
    ML_MODEL_PATH: str = "models/wait_time_predictor_v1.pkl"
    ML_MIN_CONFIDENCE_THRESHOLD: float = 0.7

    # Core API connection (push CV updates)
    CORE_API_URL: str = "http://localhost:8000"
    CORE_API_SERVICE_KEY: str = "dev-ai-service-key"


settings = AIServiceSettings()
