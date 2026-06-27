"""
RetailFlow AI — Unit Tests: Feature Engineering

Tests for FeatureBuilder and FeatureVector.
No XGBoost, no database, no Redis required.

Coverage:
  - FeatureVector.to_numpy() has correct shape and dtype
  - FeatureVector.to_dataframe() has correct column names
  - FeatureBuilder.build_for_inference() extracts correct time features
  - FeatureBuilder._compute_rolling() computes correct windows
  - FeatureBuilder.build_training_dataframe() handles edge cases
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from ml_service.config import ml_config
from ml_service.features import FeatureBuilder, FeatureVector


# =============================================================================
# Test: FeatureVector
# =============================================================================

class TestFeatureVector:

    def _make(self, **kwargs) -> FeatureVector:
        defaults = dict(
            queue_length=5.0, hour_of_day=14.0, day_of_week=2.0,
            is_weekend=0.0, month=6.0, rolling_avg_30m=4.0,
            rolling_avg_1h=3.5, rolling_max_1h=8.0, avg_service_time=120.0,
        )
        defaults.update(kwargs)
        return FeatureVector(**defaults)

    def test_to_numpy_shape(self) -> None:
        """Feature vector must be shape (1, n_features) for XGBoost."""
        fv = self._make()
        arr = fv.to_numpy()
        assert arr.shape == (1, len(ml_config.FEATURE_NAMES))

    def test_to_numpy_dtype_float32(self) -> None:
        """XGBoost expects float32 input."""
        fv = self._make()
        assert fv.to_numpy().dtype == np.float32

    def test_to_dataframe_column_order(self) -> None:
        """DataFrame columns must match FEATURE_NAMES exactly."""
        fv = self._make()
        df = fv.to_dataframe()
        assert list(df.columns) == ml_config.FEATURE_NAMES

    def test_to_dataframe_single_row(self) -> None:
        """DataFrame should have exactly 1 row."""
        fv = self._make()
        assert len(fv.to_dataframe()) == 1

    def test_to_dict_has_all_features(self) -> None:
        """to_dict() must include all 9 features."""
        fv = self._make()
        d = fv.to_dict()
        for name in ml_config.FEATURE_NAMES:
            assert name in d, f"Missing feature: {name}"


# =============================================================================
# Test: FeatureBuilder — time feature extraction
# =============================================================================

class TestFeatureBuilderTimeFeatures:

    def setup_method(self) -> None:
        self.builder = FeatureBuilder()

    def test_hour_extracted_correctly(self) -> None:
        """hour_of_day should match the hour from recorded_at."""
        dt = datetime(2026, 6, 15, 14, 30, tzinfo=timezone.utc)  # 14:30 UTC
        fv = self.builder.build_for_inference(queue_length=3, avg_service_time=120, recorded_at=dt)
        assert fv.hour_of_day == 14.0

    def test_monday_is_dow_0(self) -> None:
        """Monday should give day_of_week=0 and is_weekend=0."""
        monday = datetime(2026, 6, 22, 10, 0, tzinfo=timezone.utc)  # Known Monday
        fv = self.builder.build_for_inference(queue_length=2, avg_service_time=120, recorded_at=monday)
        assert fv.day_of_week == 0.0
        assert fv.is_weekend == 0.0

    def test_saturday_is_weekend(self) -> None:
        """Saturday should give is_weekend=1."""
        saturday = datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc)  # Known Saturday
        fv = self.builder.build_for_inference(queue_length=2, avg_service_time=120, recorded_at=saturday)
        assert fv.is_weekend == 1.0

    def test_month_extracted_correctly(self) -> None:
        dt = datetime(2026, 12, 25, 10, 0, tzinfo=timezone.utc)
        fv = self.builder.build_for_inference(queue_length=5, avg_service_time=120, recorded_at=dt)
        assert fv.month == 12.0

    def test_queue_length_stored_correctly(self) -> None:
        fv = self.builder.build_for_inference(queue_length=7, avg_service_time=120)
        assert fv.queue_length == 7.0

    def test_avg_service_time_stored(self) -> None:
        fv = self.builder.build_for_inference(queue_length=3, avg_service_time=90)
        assert fv.avg_service_time == 90.0

    def test_no_recent_snapshots_gives_zero_rolling(self) -> None:
        """With no history, all rolling features should be 0.0."""
        fv = self.builder.build_for_inference(queue_length=4, avg_service_time=120, recent_snapshots=[])
        assert fv.rolling_avg_30m == 0.0
        assert fv.rolling_avg_1h == 0.0
        assert fv.rolling_max_1h == 0.0


# =============================================================================
# Test: FeatureBuilder — rolling window computation
# =============================================================================

class TestRollingWindows:

    def setup_method(self) -> None:
        self.builder = FeatureBuilder()

    def _snap(self, queue_length: int, minutes_ago: int) -> dict:
        """Build a snapshot dict at N minutes ago."""
        return {
            "queue_length": queue_length,
            "recorded_at": datetime.now(tz=timezone.utc) - timedelta(minutes=minutes_ago),
        }

    def test_avg_30m_excludes_older_snapshots(self) -> None:
        """Snapshots older than 30 min should not affect avg_30m."""
        snaps = [
            self._snap(10, 5),   # within 30m  → included in 30m and 1h
            self._snap(6, 20),   # within 30m  → included in 30m and 1h
            self._snap(20, 40),  # outside 30m → only in 1h
            self._snap(4, 90),   # outside 1h  → excluded from both
        ]
        ref = datetime.now(tz=timezone.utc)
        avg_30m, avg_1h, max_1h = self.builder._compute_rolling(snaps, ref)
        assert avg_30m == pytest.approx(8.0)  # (10 + 6) / 2
        assert avg_1h == pytest.approx((10 + 6 + 20) / 3, abs=0.1)
        assert max_1h == 20.0

    def test_all_snapshots_outside_window_gives_zero(self) -> None:
        snaps = [self._snap(10, 120), self._snap(15, 90)]  # Both > 1h
        ref = datetime.now(tz=timezone.utc)
        avg_30m, avg_1h, max_1h = self.builder._compute_rolling(snaps, ref)
        assert avg_30m == 0.0
        assert avg_1h == 0.0
        assert max_1h == 0.0


# =============================================================================
# Test: FeatureBuilder — training dataset construction
# =============================================================================

class TestBuildTrainingDataframe:

    def setup_method(self) -> None:
        self.builder = FeatureBuilder()

    def _make_snapshot(self, queue_length: int, ewt: int, hours_ago: int) -> dict:
        return {
            "queue_length": queue_length,
            "estimated_wait_seconds": ewt,
            "recorded_at": datetime.now(tz=timezone.utc) - timedelta(hours=hours_ago),
        }

    def test_returns_dataframe_and_series(self) -> None:
        snaps = [self._make_snapshot(3, 360, h) for h in range(10, 0, -1)]
        X, y = self.builder.build_training_dataframe(snaps, avg_service_time=120)
        assert isinstance(X, pd.DataFrame)
        assert isinstance(y, pd.Series)

    def test_row_count_matches_valid_snapshots(self) -> None:
        snaps = [self._make_snapshot(i, i * 120, h) for i, h in enumerate(range(5, 0, -1))]
        X, y = self.builder.build_training_dataframe(snaps, avg_service_time=120)
        assert len(X) == len(snaps)
        assert len(y) == len(snaps)

    def test_null_ewt_rows_are_dropped(self) -> None:
        """Snapshots with null estimated_wait_seconds should be excluded."""
        snaps = [
            self._make_snapshot(3, 360, 5),
            {"queue_length": 5, "estimated_wait_seconds": None, "recorded_at": datetime.now(tz=timezone.utc)},
            self._make_snapshot(2, 240, 3),
        ]
        X, y = self.builder.build_training_dataframe(snaps, avg_service_time=120)
        assert len(X) == 2  # Null row excluded

    def test_feature_columns_match_config(self) -> None:
        snaps = [self._make_snapshot(4, 480, h) for h in range(5, 0, -1)]
        X, y = self.builder.build_training_dataframe(snaps, avg_service_time=120)
        assert list(X.columns) == ml_config.FEATURE_NAMES

    def test_empty_input_returns_empty_dataframe(self) -> None:
        X, y = self.builder.build_training_dataframe([], avg_service_time=120)
        assert X.empty
        assert y.empty
