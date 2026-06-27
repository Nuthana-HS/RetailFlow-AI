"""
RetailFlow AI — ML Service Configuration

Environment-based config for the XGBoost EWT prediction service.

Model Storage:
    Trained models are serialized with pickle and saved to MODEL_DIR.
    One model per store (each store has unique queue dynamics).

    Path pattern: {MODEL_DIR}/ewt_model_{store_id}.pkl
    Metadata: Redis key → ml:model_meta:{store_id} (JSON)
"""

import os
from pathlib import Path


class MLConfig:
    """Configuration for the ML prediction service."""

    # Directory where trained model .pkl files are stored
    MODEL_DIR: Path = Path(
        os.getenv("ML_MODEL_DIR", "models")
    )

    # Minimum queue snapshots required to train (too few → unreliable model)
    MIN_TRAINING_SAMPLES: int = int(os.getenv("ML_MIN_SAMPLES", "50"))

    # XGBoost hyperparameters (good defaults for regression on tabular queue data)
    XGB_N_ESTIMATORS: int = 300
    XGB_MAX_DEPTH: int = 6
    XGB_LEARNING_RATE: float = 0.05
    XGB_SUBSAMPLE: float = 0.8
    XGB_COLSAMPLE_BYTREE: float = 0.8
    XGB_RANDOM_STATE: int = 42

    # Prediction caching
    PREDICTION_CACHE_TTL: int = 60   # seconds — recalculate every minute
    METADATA_CACHE_TTL: int = 3600   # model metadata cached for 1 hour

    # Feature names (in the exact order used for training and inference)
    FEATURE_NAMES: list[str] = [
        "queue_length",
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "month",
        "rolling_avg_30m",
        "rolling_avg_1h",
        "rolling_max_1h",
        "avg_service_time",
    ]

    # Redis key patterns
    @staticmethod
    def model_meta_key(store_id: str) -> str:
        return f"ml:model_meta:{store_id}"

    @staticmethod
    def prediction_cache_key(
        store_id: str,
        counter_id: str,
        queue_length: int,
        hour: int,
        dow: int,
    ) -> str:
        return f"ml:predict:{store_id}:{counter_id}:{queue_length}:{hour}:{dow}"


ml_config = MLConfig()
