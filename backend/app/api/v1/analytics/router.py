"""
RetailFlow AI — Analytics API Router

REST endpoints for the analytics dashboard:

  GET /api/v1/analytics/stores/{store_id}/summary      → KPI metric cards
  GET /api/v1/analytics/stores/{store_id}/peak-hours   → Heatmap 7×24
  GET /api/v1/analytics/stores/{store_id}/trends       → Time-series trend
  GET /api/v1/analytics/stores/{store_id}/counters     → Counter comparison
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.dependencies import ManagerUser
from app.core.database import get_db
from app.core.redis import get_redis
from app.schemas.analytics import (
    CounterComparisonResponse,
    PeakHoursHeatmap,
    QueueTrendsResponse,
    StoreSummaryAnalytics,
)
from app.schemas.common import APIResponse
from app.services.analytics_service import (
    AnalyticsAccessDeniedError,
    AnalyticsService,
    AnalyticsStoreNotFoundError,
    get_analytics_service,
)

router = APIRouter()


def _raise_for_analytics_errors(exc: Exception) -> None:
    """Map analytics domain exceptions → HTTP status codes."""
    if isinstance(exc, AnalyticsStoreNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STORE_NOT_FOUND", "message": str(exc)},
        )
    if isinstance(exc, AnalyticsAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": str(exc)},
        )
    raise exc


# =============================================================================
# Endpoints
# =============================================================================

@router.get(
    "/stores/{store_id}/summary",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[StoreSummaryAnalytics],
    summary="Get store KPI summary",
    description=(
        "Returns high-level KPI metric cards for the analytics dashboard. "
        "Includes avg/peak queue, estimated throughput, busiest hour and day. "
        "Results cached in Redis (5min TTL for last 24h, 1h for historical)."
    ),
)
async def get_store_summary(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    days_back: int = Query(
        default=1,
        ge=1,
        le=90,
        description="Look-back window in days (1=last 24h, 7=last week, 30=last month)",
    ),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> APIResponse[StoreSummaryAnalytics]:
    """Get KPI summary with Redis caching."""
    try:
        summary = await analytics_service.get_store_summary(
            db, redis, store_id, current_user, days_back=days_back
        )
        cache_msg = " (cached)" if summary.cached else ""
        return APIResponse(
            data=summary,
            message=f"Summary retrieved for last {days_back} day(s){cache_msg}",
        )
    except Exception as e:
        _raise_for_analytics_errors(e)


@router.get(
    "/stores/{store_id}/peak-hours",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[PeakHoursHeatmap],
    summary="Get peak hours heatmap (7 days × 24 hours)",
    description=(
        "Returns a 7×24 grid of average queue lengths by day-of-week and hour-of-day. "
        "Each cell has a normalized intensity value (0.0–1.0) for heatmap coloring. "
        "Use 30 days for a stable pattern; 7 days for recent behavior."
    ),
)
async def get_peak_hours(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    days_back: int = Query(
        default=30,
        ge=7,
        le=90,
        description="Look-back window in days (minimum 7 for statistical validity)",
    ),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> APIResponse[PeakHoursHeatmap]:
    """Get peak hours heatmap for scheduling optimization."""
    try:
        heatmap = await analytics_service.get_peak_hours_heatmap(
            db, redis, store_id, current_user, days_back=days_back
        )
        return APIResponse(
            data=heatmap,
            message=f"Heatmap generated from last {days_back} days ({len(heatmap.cells)} data points)",
        )
    except Exception as e:
        _raise_for_analytics_errors(e)


@router.get(
    "/stores/{store_id}/trends",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[QueueTrendsResponse],
    summary="Get queue trend time series",
    description=(
        "Returns time-bucketed queue length data for line/area charts. "
        "Use bucket_minutes=15 for last 24h (dense), 60 for last 7d, 1440 for last 30d. "
        "Data is per-counter for counter comparison charts."
    ),
)
async def get_queue_trends(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    days_back: int = Query(default=1, ge=1, le=30, description="Look-back in days"),
    bucket_minutes: int = Query(
        default=60,
        description="Bucket size in minutes",
        examples=[15, 60, 1440],
    ),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> APIResponse[QueueTrendsResponse]:
    """Get time-bucketed queue trend data."""
    # Validate bucket_minutes
    allowed_buckets = [1, 5, 15, 30, 60, 1440]
    if bucket_minutes not in allowed_buckets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_BUCKET",
                "message": f"bucket_minutes must be one of {allowed_buckets}",
            },
        )

    try:
        trends = await analytics_service.get_queue_trends(
            db, redis, store_id, current_user,
            days_back=days_back, bucket_minutes=bucket_minutes,
        )
        return APIResponse(
            data=trends,
            message=f"Trends retrieved: {len(trends.buckets)} time buckets",
        )
    except Exception as e:
        _raise_for_analytics_errors(e)


@router.get(
    "/stores/{store_id}/counters",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[CounterComparisonResponse],
    summary="Compare counter performance",
    description=(
        "Returns a ranked comparison of all counters in a store. "
        "Rank 1 = shortest avg queue (most efficient). "
        "Helps managers identify underperforming counters that need attention."
    ),
)
async def get_counter_comparison(
    store_id: uuid.UUID,
    current_user: ManagerUser,
    days_back: int = Query(
        default=7,
        ge=1,
        le=30,
        description="Look-back window in days",
    ),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> APIResponse[CounterComparisonResponse]:
    """Get counter performance comparison table."""
    try:
        comparison = await analytics_service.get_counter_comparison(
            db, redis, store_id, current_user, days_back=days_back
        )
        return APIResponse(
            data=comparison,
            message=f"Counter comparison: {len(comparison.counters)} counters ranked",
        )
    except Exception as e:
        _raise_for_analytics_errors(e)
