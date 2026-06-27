"""
RetailFlow AI — Camera Zone Repository

Data access layer for CameraZone records.

The CV service reads from this table at startup to discover all active zones.
Admin/Manager APIs write to this table to configure zones.
"""

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import CameraZone


class CameraRepository:
    """CRUD operations for CameraZone records."""

    async def create(
        self,
        db: AsyncSession,
        *,
        counter_id: uuid.UUID,
        store_id: uuid.UUID,
        camera_source: str,
        camera_url: str | None,
        zone_x1: float,
        zone_y1: float,
        zone_x2: float,
        zone_y2: float,
        frame_width: int = 1280,
        frame_height: int = 720,
        min_confidence: float = 0.45,
        update_interval_seconds: int = 5,
    ) -> CameraZone:
        """Create a new camera zone for a counter."""
        zone = CameraZone(
            counter_id=counter_id,
            store_id=store_id,
            camera_source=camera_source,
            camera_url=camera_url,
            zone_x1=zone_x1,
            zone_y1=zone_y1,
            zone_x2=zone_x2,
            zone_y2=zone_y2,
            frame_width=frame_width,
            frame_height=frame_height,
            min_confidence=min_confidence,
            update_interval_seconds=update_interval_seconds,
        )
        db.add(zone)
        await db.flush()
        await db.refresh(zone)
        return zone

    async def get_by_counter(
        self,
        db: AsyncSession,
        counter_id: uuid.UUID,
    ) -> CameraZone | None:
        """Fetch the zone for a specific counter (one-to-one)."""
        result = await db.execute(
            select(CameraZone).where(CameraZone.counter_id == counter_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        db: AsyncSession,
        zone_id: uuid.UUID,
    ) -> CameraZone | None:
        """Fetch a zone by its primary key."""
        result = await db.execute(
            select(CameraZone).where(CameraZone.id == zone_id)
        )
        return result.scalar_one_or_none()

    async def get_all_active_for_store(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
    ) -> Sequence[CameraZone]:
        """
        Fetch all active zones for a store.

        Called by the CV service processor at startup to configure
        one detection pipeline per zone.
        """
        result = await db.execute(
            select(CameraZone).where(
                CameraZone.store_id == store_id,
                CameraZone.is_active == True,  # noqa: E712
            )
        )
        return result.scalars().all()

    async def update(
        self,
        db: AsyncSession,
        zone: CameraZone,
        updates: dict,
    ) -> CameraZone:
        """Apply partial updates to a camera zone."""
        for field, value in updates.items():
            setattr(zone, field, value)
        await db.flush()
        await db.refresh(zone)
        return zone

    async def delete(
        self,
        db: AsyncSession,
        zone: CameraZone,
    ) -> None:
        """Delete a camera zone (hard delete — no historical impact)."""
        await db.delete(zone)
        await db.flush()
