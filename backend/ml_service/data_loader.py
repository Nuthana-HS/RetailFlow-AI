"""
RetailFlow AI — Training Data Loader

Fetches raw QueueSnapshot records from the database for ML training.

Query Design:
    Loads all snapshots for a store with non-null estimated_wait_seconds
    (null = no training label available).

    Joins with stores to get avg_service_time (needed as a feature).

    Returns plain Python dicts (not ORM objects) to avoid detached-instance
    errors when passing data to background threads.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queue import QueueSnapshot
from app.models.store import Store


class TrainingDataLoader:
    """Loads training data from the QueueSnapshot time-series table."""

    async def load(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        days_back: int = 30,
        min_samples: int = 50,
    ) -> tuple[list[dict], int, str | None]:
        """
        Load training data for a store.

        Args:
            store_id: Target store.
            days_back: How many days of history to include.
            min_samples: Minimum snapshots required. Returns error if fewer.

        Returns:
            Tuple of:
              - snapshots: List of dicts {queue_length, estimated_wait_seconds, recorded_at}
              - avg_service_time: Store's base service rate (seconds/customer)
              - error: Error message string, or None if successful
        """
        # Fetch store avg_service_time
        store_result = await db.execute(
            select(Store.avg_service_time).where(Store.id == store_id)
        )
        avg_service_time_row = store_result.one_or_none()
        if avg_service_time_row is None:
            return [], 0, f"Store {store_id} not found"

        avg_service_time = avg_service_time_row[0]

        # Time range
        to_dt = datetime.now(tz=timezone.utc)
        from_dt = to_dt - timedelta(days=days_back)

        # Fetch snapshots
        result = await db.execute(
            select(
                QueueSnapshot.queue_length,
                QueueSnapshot.estimated_wait_seconds,
                QueueSnapshot.recorded_at,
                QueueSnapshot.counter_id,
            ).where(
                and_(
                    QueueSnapshot.store_id == store_id,
                    QueueSnapshot.estimated_wait_seconds.isnot(None),
                    QueueSnapshot.recorded_at >= from_dt,
                    QueueSnapshot.recorded_at <= to_dt,
                )
            ).order_by(QueueSnapshot.recorded_at.asc())
        )

        rows = result.all()
        n = len(rows)

        if n < min_samples:
            return [], avg_service_time, (
                f"Insufficient training data. Need at least {min_samples} queue snapshots "
                f"with wait time data. Currently have: {n}. "
                f"Generate data by updating queue lengths via the Queue Engine API."
            )

        snapshots = [
            {
                "queue_length": row.queue_length,
                "estimated_wait_seconds": row.estimated_wait_seconds,
                "recorded_at": row.recorded_at,
                "counter_id": str(row.counter_id) if row.counter_id else None,
            }
            for row in rows
        ]

        return snapshots, avg_service_time, None

    async def load_recent_for_counter(
        self,
        db: AsyncSession,
        counter_id: uuid.UUID,
        minutes: int = 60,
        limit: int = 100,
    ) -> list[dict]:
        """
        Load recent snapshots for rolling average computation during inference.

        Args:
            counter_id: Target counter.
            minutes: Look-back window in minutes.
            limit: Max records to return.

        Returns:
            List of {queue_length, recorded_at} dicts, sorted oldest first.
        """
        from_dt = datetime.now(tz=timezone.utc) - timedelta(minutes=minutes)

        result = await db.execute(
            select(
                QueueSnapshot.queue_length,
                QueueSnapshot.recorded_at,
            )
            .where(
                and_(
                    QueueSnapshot.counter_id == counter_id,
                    QueueSnapshot.recorded_at >= from_dt,
                )
            )
            .order_by(QueueSnapshot.recorded_at.asc())
            .limit(limit)
        )

        return [
            {"queue_length": row.queue_length, "recorded_at": row.recorded_at}
            for row in result.all()
        ]
