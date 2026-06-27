"""
RetailFlow AI — Unit Tests: EWT Predictor

Tests for EWTPredictor logic — no XGBoost, no disk, no Redis.
Uses mocked models and mock Redis to test the caching and fallback paths.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from ml_service.features import FeatureVector
from ml_service.predictor import EWTPredictor, CachedEWTPredictor


def _make_feature_vector(queue_length: int = 5) -> FeatureVector:
    return FeatureVector(
        queue_length=float(queue_length),
        hour_of_day=14.0,
        day_of_week=2.0,
        is_weekend=0.0,
        month=6.0,
        rolling_avg_30m=4.0,
        rolling_avg_1h=3.5,
        rolling_max_1h=8.0,
        avg_service_time=120.0,
    )


# =============================================================================
# Test: EWTPredictor — formula fallback
# =============================================================================

class TestEWTPredictorFallback:

    def test_fallback_when_model_file_missing(self, tmp_path: Path) -> None:
        """When model file doesn't exist, use linear formula."""
        model_path = tmp_path / "missing_model.pkl"
        predictor = EWTPredictor(model_path)
        fv = _make_feature_vector(queue_length=5)
        # 5 × 120 = 600 seconds
        result = predictor.predict(fv)
        assert result == 600

    def test_fallback_for_zero_queue(self, tmp_path: Path) -> None:
        """Zero queue length → zero wait time."""
        predictor = EWTPredictor(tmp_path / "missing.pkl")
        fv = _make_feature_vector(queue_length=0)
        assert predictor.predict(fv) == 0

    def test_model_not_loaded_when_file_missing(self, tmp_path: Path) -> None:
        predictor = EWTPredictor(tmp_path / "nope.pkl")
        assert predictor.is_model_loaded() is False


# =============================================================================
# Test: EWTPredictor — with mocked XGBoost model
# =============================================================================

class TestEWTPredictorWithModel:

    def _make_predictor_with_mock_model(self, tmp_path: Path, pred_value: float) -> EWTPredictor:
        """Create an EWTPredictor with a mock model injected."""
        mock_model = MagicMock()
        mock_model.predict = MagicMock(return_value=np.array([pred_value]))

        # Create a dummy pkl file so is_model_loaded passes
        model_path = tmp_path / "model.pkl"
        model_path.write_bytes(b"fake")

        predictor = EWTPredictor(model_path)
        predictor._model = mock_model  # Inject mock directly
        return predictor

    def test_uses_model_when_loaded(self, tmp_path: Path) -> None:
        """When model is loaded, prediction comes from XGBoost."""
        predictor = self._make_predictor_with_mock_model(tmp_path, pred_value=450.0)
        fv = _make_feature_vector(queue_length=5)
        result = predictor.predict(fv)
        assert result == 450

    def test_negative_prediction_clamped_to_zero(self, tmp_path: Path) -> None:
        """XGBoost cannot produce negative EWT — clamp to 0."""
        predictor = self._make_predictor_with_mock_model(tmp_path, pred_value=-100.0)
        fv = _make_feature_vector(queue_length=1)
        assert predictor.predict(fv) == 0

    def test_excessive_prediction_clamped_to_4h(self, tmp_path: Path) -> None:
        """Predictions beyond 4 hours (14400s) are unrealistic — clamp."""
        predictor = self._make_predictor_with_mock_model(tmp_path, pred_value=99_999.0)
        fv = _make_feature_vector(queue_length=100)
        assert predictor.predict(fv) == 14_400

    def test_is_model_loaded_true_when_injected(self, tmp_path: Path) -> None:
        predictor = self._make_predictor_with_mock_model(tmp_path, 300.0)
        assert predictor.is_model_loaded() is True

    def test_reload_clears_model(self, tmp_path: Path) -> None:
        """reload() should force the model to be re-read from disk."""
        predictor = self._make_predictor_with_mock_model(tmp_path, 300.0)
        # Model is loaded
        assert predictor._model is not None

        # Replace the model file with non-existent path to simulate missing model after reload
        predictor._model_path = tmp_path / "nonexistent.pkl"
        predictor.reload()

        # After reload, model should be None (file not found)
        assert predictor._model is None


# =============================================================================
# Test: CachedEWTPredictor — Redis caching
# =============================================================================

class TestCachedEWTPredictor:

    def _make_cached_predictor(self, tmp_path: Path, mock_redis) -> CachedEWTPredictor:
        model_path = tmp_path / "model.pkl"
        return CachedEWTPredictor(model_path, mock_redis)

    @pytest.mark.asyncio
    async def test_returns_cached_value_on_cache_hit(self, tmp_path: Path) -> None:
        """Cache hit → return cached value without calling model."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="360")  # Cache hit
        mock_redis.setex = AsyncMock()

        cached = self._make_cached_predictor(tmp_path, mock_redis)
        fv = _make_feature_vector(queue_length=3)

        seconds, from_cache = await cached.predict_cached(fv, "store-a", "counter-b")

        assert seconds == 360
        assert from_cache is True
        # setex should NOT be called on cache hit
        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_runs_inference_on_cache_miss(self, tmp_path: Path) -> None:
        """Cache miss → run inference and store result in Redis."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # Cache miss
        mock_redis.setex = AsyncMock()

        cached = self._make_cached_predictor(tmp_path, mock_redis)

        # No model file → falls back to formula: 5 × 120 = 600
        fv = _make_feature_vector(queue_length=5)
        seconds, from_cache = await cached.predict_cached(fv, "store-a", "counter-b")

        assert seconds == 600
        assert from_cache is False
        # setex should be called to cache the result
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_key_differs_by_queue_length(self, tmp_path: Path) -> None:
        """Different queue lengths must produce different cache keys."""
        from ml_service.config import ml_config

        key1 = ml_config.prediction_cache_key("s", "c", queue_length=3, hour=14, dow=2)
        key2 = ml_config.prediction_cache_key("s", "c", queue_length=7, hour=14, dow=2)
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_cache_key_differs_by_store(self, tmp_path: Path) -> None:
        from ml_service.config import ml_config

        key1 = ml_config.prediction_cache_key("store-a", "c", queue_length=3, hour=14, dow=2)
        key2 = ml_config.prediction_cache_key("store-b", "c", queue_length=3, hour=14, dow=2)
        assert key1 != key2
