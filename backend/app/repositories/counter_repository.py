"""
RetailFlow AI — Counter Repository

Data access layer for Counter operations.
Counters are soft-deleted to preserve queue history for analytics.
"""

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store import Counter, CounterStatus


class CounterRepository:
    """
    Data access layer for Counter operations.

    Key Design: Soft-delete pattern — counters are never physically removed
    because Phase 5 queue snapshots will reference counter IDs.
    All list queries filter `is_deleted == False` by default.
    """

    async def create(
        self,
        db: AsyncSession,
        *,
        store_id: uuid.UUID,
        counter_number: int,
        label: str | None,
        status: CounterStatus,
    ) -> Counter:
        """
        Create a new counter for a store.

        Args:
            store_id: The store this counter belongs to.
            counter_number: The display number (must be unique per store).
            label: Optional friendly label (e.g., "Express Lane").
            status: Initial operational status (default: CLOSED).

        Returns:
            The newly created Counter instance.
        """
        counter = Counter(
            store_id=store_id,
            counter_number=counter_number,
            label=label,
            status=status,
        )
        db.add(counter)
        await db.flush()
        await db.refresh(counter)
        return counter

    async def get_by_id(
        self,
        db: AsyncSession,
        counter_id: uuid.UUID,
    ) -> Counter | None:
        """
        Fetch a counter by UUID (only non-deleted counters).

        Returns:
            Counter instance or None if not found or soft-deleted.
        """
        result = await db.execute(
            select(Counter).where(
                Counter.id == counter_id,
                Counter.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_store(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        status: CounterStatus | None = None,
    ) -> Sequence[Counter]:
        """
        List all active (non-deleted) counters for a store.

        Args:
            store_id: Filter by store.
            status: Optional filter by counter status.

        Returns:
            Sequence of Counter instances ordered by counter_number.
        """
        query = select(Counter).where(
            Counter.store_id == store_id,
            Counter.is_deleted == False,  # noqa: E712
        )

        if status is not None:
            query = query.where(Counter.status == status)

        result = await db.execute(
            query.order_by(Counter.counter_number)
        )
        return result.scalars().all()

    async def counter_number_exists(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        counter_number: int,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check if a counter number already exists in a store.

        Used to enforce the unique constraint (store_id, counter_number)
        at the application layer before hitting the DB constraint.

        Args:
            exclude_id: When updating, exclude the current counter's ID.

        Returns:
            True if the number is already in use.
        """
        query = select(Counter.id).where(
            Counter.store_id == store_id,
            Counter.counter_number == counter_number,
            Counter.is_deleted == False,  # noqa: E712
        )
        if exclude_id is not None:
            query = query.where(Counter.id != exclude_id)

        result = await db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def update(
        self,
        db: AsyncSession,
        counter: Counter,
        updates: dict,
    ) -> Counter:
        """
        Apply partial updates to a Counter instance.

        Args:
            counter: The existing Counter ORM instance.
            updates: Dict of field names → new values (None values skipped).

        Returns:
            Updated Counter instance.
        """
        for field, value in updates.items():
            if value is not None or field == "cashier_id":
                # cashier_id can be explicitly set to None (unassign cashier)
                setattr(counter, field, value)
        await db.flush()
        await db.refresh(counter)
        return counter

    async def soft_delete(
        self,
        db: AsyncSession,
        counter: Counter,
    ) -> Counter:
        """
        Soft-delete a counter (marks is_deleted=True).

        The counter record remains in the database for historical analytics.
        The counter is also set to CLOSED status on deletion.

        Returns:
            Updated Counter instance with is_deleted=True.
        """
        counter.is_deleted = True
        counter.status = CounterStatus.CLOSED
        counter.cashier_id = None
        await db.flush()
        return counter

    async def get_open_counters_count(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
    ) -> int:
        """
        Count open (active, non-deleted) counters in a store.

        Used by the queue engine to calculate queue distribution.
        """
        from sqlalchemy import func
        result = await db.execute(
            select(func.count(Counter.id)).where(
                Counter.store_id == store_id,
                Counter.status == CounterStatus.OPEN,
                Counter.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one()
