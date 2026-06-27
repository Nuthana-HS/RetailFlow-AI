"""
RetailFlow AI — ML Feature Engineering

Builds the feature vector used for both XGBoost training and inference.

Features Chosen (and Why):

1. queue_length         — Primary driver: more people = longer wait
2. hour_of_day (0–23)  — Rush hour effect: 12–14 is slower than 15–17
3. day_of_week (0–6)   — Weekend queues behave differently from weekdays
4. is_weekend (0/1)    — Explicit flag to help XGBoost learn the weekend pattern
5. month (1–12)        — Seasonal variation (festive season = longer queues)
6. rolling_avg_30m     — Recent trend: if the queue was growing, it may keep growing
7. rolling_avg_1h      — Longer trend: helps predict sustained peak periods
8. rolling_max_1h      — Peak in the last hour: indicates burst capacity events
9. avg_service_time    — Store-level base rate (seconds per customer)

Target:
    estimated_wait_seconds — EWT in seconds (from QueueSnapshot)

Training Labels Note:
    Initially, estimated_wait_seconds = queue_length × avg_service_time (formula).
    As real-world service time data is collected (e.g., from POS timestamps),
    the labels will reflect actual measured wait times rather than formula values.
    The model is designed for this progressive data quality improvement.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd


@dataclass
class FeatureVector:
    """
    A single feature vector for EWT prediction.

    Column order must match MLConfig.FEATURE_NAMES exactly.
    """

    queue_length: float
    hour_of_day: float
    day_of_week: float
    is_weekend: float
    month: float
    rolling_avg_30m: float
    rolling_avg_1h: float
    rolling_max_1h: float
    avg_service_time: float

    def to_numpy(self) -> np.ndarray:
        """Convert to 2D numpy array for XGBoost inference (shape: 1 × n_features)."""
        values = [
            self.queue_length, self.hour_of_day, self.day_of_week,
            self.is_weekend, self.month, self.rolling_avg_30m,
            self.rolling_avg_1h, self.rolling_max_1h, self.avg_service_time,
        ]
        return np.array([values], dtype=np.float32)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to single-row DataFrame with correct column names."""
        from ml_service.config import ml_config
        return pd.DataFrame([self.to_dict()], columns=ml_config.FEATURE_NAMES)


class FeatureBuilder:
    """
    Builds FeatureVector objects from raw QueueSnapshot data.

    Used in two contexts:
      1. TRAINING: builds a full feature matrix from historical snapshots
      2. INFERENCE: builds a single feature vector for a live prediction request
    """

    def build_for_inference(
        self,
        queue_length: int,
        avg_service_time: int,
        recorded_at: datetime | None = None,
        recent_snapshots: list[dict] | None = None,
    ) -> FeatureVector:
        """
        Build a feature vector for live EWT prediction.

        Args:
            queue_length: Current people in queue.
            avg_service_time: Store's avg seconds per customer.
            recorded_at: Timestamp for time features (defaults to now UTC).
            recent_snapshots: List of recent snapshot dicts {queue_length, recorded_at}
                              used to compute rolling averages. Pass [] if unavailable.

        Returns:
            FeatureVector ready for XGBoost inference.
        """
        if recorded_at is None:
            recorded_at = datetime.now(tz=timezone.utc)

        # Ensure timezone-aware for comparison
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=timezone.utc)

        hour = recorded_at.hour
        dow = recorded_at.weekday()  # Monday=0, Sunday=6
        is_weekend = 1 if dow >= 5 else 0
        month = recorded_at.month

        # Compute rolling averages from recent snapshots
        rolling_avg_30m, rolling_avg_1h, rolling_max_1h = self._compute_rolling(
            recent_snapshots or [], recorded_at
        )

        return FeatureVector(
            queue_length=float(queue_length),
            hour_of_day=float(hour),
            day_of_week=float(dow),
            is_weekend=float(is_weekend),
            month=float(month),
            rolling_avg_30m=rolling_avg_30m,
            rolling_avg_1h=rolling_avg_1h,
            rolling_max_1h=rolling_max_1h,
            avg_service_time=float(avg_service_time),
        )

    def _compute_rolling(
        self,
        snapshots: list[dict],
        reference_dt: datetime,
    ) -> tuple[float, float, float]:
        """
        Compute rolling avg_30m, avg_1h, max_1h from recent snapshots.

        Args:
            snapshots: List of {queue_length: int, recorded_at: datetime}.
            reference_dt: Compute rolling windows relative to this time.

        Returns:
            Tuple of (avg_30m, avg_1h, max_1h). Falls back to 0.0 if empty.
        """
        from datetime import timedelta

        if not snapshots:
            return 0.0, 0.0, 0.0

        window_30m = reference_dt - timedelta(minutes=30)
        window_1h = reference_dt - timedelta(hours=1)

        lengths_30m = []
        lengths_1h = []

        for snap in snapshots:
            snap_time = snap.get("recorded_at")
            snap_q = snap.get("queue_length", 0)

            if snap_time is None:
                continue

            # Ensure timezone-aware
            if hasattr(snap_time, "tzinfo") and snap_time.tzinfo is None:
                snap_time = snap_time.replace(tzinfo=timezone.utc)

            if snap_time >= window_1h:
                lengths_1h.append(snap_q)
            if snap_time >= window_30m:
                lengths_30m.append(snap_q)

        avg_30m = float(np.mean(lengths_30m)) if lengths_30m else 0.0
        avg_1h = float(np.mean(lengths_1h)) if lengths_1h else 0.0
        max_1h = float(max(lengths_1h)) if lengths_1h else 0.0

        return avg_30m, avg_1h, max_1h

    def build_training_dataframe(
        self,
        snapshots: list[dict],
        avg_service_time: int,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Build the full training dataset from historical QueueSnapshot records.

        Args:
            snapshots: Raw snapshot dicts from DB:
                {queue_length, estimated_wait_seconds, recorded_at}
            avg_service_time: Store-level average service time (seconds).

        Returns:
            Tuple of (X: feature DataFrame, y: target Series).
            Rows with null estimated_wait_seconds are dropped (no training label).
        """
        rows = []
        # Sort by time for rolling window computation
        sorted_snaps = sorted(snapshots, key=lambda s: s.get("recorded_at", datetime.min))

        for i, snap in enumerate(sorted_snaps):
            ewt = snap.get("estimated_wait_seconds")
            if ewt is None:
                continue  # No training label

            recorded_at = snap.get("recorded_at")
            if recorded_at is None:
                continue

            # Use all snapshots BEFORE this one for rolling features
            previous = sorted_snaps[:i]

            features = self.build_for_inference(
                queue_length=snap.get("queue_length", 0),
                avg_service_time=avg_service_time,
                recorded_at=recorded_at if hasattr(recorded_at, "hour") else None,
                recent_snapshots=previous,
            )

            row = features.to_dict()
            row["target_ewt"] = float(ewt)
            rows.append(row)

        if not rows:
            return pd.DataFrame(), pd.Series(dtype=float)

        df = pd.DataFrame(rows)
        from ml_service.config import ml_config
        X = df[ml_config.FEATURE_NAMES]
        y = df["target_ewt"]

        return X, y
