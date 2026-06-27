"""
RetailFlow AI — Queue Snapshot Repository

Data access layer for QueueSnapshot (append-only time-series writes)
and AlertConfig CRUD operations.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queue import AlertConfig, AlertType, QueueSnapshot, QueueUpdateSource


class QueueRepository:
    """
    Data access layer for QueueSnapshot records.

    Write pattern: append-only inserts (high frequency).
    Read pattern: time-range queries for analytics.
    """

    async def insert_snapshot(
        self,
        db: AsyncSession,
        *,
        counter_id: uuid.UUID | None,
        store_id: uuid.UUID,
        queue_length: int,
        estimated_wait_seconds: int | None,
        source: QueueUpdateSource,
        people_served: int | None = None,
    ) -> QueueSnapshot:
        """
        Insert a new queue snapshot.

        This is the primary write path of the queue engine.
        Called on every manual update, CV frame, or ML prediction.

        Note: Session commit is handled by the FastAPI get_db() dependency.
        """
        snapshot = QueueSnapshot(
            counter_id=counter_id,
            store_id=store_id,
            queue_length=queue_length,
            estimated_wait_seconds=estimated_wait_seconds,
            source=source,
            people_served=people_served,
        )
        db.add(snapshot)
        await db.flush()
        return snapshot

    async def get_recent_for_counter(
        self,
        db: AsyncSession,
        counter_id: uuid.UUID,
        limit: int = 50,
    ) -> Sequence[QueueSnapshot]:
        """
        Fetch the most recent snapshots for a counter.

        Used by the analytics dashboard for sparkline charts.

        Returns:
            Snapshots ordered by recorded_at DESC (most recent first).
        """
        result = await db.execute(
            select(QueueSnapshot)
            .where(QueueSnapshot.counter_id == counter_id)
            .order_by(QueueSnapshot.recorded_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_history_for_store(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        from_dt: datetime,
        to_dt: datetime,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[QueueSnapshot], int]:
        """
        Fetch queue snapshots for a store within a time range.

        Args:
            from_dt: Start of time range (UTC).
            to_dt: End of time range (UTC).
            skip: Pagination offset.
            limit: Max records to return.

        Returns:
            Tuple of (snapshots, total_count).
        """
        from sqlalchemy import func
        query = (
            select(QueueSnapshot)
            .where(
                QueueSnapshot.store_id == store_id,
                QueueSnapshot.recorded_at >= from_dt,
                QueueSnapshot.recorded_at <= to_dt,
            )
        )

        count_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        result = await db.execute(
            query.offset(skip).limit(limit).order_by(QueueSnapshot.recorded_at.desc())
        )
        return result.scalars().all(), total


class AlertRepository:
    """Data access layer for AlertConfig records."""

    async def create(
        self,
        db: AsyncSession,
        *,
        store_id: uuid.UUID,
        counter_id: uuid.UUID | None,
        alert_type: AlertType,
        threshold: int,
        cooldown_minutes: int,
    ) -> AlertConfig:
        """Create a new alert configuration."""
        config = AlertConfig(
            store_id=store_id,
            counter_id=counter_id,
            alert_type=alert_type,
            threshold=threshold,
            cooldown_minutes=cooldown_minutes,
        )
        db.add(config)
        await db.flush()
        await db.refresh(config)
        return config

    async def get_by_id(
        self,
        db: AsyncSession,
        alert_id: uuid.UUID,
    ) -> AlertConfig | None:
        """Fetch an alert config by UUID."""
        result = await db.execute(
            select(AlertConfig).where(AlertConfig.id == alert_id)
        )
        return result.scalar_one_or_none()

    async def list_for_store(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        active_only: bool = False,
    ) -> Sequence[AlertConfig]:
        """
        List all alert configs for a store (including counter-specific ones).

        Args:
            active_only: If True, only return configs with is_active=True.
        """
        query = select(AlertConfig).where(AlertConfig.store_id == store_id)
        if active_only:
            query = query.where(AlertConfig.is_active == True)  # noqa: E712
        result = await db.execute(query.order_by(AlertConfig.created_at.desc()))
        return result.scalars().all()

    async def update(
        self,
        db: AsyncSession,
        config: AlertConfig,
        updates: dict,
    ) -> AlertConfig:
        """Apply partial updates to an alert config."""
        for field, value in updates.items():
            setattr(config, field, value)
        await db.flush()
        await db.refresh(config)
        return config

    async def get_active_for_store(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
    ) -> Sequence[AlertConfig]:
        """
        Fetch all active alert configs for a store.

        Used by the alert checker after every queue update.
        Checks both store-level (counter_id IS NULL) and
        counter-specific configs.
        """
        result = await db.execute(
            select(AlertConfig).where(
                AlertConfig.store_id == store_id,
                AlertConfig.is_active == True,  # noqa: E712
            ).order_by(AlertConfig.counter_id.nulls_first())  # Store-level first
        )
        return result.scalars().all()

    async def record_trigger(
        self,
        db: AsyncSession,
        alert_id: uuid.UUID,
    ) -> None:
        """Update last_triggered_at to now (enforces cooldown)."""
        from sqlalchemy import update
        await db.execute(
            update(AlertConfig)
            .where(AlertConfig.id == alert_id)
            .values(last_triggered_at=datetime.now(tz=timezone.utc))
        )
        await db.flush()

    async def is_in_cooldown(
        self,
        config: AlertConfig,
    ) -> bool:
        """
        Check if this alert config is currently in its cooldown period.

        Returns:
            True if the cooldown has not elapsed (do not fire alert).
        """
        if config.last_triggered_at is None:
            return False
        cooldown_end = config.last_triggered_at + timedelta(
            minutes=config.cooldown_minutes
        )
        return datetime.now(tz=timezone.utc) < cooldown_end
