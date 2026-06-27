"""
RetailFlow AI — CV Service Configuration

All configuration for the standalone CV service process.
Values are loaded from environment variables with sensible defaults.

Usage:
    Set RETAILFLOW_API_URL and RETAILFLOW_API_TOKEN in environment
    (or a .env file at the cv_service root), then run:

        python -m cv_service.main --store-id <store_uuid>
"""

import os
from dataclasses import dataclass, field


@dataclass
class CVServiceConfig:
    """
    Configuration for the Computer Vision Service.

    Loaded from environment variables at startup.
    All queue updates are made to the RetailFlow API,
    so the CV service has no direct DB access.
    """

    # API connection (the FastAPI backend from Phase 3-8)
    api_base_url: str = field(
        default_factory=lambda: os.getenv(
            "RETAILFLOW_API_URL", "http://localhost:8000"
        )
    )
    api_token: str = field(
        default_factory=lambda: os.getenv("RETAILFLOW_API_TOKEN", "")
    )

    # YOLOv8 model config
    model_path: str = field(
        default_factory=lambda: os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")
    )
    device: str = field(
        default_factory=lambda: os.getenv("YOLO_DEVICE", "cpu")
    )
    # Person class index in COCO dataset (YOLOv8 default)
    person_class_id: int = 0

    # Processing config
    default_update_interval: int = field(
        default_factory=lambda: int(os.getenv("CV_UPDATE_INTERVAL", "5"))
    )
    simulation_max_queue: int = field(
        default_factory=lambda: int(os.getenv("CV_SIM_MAX_QUEUE", "15"))
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.getenv("CV_LOG_LEVEL", "INFO")
    )


# Module-level singleton
cv_config = CVServiceConfig()
