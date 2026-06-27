"""
RetailFlow AI — Queue Engine API Router

REST endpoints for the queue engine:

Real-Time State (hot path — reads from Redis):
  GET  /api/v1/queues/stores/{store_id}                  → Full store queue state
  GET  /api/v1/queues/stores/{store_id}/counters/{id}    → Single counter state

Queue Updates:
  POST /api/v1/queues/stores/{store_id}/counters/{id}/update  → Manual update

History & Analytics:
  GET  /api/v1/queues/stores/{store_id}/history          → Snapshot history

Alert Configuration:
  POST   /api/v1/queues/stores/{store_id}/alerts         → Create alert
  GET    /api/v1/queues/stores/{store_id}/alerts         → List alerts
  PATCH  /api/v1/queues/stores/{store_id}/alerts/{id}    → Update alert
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.dependencies import ManagerUser, get_current_active_user
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.queue import (
    AlertConfigRequest,
    AlertConfigResponse,
    CounterQueueState,
    QueueHistoryResponse,
    QueueUpdateRequest,
    StoreQueueState,
)
from app.services.queue_service import (
    AlertConfigNotFoundError,
    QueueAccessDeniedError,
    QueueCounterClosedError,
    QueueCounterNotFoundError,
    QueueService,
    QueueStoreNotFoundError,
    get_queue_service,
)

router = APIRouter()


def _raise_for_queue_errors(exc: Exception) -> None:
    """Central mapping of queue domain exceptions → HTTP status codes."""
    if isinstance(exc, (QueueStoreNotFoundError, QueueCounterNotFoundError, AlertConfigNotFoundError)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": str(exc)},
        )
    if isinstance(exc, QueueAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": str(exc)},
        )
    if isinstance(exc, QueueCounterClosedError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "COUNTER_CLOSED", "message": str(exc)},
        )
    raise exc


# =============================================================================
# Real-Time Queue State Endpoints
# =============================================================================

@router.get(
    "/stores/{store_id}",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[StoreQueueState],
    summary="Get real-time queue state for an entire store",
    description=(
        "Returns the current queue length and EWT for all counters. "
        "Reads from Redis — sub-millisecond latency. "
        "Poll this endpoint every 5 seconds for near-real-time dashboard updates. "
        "For true real-time, use the WebSocket endpoint (Phase 7)."
    ),
)
async def get_store_queue_state(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    queue_service: QueueService = Depends(get_queue_service),
) -> APIResponse[StoreQueueState]:
    """Get real-time queue state for an entire store."""
    try:
        state = await queue_service.get_store_queue_state(
            db, redis, store_id, current_user
        )
        return APIResponse(data=state, message="Queue state retrieved")
    except Exception as e:
        _raise_for_queue_errors(e)


@router.get(
    "/stores/{store_id}/counters/{counter_id}",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[CounterQueueState],
    summary="Get real-time queue state for a single counter",
)
async def get_counter_queue_state(
    store_id: uuid.UUID,
    counter_id: uuid.UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    queue_service: QueueService = Depends(get_queue_service),
) -> APIResponse[CounterQueueState]:
    """Get real-time state for a specific counter."""
    try:
        # Get the full store state and filter to requested counter
        store_state = await queue_service.get_store_queue_state(
            db, redis, store_id, current_user
        )
        counter_state = next(
            (c for c in store_state.counters if c.counter_id == counter_id),
            None,
        )
        if counter_state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "COUNTER_NOT_FOUND", "message": f"Counter {counter_id} not found in store"},
            )
        return APIResponse(data=counter_state, message="Counter state retrieved")
    except HTTPException:
        raise
    except Exception as e:
        _raise_for_queue_errors(e)


# =============================================================================
# Queue Update Endpoint
# =============================================================================

@router.post(
    "/stores/{store_id}/counters/{counter_id}/update",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[CounterQueueState],
    summary="Manually update a counter's queue length",
    description=(
        "Sets the queue length for a counter. "
        "Only works on OPEN counters. "
        "Triggers a Redis pub/sub event for connected WebSocket clients. "
        "Writes a QueueSnapshot to the database for analytics."
    ),
    responses={
        200: {"description": "Queue updated successfully"},
        403: {"description": "Not assigned to this store"},
        404: {"description": "Counter or store not found"},
        409: {"description": "Counter is closed — cannot update"},
    },
)
async def update_counter_queue(
    store_id: uuid.UUID,
    counter_id: uuid.UUID,
    data: QueueUpdateRequest,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    queue_service: QueueService = Depends(get_queue_service),
) -> APIResponse[CounterQueueState]:
    """Manually set the queue length for an open counter."""
    try:
        updated_state = await queue_service.update_counter_queue(
            db, redis, counter_id, data, current_user
        )
        return APIResponse(
            data=updated_state,
            message=f"Queue updated: {data.queue_length} customers waiting",
        )
    except Exception as e:
        _raise_for_queue_errors(e)


# =============================================================================
# Queue History Endpoint
# =============================================================================

@router.get(
    "/stores/{store_id}/history",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[QueueHistoryResponse],
    summary="Get queue snapshot history for a store",
    description=(
        "Returns time-series queue snapshots from the database. "
        "Use 'hours' to control the look-back window (default: last 24 hours). "
        "Used by the analytics dashboard for trend charts."
    ),
)
async def get_queue_history(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    hours: int = Query(default=24, ge=1, le=168, description="Look back N hours (1–168)"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    queue_service: QueueService = Depends(get_queue_service),
) -> APIResponse[QueueHistoryResponse]:
    """Get paginated queue snapshot history."""
    try:
        history = await queue_service.get_queue_history(
            db, store_id, current_user, hours=hours, page=page, limit=limit
        )
        return APIResponse(data=history, message=f"Retrieved {history.total} snapshots")
    except Exception as e:
        _raise_for_queue_errors(e)


# =============================================================================
# Alert Configuration Endpoints
# =============================================================================

@router.post(
    "/stores/{store_id}/alerts",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[AlertConfigResponse],
    summary="Create a queue alert threshold",
    description=(
        "Configure a queue length or wait time alert. "
        "Alerts fire when the threshold is exceeded and the cooldown has elapsed. "
        "counter_id=null → store-wide alert; counter_id=UUID → counter-specific."
    ),
)
async def create_alert(
    store_id: uuid.UUID,
    data: AlertConfigRequest,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    queue_service: QueueService = Depends(get_queue_service),
) -> APIResponse[AlertConfigResponse]:
    """Configure a new alert threshold for a store."""
    try:
        config = await queue_service.configure_alert(db, store_id, data, current_user)
        return APIResponse(
            data=config,
            message=f"Alert configured: {data.alert_type} >= {data.threshold}",
        )
    except Exception as e:
        _raise_for_queue_errors(e)


@router.get(
    "/stores/{store_id}/alerts",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[list[AlertConfigResponse]],
    summary="List alert configs for a store",
)
async def list_alerts(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    queue_service: QueueService = Depends(get_queue_service),
) -> APIResponse[list[AlertConfigResponse]]:
    """List all alert configurations for a store."""
    try:
        configs = await queue_service.list_alerts(db, store_id, current_user)
        return APIResponse(data=configs, message=f"Retrieved {len(configs)} alert configs")
    except Exception as e:
        _raise_for_queue_errors(e)


@router.patch(
    "/stores/{store_id}/alerts/{alert_id}",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[AlertConfigResponse],
    summary="Update an alert configuration",
    description="Toggle is_active, adjust threshold, or change cooldown.",
)
async def update_alert(
    store_id: uuid.UUID,
    alert_id: uuid.UUID,
    data: AlertConfigRequest,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
    queue_service: QueueService = Depends(get_queue_service),
) -> APIResponse[AlertConfigResponse]:
    """Update an existing alert configuration."""
    try:
        # Verify access first
        store = await queue_service._store_repo.get_by_id(db, store_id)
        if store is None:
            raise QueueStoreNotFoundError(f"Store {store_id} not found")

        config = await queue_service._alert_repo.get_by_id(db, alert_id)
        if config is None or config.store_id != store_id:
            raise AlertConfigNotFoundError(f"Alert config {alert_id} not found")

        updates = {
            "threshold": data.threshold,
            "cooldown_minutes": data.cooldown_minutes,
            "is_active": data.is_active,
            "alert_type": data.alert_type,
        }
        updated = await queue_service._alert_repo.update(db, config, updates)
        return APIResponse(
            data=AlertConfigResponse.model_validate(updated),
            message="Alert config updated",
        )
    except Exception as e:
        _raise_for_queue_errors(e)
