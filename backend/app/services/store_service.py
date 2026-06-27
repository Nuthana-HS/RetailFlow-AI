"""
RetailFlow AI — Store Service

Business logic layer for store and counter management.

Clean Architecture Rules (same as AuthService):
  - StoreService never imports from app.api (no upward dependency)
  - StoreService raises domain exceptions, not HTTP exceptions
  - All database access goes through repositories

RBAC Enforcement:
  - Admin can CRUD any store
  - Manager can only READ/UPDATE stores they are assigned to
  - RBAC checks happen in the service layer (not just the router)
    so they are testable without HTTP

Domain Exceptions:
  - StoreNotFoundError     → HTTP 404
  - CounterNotFoundError   → HTTP 404
  - DuplicateCounterError  → HTTP 409
  - ManagerNotFoundError   → HTTP 404
  - ManagerAlreadyAssigned → HTTP 409
  - AccessDeniedError      → HTTP 403
"""

import math
import uuid
from datetime import time

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store import Counter, CounterStatus, Store
from app.models.user import User, UserRole
from app.repositories.counter_repository import CounterRepository
from app.repositories.store_repository import StoreRepository
from app.repositories.user_repository import UserRepository
from app.schemas.store import (
    CounterCreateRequest,
    CounterUpdateRequest,
    StoreCreateRequest,
    StoreUpdateRequest,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Domain Exceptions
# =============================================================================

class StoreNotFoundError(Exception):
    """Raised when a store ID does not match any record."""
    pass


class CounterNotFoundError(Exception):
    """Raised when a counter ID does not match any active counter."""
    pass


class DuplicateCounterError(Exception):
    """Raised when counter_number already exists in the store."""
    pass


class ManagerNotFoundError(Exception):
    """Raised when the specified user doesn't exist or isn't a manager."""
    pass


class ManagerAlreadyAssignedError(Exception):
    """Raised when trying to assign a manager already assigned to the store."""
    pass


class AccessDeniedError(Exception):
    """Raised when a manager tries to access a store they are not assigned to."""
    pass


# =============================================================================
# Store Service
# =============================================================================

class StoreService:
    """
    Orchestrates all store and counter business logic.

    Injected repositories:
      - store_repo: StoreRepository
      - counter_repo: CounterRepository
      - user_repo: UserRepository (for manager validation)
    """

    def __init__(
        self,
        store_repo: StoreRepository,
        counter_repo: CounterRepository,
        user_repo: UserRepository,
    ) -> None:
        self._store_repo = store_repo
        self._counter_repo = counter_repo
        self._user_repo = user_repo

    # -------------------------------------------------------------------------
    # Store CRUD
    # -------------------------------------------------------------------------

    async def create_store(
        self,
        db: AsyncSession,
        data: StoreCreateRequest,
        admin_user: User,
    ) -> Store:
        """
        Create a new store, owned by the admin creating it.

        Args:
            data: Validated store creation request.
            admin_user: The admin user performing the action.

        Returns:
            Newly created Store instance.
        """
        log = logger.bind(admin_id=str(admin_user.id), store_name=data.name)
        log.info("Creating store")

        store = await self._store_repo.create(
            db,
            name=data.name,
            address=data.address,
            city=data.city,
            state=data.state,
            zip_code=data.zip_code,
            phone=data.phone,
            open_time=_parse_time(data.open_time),
            close_time=_parse_time(data.close_time),
            avg_service_time=data.avg_service_time,
            admin_id=admin_user.id,
        )

        log.info("Store created", store_id=str(store.id))
        return store

    async def get_store(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        requesting_user: User,
    ) -> Store:
        """
        Retrieve a store by ID, with RBAC enforcement.

        - Admins can access any store.
        - Managers can only access their assigned stores.

        Returns:
            Store instance.

        Raises:
            StoreNotFoundError: Store does not exist.
            AccessDeniedError: Manager not assigned to this store.
        """
        store = await self._store_repo.get_by_id(db, store_id)
        if store is None:
            raise StoreNotFoundError(f"Store {store_id} not found")

        if requesting_user.role == UserRole.MANAGER:
            is_assigned = await self._store_repo.is_manager_of_store(
                db, requesting_user.id, store_id
            )
            if not is_assigned:
                raise AccessDeniedError(
                    "You are not assigned to this store. "
                    "Contact your administrator to request access."
                )

        return store

    async def list_stores(
        self,
        db: AsyncSession,
        requesting_user: User,
        page: int = 1,
        limit: int = 20,
        city: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Store], int, int]:
        """
        List stores with pagination, filtered by the requesting user's role.

        - Admins see all stores.
        - Managers only see their assigned stores.

        Returns:
            Tuple of (stores, total_count, total_pages).
        """
        skip = (page - 1) * limit

        if requesting_user.role == UserRole.ADMIN:
            stores, total = await self._store_repo.list_all(
                db, skip=skip, limit=limit, city=city, is_active=is_active
            )
        else:
            stores, total = await self._store_repo.list_for_manager(
                db, requesting_user.id, skip=skip, limit=limit
            )

        total_pages = math.ceil(total / limit) if total > 0 else 1
        return list(stores), total, total_pages

    async def update_store(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        data: StoreUpdateRequest,
        requesting_user: User,
    ) -> Store:
        """
        Partially update a store's details.

        - Admins can update any store.
        - Managers can update only their assigned stores.

        Returns:
            Updated Store instance.

        Raises:
            StoreNotFoundError, AccessDeniedError.
        """
        # get_store handles access check
        store = await self.get_store(db, store_id, requesting_user)

        # Build the updates dict, parsing time strings to time objects
        updates: dict = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.address is not None:
            updates["address"] = data.address
        if data.city is not None:
            updates["city"] = data.city
        if data.state is not None:
            updates["state"] = data.state
        if data.zip_code is not None:
            updates["zip_code"] = data.zip_code
        if data.phone is not None:
            updates["phone"] = data.phone
        if data.open_time is not None:
            updates["open_time"] = _parse_time(data.open_time)
        if data.close_time is not None:
            updates["close_time"] = _parse_time(data.close_time)
        if data.avg_service_time is not None:
            updates["avg_service_time"] = data.avg_service_time
        if data.is_active is not None:
            updates["is_active"] = data.is_active

        updated = await self._store_repo.update(db, store, updates)
        logger.info(
            "Store updated",
            store_id=str(store_id),
            updated_by=str(requesting_user.id),
            fields=list(updates.keys()),
        )
        return updated

    # -------------------------------------------------------------------------
    # Manager Assignment
    # -------------------------------------------------------------------------

    async def assign_manager(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        manager_id: uuid.UUID,
    ) -> None:
        """
        Assign a manager to a store.

        Validates:
          - Store exists
          - Manager user exists and has role=MANAGER
          - Manager not already assigned

        Raises:
            StoreNotFoundError, ManagerNotFoundError, ManagerAlreadyAssignedError.
        """
        store = await self._store_repo.get_by_id(db, store_id)
        if store is None:
            raise StoreNotFoundError(f"Store {store_id} not found")

        manager = await self._user_repo.get_by_id(db, manager_id)
        if manager is None or manager.role != UserRole.MANAGER:
            raise ManagerNotFoundError(
                f"No active manager found with ID {manager_id}. "
                "Only users with role='manager' can be assigned to stores."
            )

        already_assigned = await self._store_repo.is_manager_of_store(
            db, manager_id, store_id
        )
        if already_assigned:
            raise ManagerAlreadyAssignedError(
                f"Manager {manager.full_name!r} is already assigned to this store."
            )

        await self._store_repo.assign_manager(db, store_id, manager_id)
        logger.info(
            "Manager assigned to store",
            store_id=str(store_id),
            manager_id=str(manager_id),
        )

    async def remove_manager(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        manager_id: uuid.UUID,
    ) -> None:
        """
        Remove a manager from a store.

        Raises:
            StoreNotFoundError, ManagerNotFoundError (not assigned).
        """
        store = await self._store_repo.get_by_id(db, store_id)
        if store is None:
            raise StoreNotFoundError(f"Store {store_id} not found")

        removed = await self._store_repo.remove_manager(db, store_id, manager_id)
        if not removed:
            raise ManagerNotFoundError(
                f"Manager {manager_id} is not assigned to this store."
            )

        logger.info(
            "Manager removed from store",
            store_id=str(store_id),
            manager_id=str(manager_id),
        )

    # -------------------------------------------------------------------------
    # Counter Management
    # -------------------------------------------------------------------------

    async def create_counter(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        data: CounterCreateRequest,
        requesting_user: User,
    ) -> Counter:
        """
        Add a new counter to a store.

        Raises:
            StoreNotFoundError, AccessDeniedError, DuplicateCounterError.
        """
        # RBAC: ensure user has access to this store
        store = await self.get_store(db, store_id, requesting_user)

        # Check counter number uniqueness within store
        if await self._counter_repo.counter_number_exists(
            db, store_id, data.counter_number
        ):
            raise DuplicateCounterError(
                f"Counter #{data.counter_number} already exists in this store. "
                "Choose a different counter number."
            )

        counter = await self._counter_repo.create(
            db,
            store_id=store_id,
            counter_number=data.counter_number,
            label=data.label,
            status=data.status,
        )

        logger.info(
            "Counter created",
            store_id=str(store_id),
            counter_id=str(counter.id),
            counter_number=data.counter_number,
        )
        return counter

    async def list_counters(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        requesting_user: User,
        status: CounterStatus | None = None,
    ) -> list[Counter]:
        """
        List all active counters for a store.

        Raises:
            StoreNotFoundError, AccessDeniedError.
        """
        await self.get_store(db, store_id, requesting_user)  # RBAC check
        counters = await self._counter_repo.get_by_store(db, store_id, status=status)
        return list(counters)

    async def update_counter(
        self,
        db: AsyncSession,
        counter_id: uuid.UUID,
        data: CounterUpdateRequest,
        requesting_user: User,
    ) -> Counter:
        """
        Update a counter's label, status, or cashier assignment.

        Raises:
            CounterNotFoundError, AccessDeniedError, DuplicateCounterError.
        """
        counter = await self._counter_repo.get_by_id(db, counter_id)
        if counter is None:
            raise CounterNotFoundError(f"Counter {counter_id} not found")

        # RBAC: check user has access to this counter's store
        await self.get_store(db, counter.store_id, requesting_user)

        updates: dict = {}
        if data.label is not None:
            updates["label"] = data.label
        if data.status is not None:
            updates["status"] = data.status
        if "cashier_id" in data.model_fields_set:
            updates["cashier_id"] = data.cashier_id  # Allow None (unassign)

        updated = await self._counter_repo.update(db, counter, updates)
        logger.info(
            "Counter updated",
            counter_id=str(counter_id),
            fields=list(updates.keys()),
        )
        return updated

    async def delete_counter(
        self,
        db: AsyncSession,
        counter_id: uuid.UUID,
        requesting_user: User,
    ) -> None:
        """
        Soft-delete a counter.

        Raises:
            CounterNotFoundError, AccessDeniedError.
        """
        counter = await self._counter_repo.get_by_id(db, counter_id)
        if counter is None:
            raise CounterNotFoundError(f"Counter {counter_id} not found")

        await self.get_store(db, counter.store_id, requesting_user)  # RBAC check
        await self._counter_repo.soft_delete(db, counter)

        logger.info(
            "Counter soft-deleted",
            counter_id=str(counter_id),
            store_id=str(counter.store_id),
        )


# =============================================================================
# Helper Utilities
# =============================================================================

def _parse_time(time_str: str) -> time:
    """Parse HH:MM string to datetime.time object."""
    h, m = map(int, time_str.split(":"))
    return time(hour=h, minute=m)


# =============================================================================
# Dependency Factory
# =============================================================================

def get_store_service() -> StoreService:
    """
    Factory function for creating StoreService with injected repositories.

    Usage:
        store_service: StoreService = Depends(get_store_service)
    """
    return StoreService(
        store_repo=StoreRepository(),
        counter_repo=CounterRepository(),
        user_repo=UserRepository(),
    )
