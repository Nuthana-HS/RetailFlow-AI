"""
RetailFlow AI — ML API Router

Endpoints for training and serving the XGBoost EWT prediction model.

  POST /api/v1/ml/stores/{store_id}/train      → Train model for this store
  GET  /api/v1/ml/stores/{store_id}/model      → Model info and metrics
  POST /api/v1/ml/stores/{store_id}/predict    → Predict EWT for given features
  GET  /api/v1/ml/stores/{store_id}/counters/{counter_id}/predict
                                               → Live prediction using current queue state
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.dependencies import ManagerUser
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.user import UserRole
from app.repositories.store_repository import StoreRepository
from app.schemas.common import APIResponse
from ml_service.config import ml_config
from ml_service.data_loader import TrainingDataLoader
from ml_service.features import FeatureBuilder
from ml_service.predictor import get_predictor, invalidate_predictor
from ml_service.trainer import XGBoostTrainer

router = APIRouter()
_store_repo = StoreRepository()
_data_loader = TrainingDataLoader()
_feature_builder = FeatureBuilder()
_trainer = XGBoostTrainer()


# =============================================================================
# Request / Response Schemas
# =============================================================================

class PredictRequest(BaseModel):
    """Request body for a manual EWT prediction."""
    queue_length: int = Field(..., ge=0, le=500)
    counter_id: str = Field(..., description="Counter UUID (used for cache key)")
    avg_service_time: int = Field(default=120, ge=1, description="Seconds per customer")


class PredictResponse(BaseModel):
    """EWT prediction result."""
    predicted_wait_seconds: int
    predicted_wait_formatted: str
    queue_length: int
    from_cache: bool
    model_loaded: bool
    store_id: str


class TrainResponse(BaseModel):
    """Result of a training run."""
    model_id: str
    store_id: str
    trained_at: str
    n_samples: int
    n_train: int
    n_val: int
    mae_seconds: float
    rmse_seconds: float
    r2: float
    feature_importances: dict[str, float]
    message: str


class ModelInfoResponse(BaseModel):
    """Metadata about the currently loaded model for a store."""
    store_id: str
    model_loaded: bool
    model_metadata: dict | None


# =============================================================================
# Helpers
# =============================================================================

def _format_wait(seconds: int) -> str:
    """Format seconds into human-readable wait time string."""
    if seconds <= 0:
        return "< 1 min"
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


async def _check_store_access(db, store_id, user) -> None:
    store = await _store_repo.get_by_id(db, store_id)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STORE_NOT_FOUND", "message": f"Store {store_id} not found"},
        )
    if user.role == UserRole.MANAGER:
        if not await _store_repo.is_manager_of_store(db, user.id, store_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Not assigned to this store"},
            )
    return store


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/stores/{store_id}/train",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[TrainResponse],
    summary="Train XGBoost EWT model for a store",
    description=(
        "Trains a gradient-boosted tree model on the store's historical queue snapshots. "
        "Uses a chronological 80/20 train/validation split (no data leakage). "
        "Requires a minimum of 50 queue snapshot records with wait time data."
    ),
)
async def train_model(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    days_back: int = Query(default=30, ge=7, le=365, description="Training data window (days)"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[TrainResponse]:
    """Train an XGBoost EWT prediction model for a store."""
    store = await _check_store_access(db, store_id, current_user)

    # Load training data
    snapshots, avg_service_time, error = await _data_loader.load(
        db,
        store_id=store_id,
        days_back=days_back,
        min_samples=ml_config.MIN_TRAINING_SAMPLES,
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INSUFFICIENT_DATA", "message": error},
        )

    # Build feature matrix
    X, y = _feature_builder.build_training_dataframe(
        snapshots, avg_service_time=avg_service_time
    )

    if X.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_FEATURES", "message": "No valid training rows after feature engineering"},
        )

    # Train
    try:
        trained = _trainer.train(X, y, store_id=str(store_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "TRAINING_FAILED", "message": f"Training error: {exc}"},
        )

    # Persist model to disk
    model_path = _trainer.get_model_path(str(store_id))
    _trainer.save(trained, model_path)

    # Cache metadata in Redis
    meta = {
        "model_id": trained.model_id,
        "store_id": str(store_id),
        "store_name": store.name,
        "trained_at": trained.trained_at,
        "n_samples": trained.n_samples,
        "n_train": trained.metrics.n_train,
        "n_val": trained.metrics.n_val,
        "mae": trained.metrics.mae,
        "rmse": trained.metrics.rmse,
        "r2": trained.metrics.r2,
        "feature_importances": trained.metrics.feature_importances,
    }
    await redis.setex(
        ml_config.model_meta_key(str(store_id)),
        ml_config.METADATA_CACHE_TTL,
        json.dumps(meta),
    )

    # Reload predictor so next predict call uses the fresh model
    invalidate_predictor(str(store_id))

    return APIResponse(
        data=TrainResponse(
            model_id=trained.model_id,
            store_id=str(store_id),
            trained_at=trained.trained_at,
            n_samples=trained.n_samples,
            n_train=trained.metrics.n_train,
            n_val=trained.metrics.n_val,
            mae_seconds=trained.metrics.mae,
            rmse_seconds=trained.metrics.rmse,
            r2=trained.metrics.r2,
            feature_importances=trained.metrics.feature_importances,
            message=(
                f"Model trained on {trained.n_samples} samples. "
                f"MAE: {trained.metrics.mae:.1f}s | R²: {trained.metrics.r2:.3f}"
            ),
        ),
        message="XGBoost model trained and saved successfully",
    )


@router.get(
    "/stores/{store_id}/model",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[ModelInfoResponse],
    summary="Get model info for a store",
)
async def get_model_info(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[ModelInfoResponse]:
    """Get metadata about the currently trained model."""
    await _check_store_access(db, store_id, current_user)

    predictor = get_predictor(str(store_id), redis)
    model_loaded = predictor.is_model_loaded()

    # Fetch metadata from Redis cache
    meta_raw = await redis.get(ml_config.model_meta_key(str(store_id)))
    meta = json.loads(meta_raw) if meta_raw else None

    return APIResponse(
        data=ModelInfoResponse(
            store_id=str(store_id),
            model_loaded=model_loaded,
            model_metadata=meta,
        ),
        message="Model info retrieved" if model_loaded else "No trained model — use POST /train first",
    )


@router.post(
    "/stores/{store_id}/predict",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[PredictResponse],
    summary="Predict EWT from a custom feature set",
    description=(
        "Predicts estimated wait time (seconds) for a given queue length. "
        "Uses the XGBoost model if trained; falls back to the linear formula otherwise. "
        "Results are cached in Redis for 60 seconds per (store, counter, queue_length, hour, dow)."
    ),
)
async def predict_ewt(
    store_id: uuid.UUID,
    data: PredictRequest,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[PredictResponse]:
    """Predict EWT for a given queue state."""
    store = await _check_store_access(db, store_id, current_user)

    features = _feature_builder.build_for_inference(
        queue_length=data.queue_length,
        avg_service_time=data.avg_service_time,
    )

    predictor = get_predictor(str(store_id), redis)
    seconds, from_cache = await predictor.predict_cached(
        features, store_id=str(store_id), counter_id=data.counter_id
    )

    return APIResponse(
        data=PredictResponse(
            predicted_wait_seconds=seconds,
            predicted_wait_formatted=_format_wait(seconds),
            queue_length=data.queue_length,
            from_cache=from_cache,
            model_loaded=predictor.is_model_loaded(),
            store_id=str(store_id),
        ),
        message=f"EWT: {_format_wait(seconds)} {'(cached)' if from_cache else '(fresh)'}",
    )


@router.get(
    "/stores/{store_id}/counters/{counter_id}/predict",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[PredictResponse],
    summary="Live EWT prediction using current queue state",
    description=(
        "Automatically fetches the current queue state from Redis + recent DB snapshots, "
        "builds the full feature vector, and returns an ML-powered EWT prediction."
    ),
)
async def predict_live(
    store_id: uuid.UUID,
    counter_id: uuid.UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[PredictResponse]:
    """Live EWT prediction for a specific counter using current queue state."""
    from app.core.queue_state import QueueStateManager

    store = await _check_store_access(db, store_id, current_user)

    # Get current queue state from Redis
    queue_state = await QueueStateManager.get_counter_state(
        redis, str(store_id), str(counter_id)
    )

    if queue_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NO_QUEUE_STATE",
                "message": "No queue state found. Update the counter queue first.",
            },
        )

    queue_length = queue_state.get("queue_length", 0)

    # Load recent snapshots for rolling features
    recent = await _data_loader.load_recent_for_counter(
        db, counter_id=counter_id, minutes=60
    )

    features = _feature_builder.build_for_inference(
        queue_length=queue_length,
        avg_service_time=store.avg_service_time,
        recent_snapshots=recent,
    )

    predictor = get_predictor(str(store_id), redis)
    seconds, from_cache = await predictor.predict_cached(
        features, store_id=str(store_id), counter_id=str(counter_id)
    )

    return APIResponse(
        data=PredictResponse(
            predicted_wait_seconds=seconds,
            predicted_wait_formatted=_format_wait(seconds),
            queue_length=queue_length,
            from_cache=from_cache,
            model_loaded=predictor.is_model_loaded(),
            store_id=str(store_id),
        ),
        message=f"Live EWT: {_format_wait(seconds)} (queue: {queue_length})",
    )
