"""
RetailFlow AI — Analytics Repository

All SQL aggregation queries for the analytics dashboard.

Query Design Principles:
    1. Use SQLAlchemy func.* for database-side aggregations (faster than Python)
    2. Push all filtering to WHERE clauses (use indexes on store_id + recorded_at)
    3. Return raw Row objects — schemas are assembled in the service layer
    4. All timestamps are in UTC; timezone conversion happens in the frontend

Performance Notes:
    The composite index idx_snapshots_store_time (store_id, recorded_at)
    on queue_snapshots makes all these queries O(log N) instead of O(N).

    For a store with 10 counters generating data for 1 year:
      ~10 × 12 × 24 × 365 = 1,051,200 rows
    With the index, each query scans only the date-range subset.
"""

import uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queue import QueueSnapshot
from app.models.store import Counter


# Day-of-week mapping (PostgreSQL DOW: 0=Sunday … 6=Saturday)
_DOW_NAMES = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
}


class AnalyticsRepository:
    """
    Data access layer for all analytics aggregations.

    All methods accept from_dt / to_dt datetime range parameters
    to support both real-time (last 24h) and historical (last 7d, 30d) views.
    """

    async def get_store_summary(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        from_dt: datetime,
        to_dt: datetime,
    ) -> dict[str, Any]:
        """
        Compute high-level KPI metrics for a store over a time period.

        Returns a dict with all fields needed to populate StoreSummaryAnalytics.

        Key queries:
            - AVG(queue_length): overall average
            - MAX(queue_length): peak
            - COUNT(*): total snapshots
            - SUM(queue_length): throughput estimator
            - EXTRACT(hour FROM recorded_at): busiest hour
        """
        time_filter = and_(
            QueueSnapshot.store_id == store_id,
            QueueSnapshot.recorded_at >= from_dt,
            QueueSnapshot.recorded_at <= to_dt,
        )

        # ── Core aggregations (single query) ──────────────────────────────────
        agg_result = await db.execute(
            select(
                func.count(QueueSnapshot.id).label("total_snapshots"),
                func.coalesce(func.sum(QueueSnapshot.queue_length), 0).label("total_customers"),
                func.coalesce(func.avg(QueueSnapshot.queue_length), 0).label("avg_queue"),
                func.coalesce(func.max(QueueSnapshot.queue_length), 0).label("peak_queue"),
                func.coalesce(func.avg(QueueSnapshot.estimated_wait_seconds), None).label("avg_wait"),
                func.coalesce(func.max(QueueSnapshot.estimated_wait_seconds), None).label("peak_wait"),
                func.count(
                    QueueSnapshot.counter_id.distinct()
                ).label("active_counters"),
            ).where(time_filter)
        )
        agg = agg_result.one()

        # ── Busiest hour (secondary query) ────────────────────────────────────
        hour_result = await db.execute(
            select(
                func.extract("hour", QueueSnapshot.recorded_at).label("hour"),
                func.avg(QueueSnapshot.queue_length).label("avg_queue"),
            )
            .where(time_filter)
            .group_by(text("hour"))
            .order_by(text("avg_queue DESC"))
            .limit(1)
        )
        busiest_hour_row = hour_result.one_or_none()
        busiest_hour = int(busiest_hour_row.hour) if busiest_hour_row else None

        # ── Busiest day of week (secondary query) ─────────────────────────────
        dow_result = await db.execute(
            select(
                func.extract("dow", QueueSnapshot.recorded_at).label("dow"),
                func.avg(QueueSnapshot.queue_length).label("avg_queue"),
            )
            .where(time_filter)
            .group_by(text("dow"))
            .order_by(text("avg_queue DESC"))
            .limit(1)
        )
        busiest_dow_row = dow_result.one_or_none()
        busiest_dow = None
        if busiest_dow_row:
            busiest_dow = _DOW_NAMES.get(int(busiest_dow_row.dow))

        return {
            "total_snapshots": agg.total_snapshots,
            "total_customers_estimated": int(agg.total_customers),
            "avg_queue_length": round(float(agg.avg_queue), 2),
            "peak_queue_length": int(agg.peak_queue),
            "avg_wait_seconds": float(agg.avg_wait) if agg.avg_wait else None,
            "peak_wait_seconds": int(agg.peak_wait) if agg.peak_wait else None,
            "busiest_hour": busiest_hour,
            "busiest_day_of_week": busiest_dow,
            "active_counters": agg.active_counters,
        }

    async def get_peak_hours_heatmap(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        from_dt: datetime,
        to_dt: datetime,
    ) -> list[dict[str, Any]]:
        """
        Compute the 7×24 peak hours heatmap.

        SQL:
            SELECT
                EXTRACT(dow FROM recorded_at) AS day_of_week,
                EXTRACT(hour FROM recorded_at) AS hour_of_day,
                AVG(queue_length)             AS avg_queue,
                COUNT(*)                      AS sample_count
            FROM queue_snapshots
            WHERE store_id = :store_id AND recorded_at BETWEEN :from AND :to
            GROUP BY day_of_week, hour_of_day
            ORDER BY day_of_week, hour_of_day

        Returns:
            List of dicts with keys: day_of_week, hour_of_day, avg_queue, sample_count.
        """
        result = await db.execute(
            select(
                func.extract("dow", QueueSnapshot.recorded_at).label("day_of_week"),
                func.extract("hour", QueueSnapshot.recorded_at).label("hour_of_day"),
                func.avg(QueueSnapshot.queue_length).label("avg_queue"),
                func.count(QueueSnapshot.id).label("sample_count"),
            )
            .where(
                QueueSnapshot.store_id == store_id,
                QueueSnapshot.recorded_at >= from_dt,
                QueueSnapshot.recorded_at <= to_dt,
            )
            .group_by(text("day_of_week"), text("hour_of_day"))
            .order_by(text("day_of_week"), text("hour_of_day"))
        )

        rows = result.all()
        return [
            {
                "day_of_week": int(row.day_of_week),
                "day_name": _DOW_NAMES.get(int(row.day_of_week), "Unknown"),
                "hour_of_day": int(row.hour_of_day),
                "avg_queue_length": round(float(row.avg_queue), 2),
                "sample_count": int(row.sample_count),
            }
            for row in rows
        ]

    async def get_queue_trends(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        from_dt: datetime,
        to_dt: datetime,
        bucket_minutes: int = 60,
    ) -> list[dict[str, Any]]:
        """
        Compute queue trend over time, bucketed by interval.

        Uses PostgreSQL date_trunc for time bucketing.
        Default: 1-hour buckets (good balance of resolution vs. data volume).

        Args:
            bucket_minutes: Width of each bucket in minutes.
                60  → hourly (good for last 7 days)
                15  → 15-min intervals (good for last 24 hours)
                1440 → daily (good for last 30 days)

        Returns:
            List of dicts with bucket_time, counter_id, avg/max queue.
        """
        # Map bucket_minutes to PostgreSQL date_trunc precision
        trunc_precision_map = {
            1: "minute",
            5: "minute",
            15: "minute",
            30: "minute",
            60: "hour",
            1440: "day",
        }
        precision = trunc_precision_map.get(bucket_minutes, "hour")

        result = await db.execute(
            select(
                func.date_trunc(precision, QueueSnapshot.recorded_at).label("bucket"),
                QueueSnapshot.counter_id.label("counter_id"),
                func.avg(QueueSnapshot.queue_length).label("avg_queue"),
                func.max(QueueSnapshot.queue_length).label("max_queue"),
                func.count(QueueSnapshot.id).label("sample_count"),
            )
            .where(
                QueueSnapshot.store_id == store_id,
                QueueSnapshot.recorded_at >= from_dt,
                QueueSnapshot.recorded_at <= to_dt,
            )
            .group_by(text("bucket"), QueueSnapshot.counter_id)
            .order_by(text("bucket"), QueueSnapshot.counter_id)
        )

        rows = result.all()
        return [
            {
                "bucket_time": row.bucket,
                "counter_id": str(row.counter_id) if row.counter_id else None,
                "avg_queue_length": round(float(row.avg_queue), 2),
                "max_queue_length": int(row.max_queue),
                "sample_count": int(row.sample_count),
            }
            for row in rows
        ]

    async def get_counter_comparison(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        from_dt: datetime,
        to_dt: datetime,
    ) -> list[dict[str, Any]]:
        """
        Compute per-counter performance stats for the comparison table.

        Joins queue_snapshots → counters to get counter_number and label.

        Returns a ranked list of counters sorted by avg_queue_length ASC
        (rank 1 = most efficient = shortest queues).
        """
        result = await db.execute(
            select(
                QueueSnapshot.counter_id.label("counter_id"),
                Counter.counter_number.label("counter_number"),
                Counter.label.label("label"),
                func.avg(QueueSnapshot.queue_length).label("avg_queue"),
                func.max(QueueSnapshot.queue_length).label("peak_queue"),
                func.avg(QueueSnapshot.estimated_wait_seconds).label("avg_wait"),
                func.count(QueueSnapshot.id).label("total_updates"),
            )
            .join(
                Counter,
                Counter.id == QueueSnapshot.counter_id,
                isouter=True,
            )
            .where(
                QueueSnapshot.store_id == store_id,
                QueueSnapshot.recorded_at >= from_dt,
                QueueSnapshot.recorded_at <= to_dt,
                QueueSnapshot.counter_id.isnot(None),
            )
            .group_by(
                QueueSnapshot.counter_id,
                Counter.counter_number,
                Counter.label,
            )
            .order_by(text("avg_queue ASC"))  # Best performers first
        )

        rows = result.all()
        return [
            {
                "counter_id": str(row.counter_id),
                "counter_number": row.counter_number or 0,
                "label": row.label,
                "avg_queue_length": round(float(row.avg_queue), 2),
                "peak_queue_length": int(row.peak_queue),
                "avg_wait_seconds": float(row.avg_wait) if row.avg_wait else None,
                "total_updates": int(row.total_updates),
            }
            for row in rows
        ]
