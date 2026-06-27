"""
RetailFlow AI — Analytics Service

Business logic for the analytics dashboard, including:
  1. RBAC enforcement (same as queue/store — managers see only their stores)
  2. Time range normalization (parse days_back → from_dt, to_dt)
  3. Redis caching layer (avoid recomputing expensive aggregations)
  4. Response assembly (raw SQL dict → Pydantic schema)

Caching Strategy:
    ┌─────────────────────────────┬──────────────┬──────────┐
    │ Endpoint                    │ Cache TTL    │ Reason   │
    ├─────────────────────────────┼──────────────┼──────────┤
    │ Store Summary (≤24h)        │ 5 minutes    │ Live KPIs│
    │ Store Summary (>24h)        │ 1 hour       │ Historical│
    │ Peak Hours Heatmap (≤7d)    │ 15 minutes   │ Changes slowly │
    │ Peak Hours Heatmap (>7d)    │ 1 hour       │ Historical│
    │ Queue Trends (≤24h)         │ 5 minutes    │ Live chart│
    │ Counter Comparison          │ 5 minutes    │ Live table│
    └─────────────────────────────┴──────────────┴──────────┘

Cache Key Format:
    analytics:store:{store_id}:{metric}:{params_hash}
    where params_hash = first 8 chars of MD5({from_dt}:{to_dt}:{extra_params})
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.queue_state import _format_wait_time
from app.core.redis import RedisKeys
from app.models.user import User, UserRole
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.store_repository import StoreRepository
from app.schemas.analytics import (
    CounterComparisonResponse,
    CounterStats,
    HeatmapCell,
    PeakHoursHeatmap,
    QueueTrendsResponse,
    StoreSummaryAnalytics,
    TrendBucket,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Domain Exceptions
# =============================================================================

class AnalyticsStoreNotFoundError(Exception):
    """Store does not exist."""
    pass


class AnalyticsAccessDeniedError(Exception):
    """User not authorized to view this store's analytics."""
    pass


# =============================================================================
# Cache TTL Constants (seconds)
# =============================================================================

_TTL_LIVE = 5 * 60          # 5 minutes: for queries covering last 24h
_TTL_RECENT = 15 * 60       # 15 minutes: for queries covering last 7d
_TTL_HISTORICAL = 60 * 60   # 1 hour: for queries covering >7 days


def _cache_key(store_id: str, metric: str, **params: Any) -> str:
    """
    Build a deterministic Redis cache key for an analytics query.

    Example: analytics:store:abc123:summary:a1b2c3d4
    """
    params_str = ":".join(f"{k}={v}" for k, v in sorted(params.items()))
    params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
    return f"analytics:store:{store_id}:{metric}:{params_hash}"


def _choose_ttl(days_back: int) -> int:
    """Select cache TTL based on query look-back window."""
    if days_back <= 1:
        return _TTL_LIVE
    elif days_back <= 7:
        return _TTL_RECENT
    else:
        return _TTL_HISTORICAL


def _time_range(days_back: int = 1) -> tuple[datetime, datetime]:
    """Compute (from_dt, to_dt) for a look-back window ending now."""
    to_dt = datetime.now(tz=timezone.utc)
    from_dt = to_dt - timedelta(days=days_back)
    return from_dt, to_dt


# =============================================================================
# Analytics Service
# =============================================================================

class AnalyticsService:
    """
    Orchestrates analytics queries with RBAC checks and Redis caching.
    """

    def __init__(
        self,
        store_repo: StoreRepository,
        analytics_repo: AnalyticsRepository,
    ) -> None:
        self._store_repo = store_repo
        self._analytics_repo = analytics_repo

    # -------------------------------------------------------------------------
    # Internal: RBAC check
    # -------------------------------------------------------------------------

    async def _check_access(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        requesting_user: User,
    ) -> None:
        """Verify the user has access to this store's data."""
        store = await self._store_repo.get_by_id(db, store_id)
        if store is None:
            raise AnalyticsStoreNotFoundError(f"Store {store_id} not found")

        if requesting_user.role == UserRole.MANAGER:
            is_assigned = await self._store_repo.is_manager_of_store(
                db, requesting_user.id, store_id
            )
            if not is_assigned:
                raise AnalyticsAccessDeniedError(
                    "You are not assigned to this store"
                )

        return store

    # -------------------------------------------------------------------------
    # Internal: Cache helpers
    # -------------------------------------------------------------------------

    async def _get_cached(self, redis: Redis, key: str) -> Any | None:
        """Fetch a JSON-serialized value from Redis cache."""
        raw = await redis.get(key)
        if raw:
            logger.debug("Analytics cache hit", key=key)
            return json.loads(raw)
        return None

    async def _set_cached(
        self,
        redis: Redis,
        key: str,
        value: dict,
        ttl: int,
    ) -> None:
        """Store a JSON-serialized value in Redis cache with TTL."""
        await redis.setex(key, ttl, json.dumps(value, default=str))
        logger.debug("Analytics cache set", key=key, ttl=ttl)

    # -------------------------------------------------------------------------
    # Store Summary
    # -------------------------------------------------------------------------

    async def get_store_summary(
        self,
        db: AsyncSession,
        redis: Redis,
        store_id: uuid.UUID,
        requesting_user: User,
        days_back: int = 1,
    ) -> StoreSummaryAnalytics:
        """
        Get KPI summary for a store over the last N days.

        Served from Redis cache if available (5-min TTL for <1 day, 1h for historical).

        Returns:
            StoreSummaryAnalytics with all metric cards populated.
        """
        store = await self._check_access(db, store_id, requesting_user)
        from_dt, to_dt = _time_range(days_back)
        ttl = _choose_ttl(days_back)

        cache_key = _cache_key(
            str(store_id), "summary",
            from_dt=from_dt.isoformat(), to_dt=to_dt.isoformat()
        )

        # Try cache first
        cached = await self._get_cached(redis, cache_key)
        if cached:
            result = StoreSummaryAnalytics(**cached)
            result.cached = True
            return result

        # Cache miss — run DB query
        data = await self._analytics_repo.get_store_summary(db, store_id, from_dt, to_dt)

        summary = StoreSummaryAnalytics(
            store_id=str(store_id),
            store_name=store.name,
            period_from=from_dt,
            period_to=to_dt,
            total_snapshots=data["total_snapshots"],
            total_customers_estimated=data["total_customers_estimated"],
            avg_queue_length=data["avg_queue_length"],
            peak_queue_length=data["peak_queue_length"],
            avg_wait_seconds=data["avg_wait_seconds"],
            avg_wait_formatted=_format_wait_time(
                int(data["avg_wait_seconds"]) if data["avg_wait_seconds"] else None
            ),
            peak_wait_seconds=data["peak_wait_seconds"],
            busiest_hour=data["busiest_hour"],
            busiest_day_of_week=data["busiest_day_of_week"],
            active_counters=data["active_counters"],
            cached=False,
        )

        # Cache the result
        await self._set_cached(redis, cache_key, summary.model_dump(), ttl)

        logger.info(
            "Analytics summary computed",
            store_id=str(store_id),
            days_back=days_back,
            total_snapshots=data["total_snapshots"],
        )
        return summary

    # -------------------------------------------------------------------------
    # Peak Hours Heatmap
    # -------------------------------------------------------------------------

    async def get_peak_hours_heatmap(
        self,
        db: AsyncSession,
        redis: Redis,
        store_id: uuid.UUID,
        requesting_user: User,
        days_back: int = 30,
    ) -> PeakHoursHeatmap:
        """
        Generate the peak hours heatmap (7 days × 24 hours grid).

        More days_back = more stable pattern but includes older data.
        Recommended: 30 days for a reliable weekly pattern.

        Returns:
            PeakHoursHeatmap with intensity-normalized cells.
        """
        store = await self._check_access(db, store_id, requesting_user)
        from_dt, to_dt = _time_range(days_back)
        ttl = _choose_ttl(days_back)

        cache_key = _cache_key(
            str(store_id), "heatmap",
            from_dt=from_dt.date().isoformat(),
            to_dt=to_dt.date().isoformat(),
        )

        cached = await self._get_cached(redis, cache_key)
        if cached:
            result = PeakHoursHeatmap(**cached)
            result.cached = True
            return result

        rows = await self._analytics_repo.get_peak_hours_heatmap(
            db, store_id, from_dt, to_dt
        )

        # Normalize intensity: max avg_queue → intensity 1.0
        max_avg = max((r["avg_queue_length"] for r in rows), default=1.0) or 1.0

        cells = [
            HeatmapCell(
                day_of_week=row["day_of_week"],
                day_name=row["day_name"],
                hour_of_day=row["hour_of_day"],
                avg_queue_length=row["avg_queue_length"],
                sample_count=row["sample_count"],
                intensity=round(row["avg_queue_length"] / max_avg, 4),
            )
            for row in rows
        ]

        heatmap = PeakHoursHeatmap(
            store_id=str(store_id),
            store_name=store.name,
            days_back=days_back,
            cells=cells,
            max_avg_queue=max_avg,
            cached=False,
        )

        await self._set_cached(redis, cache_key, heatmap.model_dump(), ttl)
        return heatmap

    # -------------------------------------------------------------------------
    # Queue Trends
    # -------------------------------------------------------------------------

    async def get_queue_trends(
        self,
        db: AsyncSession,
        redis: Redis,
        store_id: uuid.UUID,
        requesting_user: User,
        days_back: int = 1,
        bucket_minutes: int = 60,
    ) -> QueueTrendsResponse:
        """
        Get queue trend data (for line/area charts).

        Args:
            days_back: Look-back window in days.
            bucket_minutes: Aggregation bucket width (15/60/1440 minutes).

        Returns:
            QueueTrendsResponse with time-bucketed data per counter.
        """
        store = await self._check_access(db, store_id, requesting_user)
        from_dt, to_dt = _time_range(days_back)
        ttl = _choose_ttl(days_back)

        cache_key = _cache_key(
            str(store_id), "trends",
            from_dt=from_dt.isoformat(),
            to_dt=to_dt.isoformat(),
            bucket=bucket_minutes,
        )

        cached = await self._get_cached(redis, cache_key)
        if cached:
            result = QueueTrendsResponse(**cached)
            result.cached = True
            return result

        rows = await self._analytics_repo.get_queue_trends(
            db, store_id, from_dt, to_dt, bucket_minutes
        )

        buckets = [
            TrendBucket(
                bucket_time=row["bucket_time"],
                counter_id=row["counter_id"],
                counter_number=None,  # Enriched in Phase 6+ frontend join
                avg_queue_length=row["avg_queue_length"],
                max_queue_length=row["max_queue_length"],
                sample_count=row["sample_count"],
            )
            for row in rows
        ]

        response = QueueTrendsResponse(
            store_id=str(store_id),
            store_name=store.name,
            from_dt=from_dt,
            to_dt=to_dt,
            bucket_minutes=bucket_minutes,
            buckets=buckets,
            cached=False,
        )

        await self._set_cached(redis, cache_key, response.model_dump(), ttl)
        return response

    # -------------------------------------------------------------------------
    # Counter Comparison
    # -------------------------------------------------------------------------

    async def get_counter_comparison(
        self,
        db: AsyncSession,
        redis: Redis,
        store_id: uuid.UUID,
        requesting_user: User,
        days_back: int = 7,
    ) -> CounterComparisonResponse:
        """
        Get performance ranking of all counters in a store.

        Returns counters ranked by avg_queue_length (rank 1 = most efficient).

        Used by the manager dashboard to identify which counters need attention.
        """
        store = await self._check_access(db, store_id, requesting_user)
        from_dt, to_dt = _time_range(days_back)
        ttl = _choose_ttl(days_back)

        cache_key = _cache_key(
            str(store_id), "comparison",
            from_dt=from_dt.isoformat(),
            to_dt=to_dt.isoformat(),
        )

        cached = await self._get_cached(redis, cache_key)
        if cached:
            result = CounterComparisonResponse(**cached)
            result.cached = True
            return result

        rows = await self._analytics_repo.get_counter_comparison(
            db, store_id, from_dt, to_dt
        )

        # Assign efficiency rank (position in sorted list, already sorted by avg_queue ASC)
        counter_stats = [
            CounterStats(
                counter_id=row["counter_id"],
                counter_number=row["counter_number"],
                label=row["label"],
                avg_queue_length=row["avg_queue_length"],
                peak_queue_length=row["peak_queue_length"],
                avg_wait_seconds=row["avg_wait_seconds"],
                avg_wait_formatted=_format_wait_time(
                    int(row["avg_wait_seconds"]) if row["avg_wait_seconds"] else None
                ),
                total_updates=row["total_updates"],
                efficiency_rank=rank + 1,
            )
            for rank, row in enumerate(rows)
        ]

        response = CounterComparisonResponse(
            store_id=str(store_id),
            store_name=store.name,
            period_from=from_dt,
            period_to=to_dt,
            counters=counter_stats,
            cached=False,
        )

        await self._set_cached(redis, cache_key, response.model_dump(), ttl)
        return response


# =============================================================================
# Dependency Factory
# =============================================================================

def get_analytics_service() -> AnalyticsService:
    """
    Factory for creating AnalyticsService with injected repositories.

    Usage:
        analytics_service: AnalyticsService = Depends(get_analytics_service)
    """
    return AnalyticsService(
        store_repo=StoreRepository(),
        analytics_repo=AnalyticsRepository(),
    )
