"""
RetailFlow AI — XGBoost Training Pipeline

Trains a gradient boosted tree model to predict estimated wait time (EWT)
from queue state and time-of-day/day-of-week features.

Model: XGBRegressor
    - Objective: reg:squarederror (minimize RMSE)
    - Evaluation metric: MAE (more interpretable than RMSE for wait times)
    - Early stopping: prevents overfitting on small datasets

Training Split:
    80% train / 20% validation
    Chronological split (NOT random) — critical for time-series data.
    Random split would leak future data into training (data leakage).

Metrics:
    MAE   — Mean Absolute Error in seconds (primary metric)
    RMSE  — Root Mean Squared Error (penalizes large errors more)
    R²    — Coefficient of determination (how much variance explained)
    MAE interpretation: MAE of 45s → average prediction off by < 1 min (good)
"""

from __future__ import annotations

import logging
import pickle
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TrainingMetrics:
    """Evaluation metrics from a training run."""

    mae: float = 0.0              # Mean Absolute Error (seconds)
    rmse: float = 0.0             # Root Mean Squared Error (seconds)
    r2: float = 0.0               # R-squared (0–1, higher = better)
    n_train: int = 0              # Training samples
    n_val: int = 0                # Validation samples
    feature_importances: dict[str, float] = field(default_factory=dict)


@dataclass
class TrainedModel:
    """A trained XGBoost model with its metadata."""

    model_id: str
    store_id: str
    trained_at: str               # ISO 8601 UTC
    n_samples: int
    feature_names: list[str]
    metrics: TrainingMetrics
    model_version: str = "xgboost"

    # The actual model object (not serialized in metadata)
    _model: object = field(default=None, repr=False, compare=False)


class XGBoostTrainer:
    """
    Trains and persists an XGBoost regression model for EWT prediction.

    Usage:
        trainer = XGBoostTrainer()
        trained = await trainer.train(X, y, store_id=store_id)
        trainer.save(trained, model_path)
    """

    def __init__(self) -> None:
        from ml_service.config import ml_config
        self._config = ml_config

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        store_id: str,
    ) -> TrainedModel:
        """
        Train an XGBoost model with chronological train/val split.

        Args:
            X: Feature DataFrame with columns matching FEATURE_NAMES.
            y: Target Series of estimated_wait_seconds.
            store_id: Used for model ID and metadata.

        Returns:
            TrainedModel with the fitted model and evaluation metrics.

        Raises:
            ImportError: If xgboost is not installed.
            ValueError: If dataset is too small or features are mismatched.
        """
        try:
            import xgboost as xgb
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        except ImportError as exc:
            raise ImportError(
                "xgboost and scikit-learn are required. "
                "Install with: pip install xgboost scikit-learn"
            ) from exc

        n = len(X)
        if n < 2:
            raise ValueError(f"Need at least 2 samples to train, got {n}")

        logger.info(f"Training XGBoost EWT model: store={store_id}, samples={n}")

        # Chronological split — NEVER use random split for time-series
        split_idx = int(n * 0.8)
        split_idx = max(1, min(split_idx, n - 1))

        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

        # Build XGBoost model
        model = xgb.XGBRegressor(
            n_estimators=self._config.XGB_N_ESTIMATORS,
            max_depth=self._config.XGB_MAX_DEPTH,
            learning_rate=self._config.XGB_LEARNING_RATE,
            subsample=self._config.XGB_SUBSAMPLE,
            colsample_bytree=self._config.XGB_COLSAMPLE_BYTREE,
            objective="reg:squarederror",
            eval_metric="mae",
            early_stopping_rounds=20,
            random_state=self._config.XGB_RANDOM_STATE,
            n_jobs=-1,
            verbosity=0,
        )

        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        # Evaluate on validation set
        y_pred = model.predict(X_val)
        mae = float(mean_absolute_error(y_val, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_val, y_pred)))
        r2 = float(r2_score(y_val, y_pred)) if len(y_val) > 1 else 0.0

        # Feature importances (gain — most reliable XGBoost importance metric)
        feature_importances = {
            name: round(float(imp), 6)
            for name, imp in zip(
                self._config.FEATURE_NAMES,
                model.feature_importances_,
            )
        }

        metrics = TrainingMetrics(
            mae=round(mae, 2),
            rmse=round(rmse, 2),
            r2=round(r2, 4),
            n_train=len(X_train),
            n_val=len(X_val),
            feature_importances=feature_importances,
        )

        model_id = f"ewt_{store_id[:8]}_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        trained = TrainedModel(
            model_id=model_id,
            store_id=store_id,
            trained_at=datetime.now(tz=timezone.utc).isoformat(),
            n_samples=n,
            feature_names=self._config.FEATURE_NAMES,
            metrics=metrics,
        )
        trained._model = model

        logger.info(
            f"XGBoost training complete: MAE={mae:.1f}s RMSE={rmse:.1f}s R²={r2:.3f}"
        )
        return trained

    def save(self, trained: TrainedModel, path: Path) -> None:
        """Serialize the trained model to disk using pickle."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(trained._model, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info(f"Model saved: {path} ({path.stat().st_size / 1024:.1f} KB)")

    def load(self, path: Path) -> object:
        """Load a trained model from disk."""
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        with open(path, "rb") as f:
            model = pickle.load(f)
        logger.info(f"Model loaded: {path}")
        return model

    def get_model_path(self, store_id: str) -> Path:
        """Compute the model file path for a store."""
        return self._config.MODEL_DIR / f"ewt_model_{store_id}.pkl"
