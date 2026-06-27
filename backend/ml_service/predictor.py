"""
RetailFlow AI — EWT Predictor

Runs XGBoost inference for Estimated Wait Time (EWT) prediction.
Integrates Redis caching to avoid redundant inference calls.

Caching Strategy:
    Cache key = ml:predict:{store_id}:{counter_id}:{queue_length}:{hour}:{dow}
    TTL = 60 seconds

    Rationale:
      - queue_length, hour, and day_of_week are the dominant features.
      - Within a 60-second window, these rarely change enough to matter.
      - This avoids running XGBoost inference on every API call (which
        is fast at <1ms but still unnecessary for repeated identical inputs).
      - The rolling averages are excluded from the cache key because they
        change continuously and would reduce cache hit rate significantly.

Fallback:
    If the trained model file is missing (model not yet trained),
    the predictor falls back to the linear formula:
        EWT = queue_length × avg_service_time
    This ensures the prediction endpoint is always usable, even before
    the first training run.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ml_service.config import ml_config
from ml_service.features import FeatureVector

logger = logging.getLogger(__name__)


class EWTPredictor:
    """
    Predicts Estimated Wait Time (seconds) using a trained XGBoost model.

    Thread-safe — model is loaded once and reused across requests.
    """

    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path
        self._model = None   # Lazy load on first predict call

    def _load(self) -> None:
        """Load XGBoost model from disk (called lazily on first prediction)."""
        if self._model is not None:
            return

        if not self._model_path.exists():
            logger.warning(
                f"No trained model at {self._model_path}. "
                "Predictions will fall back to linear formula."
            )
            return

        try:
            from ml_service.trainer import XGBoostTrainer
            trainer = XGBoostTrainer()
            self._model = trainer.load(self._model_path)
            logger.info(f"Predictor loaded model from {self._model_path}")
        except Exception as exc:
            logger.error(f"Failed to load model: {exc}")
            self._model = None

    def predict(self, features: FeatureVector) -> int:
        """
        Predict EWT from a feature vector.

        Args:
            features: Fully populated FeatureVector.

        Returns:
            Predicted EWT in seconds (non-negative integer).

        Behaviour:
            - If model is loaded: returns XGBoost prediction
            - If model unavailable: returns linear formula fallback
        """
        self._load()

        if self._model is None:
            # Linear formula fallback
            fallback = int(features.queue_length * features.avg_service_time)
            logger.debug(f"Using formula fallback: {fallback}s")
            return max(0, fallback)

        # XGBoost inference
        X = features.to_dataframe()
        raw_pred = float(self._model.predict(X)[0])
        # Clamp: EWT cannot be negative; cap at 4 hours (3 sigma sanity check)
        prediction = max(0, min(int(raw_pred), 14_400))

        logger.debug(f"XGBoost prediction: {prediction}s (raw={raw_pred:.1f}s)")
        return prediction

    def is_model_loaded(self) -> bool:
        """True if a trained model has been loaded successfully."""
        self._load()
        return self._model is not None

    def reload(self) -> None:
        """Force a model reload from disk (called after training)."""
        self._model = None
        self._load()


class CachedEWTPredictor:
    """
    EWTPredictor wrapped with Redis caching.

    Usage:
        predictor = CachedEWTPredictor(model_path, redis)
        seconds = await predictor.predict_cached(features, store_id, counter_id)
    """

    def __init__(self, model_path: Path, redis) -> None:
        self._predictor = EWTPredictor(model_path)
        self._redis = redis

    async def predict_cached(
        self,
        features: FeatureVector,
        store_id: str,
        counter_id: str,
    ) -> tuple[int, bool]:
        """
        Get a cached or fresh EWT prediction.

        Args:
            features: Feature vector for this prediction.
            store_id: Used for the cache key.
            counter_id: Used for the cache key.

        Returns:
            Tuple of (predicted_seconds: int, from_cache: bool).
        """
        cache_key = ml_config.prediction_cache_key(
            store_id=store_id,
            counter_id=counter_id,
            queue_length=int(features.queue_length),
            hour=int(features.hour_of_day),
            dow=int(features.day_of_week),
        )

        # Check cache
        cached = await self._redis.get(cache_key)
        if cached:
            return int(cached), True

        # Run inference
        seconds = self._predictor.predict(features)

        # Cache result
        await self._redis.setex(cache_key, ml_config.PREDICTION_CACHE_TTL, seconds)

        return seconds, False

    def reload(self) -> None:
        """Reload the underlying model (called after training completes)."""
        self._predictor.reload()

    def is_model_loaded(self) -> bool:
        return self._predictor.is_model_loaded()


# ─────────────────────────────────────────────────────────────────────────────
# Store-keyed predictor registry
# ─────────────────────────────────────────────────────────────────────────────
# One predictor instance per store — avoids reloading model on every request.
_predictor_registry: dict[str, CachedEWTPredictor] = {}


def get_predictor(store_id: str, redis) -> CachedEWTPredictor:
    """
    Get or create a CachedEWTPredictor for a store.

    Module-level cache: the predictor is created once per store per process.
    Calling reload() after training updates the underlying model.
    """
    if store_id not in _predictor_registry:
        model_path = ml_config.MODEL_DIR / f"ewt_model_{store_id}.pkl"
        _predictor_registry[store_id] = CachedEWTPredictor(model_path, redis)
    return _predictor_registry[store_id]


def invalidate_predictor(store_id: str) -> None:
    """Force a predictor reload for a store (called after retraining)."""
    if store_id in _predictor_registry:
        _predictor_registry[store_id].reload()
