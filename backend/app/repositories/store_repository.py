"""
RetailFlow AI — Store Repository

Data access layer for Store and StoreManager operations.
Follows the same patterns established in UserRepository (Phase 3).
"""

import uuid
from datetime import time
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store import Counter, CounterStatus, Store, StoreManager
from app.models.user import User


class StoreRepository:
    """
    Data access layer for Store and StoreManager operations.

    All methods are stateless and receive the db session as argument.
    """

    # -------------------------------------------------------------------------
    # Store CRUD
    # -------------------------------------------------------------------------

    async def create(
        self,
        db: AsyncSession,
        *,
        name: str,
        address: str,
        city: str,
        state: str,
        zip_code: str | None,
        phone: str | None,
        open_time: time,
        close_time: time,
        avg_service_time: int,
        admin_id: uuid.UUID,
    ) -> Store:
        """Create a new store record."""
        store = Store(
            name=name,
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            phone=phone,
            open_time=open_time,
            close_time=close_time,
            avg_service_time=avg_service_time,
            admin_id=admin_id,
        )
        db.add(store)
        await db.flush()
        await db.refresh(store)
        return store

    async def get_by_id(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
    ) -> Store | None:
        """Fetch a store by its UUID."""
        result = await db.execute(
            select(Store).where(Store.id == store_id)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        db: AsyncSession,
        store: Store,
        updates: dict,
    ) -> Store:
        """
        Apply partial updates to a Store instance.

        Args:
            store: The existing Store ORM instance to update.
            updates: Dictionary of field names → new values.
                     Only non-None values in updates are applied.

        Returns:
            Updated Store instance.
        """
        for field, value in updates.items():
            if value is not None:
                setattr(store, field, value)
        await db.flush()
        await db.refresh(store)
        return store

    async def list_all(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        city: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[Sequence[Store], int]:
        """
        List all stores with optional filters and pagination.

        Returns:
            Tuple of (stores list, total count).
        """
        query = select(Store)

        if city is not None:
            query = query.where(Store.city == city)
        if is_active is not None:
            query = query.where(Store.is_active == is_active)

        # Count total
        count_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # Fetch page
        result = await db.execute(
            query.offset(skip).limit(limit).order_by(Store.created_at.desc())
        )
        return result.scalars().all(), total

    async def list_for_manager(
        self,
        db: AsyncSession,
        manager_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Store], int]:
        """
        List all stores assigned to a specific manager.

        Used for RBAC: managers can only see their own stores.

        Returns:
            Tuple of (stores list, total count).
        """
        query = (
            select(Store)
            .join(StoreManager, StoreManager.store_id == Store.id)
            .where(StoreManager.user_id == manager_id, Store.is_active == True)  # noqa: E712
        )

        count_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        result = await db.execute(
            query.offset(skip).limit(limit).order_by(Store.name)
        )
        return result.scalars().all(), total

    async def is_manager_of_store(
        self,
        db: AsyncSession,
        manager_id: uuid.UUID,
        store_id: uuid.UUID,
    ) -> bool:
        """
        Check if a user is an assigned manager of a specific store.

        Used in RBAC checks: before any manager operation, verify assignment.

        Returns:
            True if the user is assigned to this store.
        """
        result = await db.execute(
            select(StoreManager.user_id).where(
                StoreManager.store_id == store_id,
                StoreManager.user_id == manager_id,
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    # -------------------------------------------------------------------------
    # Manager Assignment
    # -------------------------------------------------------------------------

    async def assign_manager(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        manager_id: uuid.UUID,
    ) -> StoreManager:
        """
        Assign a manager to a store.

        Args:
            store_id: UUID of the store.
            manager_id: UUID of the manager user.

        Returns:
            The new StoreManager association record.
        """
        association = StoreManager(
            store_id=store_id,
            user_id=manager_id,
        )
        db.add(association)
        await db.flush()
        return association

    async def remove_manager(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        manager_id: uuid.UUID,
    ) -> bool:
        """
        Remove a manager from a store.

        Returns:
            True if the association existed and was removed, False otherwise.
        """
        result = await db.execute(
            select(StoreManager).where(
                StoreManager.store_id == store_id,
                StoreManager.user_id == manager_id,
            )
        )
        association = result.scalar_one_or_none()
        if association is None:
            return False
        await db.delete(association)
        await db.flush()
        return True

    async def get_store_managers(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
    ) -> Sequence[User]:
        """
        Get all managers assigned to a store.

        Returns:
            Sequence of User instances with role=manager.
        """
        result = await db.execute(
            select(User)
            .join(StoreManager, StoreManager.user_id == User.id)
            .where(StoreManager.store_id == store_id)
            .order_by(User.full_name)
        )
        return result.scalars().all()

    async def get_counter_stats(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
    ) -> tuple[int, int]:
        """
        Get total and open counter counts for a store.

        Returns:
            Tuple of (total_active_counters, open_counters).
        """
        total_result = await db.execute(
            select(func.count(Counter.id)).where(
                Counter.store_id == store_id,
                Counter.is_deleted == False,  # noqa: E712
            )
        )
        total = total_result.scalar_one()

        open_result = await db.execute(
            select(func.count(Counter.id)).where(
                Counter.store_id == store_id,
                Counter.is_deleted == False,  # noqa: E712
                Counter.status == CounterStatus.OPEN,
            )
        )
        open_count = open_result.scalar_one()

        return total, open_count
