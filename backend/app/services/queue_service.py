"""
RetailFlow AI — Queue Service

Business logic for the queue engine.

Data Flow per Update:
    Manager POSTs update
        → QueueService.update_counter_queue()
            → RBAC check (store_repo.is_manager_of_store)
            → Redis update (queue_state_manager.update_counter_state)
            → Redis pub/sub broadcast (queue_state_manager.publish_queue_event)
            → DB snapshot insert (queue_repo.insert_snapshot)  ← async, non-blocking
            → Alert check (alert_repo.get_active_for_store)
        → Response with CounterQueueState

Data Flow per Dashboard Read:
    Dashboard polls /api/v1/queues/stores/{store_id}
        → QueueService.get_store_queue_state()
            → RBAC check
            → Get all open counters (counter_repo.get_by_store)
            → PIPELINE read from Redis (queue_state_manager.get_store_state)
            → Assemble StoreQueueState
        → Response with StoreQueueState

Performance Target:
    Dashboard read: < 5ms end-to-end (Redis pipeline + minimal CPU)
    Queue update: < 30ms end-to-end (Redis write + Postgres insert)
"""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.queue_state import _format_wait_time, queue_state_manager
from app.models.queue import AlertType, QueueUpdateSource
from app.models.store import CounterStatus
from app.models.user import User, UserRole
from app.repositories.alert_repository import AlertRepository
from app.repositories.counter_repository import CounterRepository
from app.repositories.queue_repository import QueueRepository
from app.repositories.store_repository import StoreRepository
from app.schemas.queue import (
    AlertConfigRequest,
    AlertConfigResponse,
    CounterQueueState,
    QueueHistoryResponse,
    QueueSnapshotResponse,
    QueueUpdateRequest,
    StoreQueueState,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Domain Exceptions
# =============================================================================

class QueueCounterNotFoundError(Exception):
    """Counter does not exist or is soft-deleted."""
    pass


class QueueCounterClosedError(Exception):
    """Cannot update queue for a closed/on-break counter."""
    pass


class QueueAccessDeniedError(Exception):
    """User does not have access to this store."""
    pass


class QueueStoreNotFoundError(Exception):
    """Store not found."""
    pass


class AlertConfigNotFoundError(Exception):
    """Alert config not found."""
    pass


# =============================================================================
# Queue Service
# =============================================================================

class QueueService:
    """Orchestrates all queue engine operations."""

    def __init__(
        self,
        store_repo: StoreRepository,
        counter_repo: CounterRepository,
        queue_repo: QueueRepository,
        alert_repo: AlertRepository,
    ) -> None:
        self._store_repo = store_repo
        self._counter_repo = counter_repo
        self._queue_repo = queue_repo
        self._alert_repo = alert_repo

    # -------------------------------------------------------------------------
    # Queue State — Real-time Reads (from Redis)
    # -------------------------------------------------------------------------

    async def get_store_queue_state(
        self,
        db: AsyncSession,
        redis: Redis,
        store_id: uuid.UUID,
        requesting_user: User,
    ) -> StoreQueueState:
        """
        Get the real-time queue state for all counters in a store.

        Uses Redis pipeline for batch read (one round-trip regardless of counter count).

        Raises:
            QueueStoreNotFoundError, QueueAccessDeniedError.
        """
        # RBAC check
        store = await self._store_repo.get_by_id(db, store_id)
        if store is None:
            raise QueueStoreNotFoundError(f"Store {store_id} not found")

        if requesting_user.role == UserRole.MANAGER:
            is_assigned = await self._store_repo.is_manager_of_store(
                db, requesting_user.id, store_id
            )
            if not is_assigned:
                raise QueueAccessDeniedError("You are not assigned to this store")

        # Get all non-deleted counters
        counters = await self._counter_repo.get_by_store(db, store_id)
        counter_ids = [str(c.id) for c in counters]

        # Batch Redis read via pipeline
        redis_states = await queue_state_manager.get_store_state(redis, counter_ids)

        # Assemble CounterQueueState objects
        counter_states: list[CounterQueueState] = []
        total_customers = 0
        open_count = 0
        wait_times: list[int] = []

        for counter, redis_state in zip(counters, redis_states):
            if counter.status == CounterStatus.CLOSED:
                queue_len = 0
                ewt = None
            elif redis_state:
                queue_len = int(redis_state.get("queue_length", 0))
                ewt_raw = int(redis_state.get("estimated_wait_sec", -1))
                ewt = ewt_raw if ewt_raw >= 0 else None
            else:
                # Counter not in Redis yet (first load) — derive from DB defaults
                queue_len = 0
                ewt = None

            last_updated_str = redis_state.get("last_updated") if redis_state else None
            last_updated = (
                datetime.fromisoformat(last_updated_str)
                if last_updated_str
                else None
            )

            if counter.status == CounterStatus.OPEN:
                open_count += 1
                total_customers += queue_len
                if ewt is not None:
                    wait_times.append(ewt)

            source_str = redis_state.get("source", "manual") if redis_state else "manual"

            counter_states.append(
                CounterQueueState(
                    counter_id=counter.id,
                    counter_number=counter.counter_number,
                    label=counter.label,
                    status=counter.status,
                    queue_length=queue_len,
                    estimated_wait_seconds=ewt,
                    estimated_wait_formatted=_format_wait_time(ewt),
                    last_updated=last_updated,
                    source=source_str,
                )
            )

        avg_wait = int(sum(wait_times) / len(wait_times)) if wait_times else None

        return StoreQueueState(
            store_id=store_id,
            store_name=store.name,
            total_customers_waiting=total_customers,
            open_counters=open_count,
            avg_wait_seconds=avg_wait,
            avg_wait_formatted=_format_wait_time(avg_wait),
            alert_active=False,  # Alert check happens on updates, not reads
            counters=counter_states,
            last_updated=datetime.now(tz=timezone.utc),
        )

    # -------------------------------------------------------------------------
    # Queue Update — Manual Override
    # -------------------------------------------------------------------------

    async def update_counter_queue(
        self,
        db: AsyncSession,
        redis: Redis,
        counter_id: uuid.UUID,
        data: QueueUpdateRequest,
        requesting_user: User,
    ) -> CounterQueueState:
        """
        Manually update the queue length for a single counter.

        Flow:
          1. Validate counter exists and is open
          2. RBAC check
          3. Update Redis (primary write — sub-ms)
          4. Publish Pub/Sub event (for WebSocket clients)
          5. Insert DB snapshot (durable record)
          6. Check alert thresholds

        Returns:
            Updated CounterQueueState.

        Raises:
            QueueCounterNotFoundError, QueueCounterClosedError, QueueAccessDeniedError.
        """
        log = logger.bind(counter_id=str(counter_id), user_id=str(requesting_user.id))

        # Validate counter
        counter = await self._counter_repo.get_by_id(db, counter_id)
        if counter is None:
            raise QueueCounterNotFoundError(f"Counter {counter_id} not found")

        # RBAC check via store
        store = await self._store_repo.get_by_id(db, counter.store_id)
        if store is None:
            raise QueueStoreNotFoundError("Store not found")

        if requesting_user.role == UserRole.MANAGER:
            is_assigned = await self._store_repo.is_manager_of_store(
                db, requesting_user.id, counter.store_id
            )
            if not is_assigned:
                raise QueueAccessDeniedError(
                    "You are not assigned to this store"
                )

        # Validate counter is open (can't update a closed counter)
        if counter.status == CounterStatus.CLOSED:
            raise QueueCounterClosedError(
                f"Counter #{counter.counter_number} is closed. "
                "Open the counter before updating its queue."
            )

        # Compute EWT using store's average service time
        source = QueueUpdateSource(data.source)

        # --- Redis write (primary) ---
        new_state = await queue_state_manager.update_counter_state(
            redis,
            counter_id=str(counter_id),
            store_id=str(counter.store_id),
            queue_length=data.queue_length,
            source=data.source,
            avg_service_time=store.avg_service_time,
        )

        ewt = int(new_state.get("estimated_wait_sec", -1))
        ewt_value = ewt if ewt >= 0 else None

        # --- Pub/Sub broadcast (non-blocking) ---
        await queue_state_manager.publish_queue_event(
            redis,
            store_id=str(counter.store_id),
            counter_id=str(counter_id),
            queue_length=data.queue_length,
            estimated_wait_seconds=ewt_value,
            counter_number=counter.counter_number,
            status=counter.status.value,
            source=data.source,
        )

        # --- DB snapshot insert (durable record) ---
        await self._queue_repo.insert_snapshot(
            db,
            counter_id=counter_id,
            store_id=counter.store_id,
            queue_length=data.queue_length,
            estimated_wait_seconds=ewt_value,
            source=source,
        )

        # --- Alert check ---
        await self._check_alerts(db, counter.store_id, counter_id, data.queue_length, ewt_value)

        log.info(
            "Queue updated",
            queue_length=data.queue_length,
            source=data.source,
        )

        return CounterQueueState(
            counter_id=counter_id,
            counter_number=counter.counter_number,
            label=counter.label,
            status=counter.status,
            queue_length=data.queue_length,
            estimated_wait_seconds=ewt_value,
            estimated_wait_formatted=_format_wait_time(ewt_value),
            last_updated=datetime.now(tz=timezone.utc),
            source=data.source,
        )

    # -------------------------------------------------------------------------
    # Queue History (Analytics)
    # -------------------------------------------------------------------------

    async def get_queue_history(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        requesting_user: User,
        hours: int = 24,
        page: int = 1,
        limit: int = 100,
    ) -> QueueHistoryResponse:
        """
        Fetch historical queue snapshots for a store.

        Args:
            hours: Look back N hours from now.
            page, limit: Pagination.

        Raises:
            QueueStoreNotFoundError, QueueAccessDeniedError.
        """
        store = await self._store_repo.get_by_id(db, store_id)
        if store is None:
            raise QueueStoreNotFoundError(f"Store {store_id} not found")

        if requesting_user.role == UserRole.MANAGER:
            is_assigned = await self._store_repo.is_manager_of_store(
                db, requesting_user.id, store_id
            )
            if not is_assigned:
                raise QueueAccessDeniedError("Access denied to this store")

        now = datetime.now(tz=timezone.utc)
        from_dt = now - timedelta(hours=hours)

        snapshots, total = await self._queue_repo.get_history_for_store(
            db, store_id, from_dt=from_dt, to_dt=now,
            skip=(page - 1) * limit, limit=limit,
        )

        return QueueHistoryResponse(
            snapshots=[QueueSnapshotResponse.model_validate(s) for s in snapshots],
            total=total,
            page=page,
            limit=limit,
        )

    # -------------------------------------------------------------------------
    # Alert Configuration
    # -------------------------------------------------------------------------

    async def configure_alert(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        data: AlertConfigRequest,
        requesting_user: User,
    ) -> AlertConfigResponse:
        """
        Create a new alert configuration for a store.

        Raises:
            QueueStoreNotFoundError, QueueAccessDeniedError.
        """
        store = await self._store_repo.get_by_id(db, store_id)
        if store is None:
            raise QueueStoreNotFoundError(f"Store {store_id} not found")

        if requesting_user.role == UserRole.MANAGER:
            is_assigned = await self._store_repo.is_manager_of_store(
                db, requesting_user.id, store_id
            )
            if not is_assigned:
                raise QueueAccessDeniedError("Access denied to this store")

        config = await self._alert_repo.create(
            db,
            store_id=store_id,
            counter_id=data.counter_id,
            alert_type=data.alert_type,
            threshold=data.threshold,
            cooldown_minutes=data.cooldown_minutes,
        )

        logger.info(
            "Alert config created",
            store_id=str(store_id),
            threshold=data.threshold,
        )
        return AlertConfigResponse.model_validate(config)

    async def list_alerts(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        requesting_user: User,
    ) -> list[AlertConfigResponse]:
        """List all alert configs for a store."""
        store = await self._store_repo.get_by_id(db, store_id)
        if store is None:
            raise QueueStoreNotFoundError(f"Store {store_id} not found")

        configs = await self._alert_repo.list_for_store(db, store_id)
        return [AlertConfigResponse.model_validate(c) for c in configs]

    # -------------------------------------------------------------------------
    # Internal: Alert Threshold Check
    # -------------------------------------------------------------------------

    async def _check_alerts(
        self,
        db: AsyncSession,
        store_id: uuid.UUID,
        counter_id: uuid.UUID,
        queue_length: int,
        wait_seconds: int | None,
    ) -> None:
        """
        Check all active alert configs after a queue update.

        This runs AFTER the update is written to Redis and the DB.
        Alert delivery (email/push) is implemented in Phase 10.
        For now, we just log when thresholds are exceeded.

        Matching logic:
            - Store-level configs (counter_id IS NULL) match any counter
            - Counter-specific configs only match their counter
        """
        configs = await self._alert_repo.get_active_for_store(db, store_id)

        for config in configs:
            # Scope check: skip counter-specific configs that don't match
            if config.counter_id is not None and config.counter_id != counter_id:
                continue

            # Cooldown check
            if await self._alert_repo.is_in_cooldown(config):
                continue

            # Threshold check
            triggered = False
            if config.alert_type == AlertType.QUEUE_LENGTH:
                triggered = queue_length >= config.threshold
            elif config.alert_type == AlertType.WAIT_TIME and wait_seconds is not None:
                triggered = wait_seconds >= config.threshold

            if triggered:
                await self._alert_repo.record_trigger(db, config.id)
                logger.warning(
                    "ALERT TRIGGERED",
                    store_id=str(store_id),
                    counter_id=str(counter_id),
                    alert_type=config.alert_type,
                    threshold=config.threshold,
                    current_value=queue_length
                    if config.alert_type == AlertType.QUEUE_LENGTH
                    else wait_seconds,
                )

                # Phase 10: Deliver in-app + email notifications
                from app.services.notification_service import notification_service
                from app.repositories.counter_repository import CounterRepository

                counter = await CounterRepository().get_by_id(db, counter_id)
                counter_number = counter.counter_number if counter else None
                trigger_val = (
                    queue_length if config.alert_type == AlertType.QUEUE_LENGTH
                    else (wait_seconds or 0)
                )

                await notification_service.handle_triggered_alert(
                    db=db,
                    config=config,
                    store_id=store_id,
                    counter_id=counter_id,
                    counter_number=counter_number,
                    trigger_value=trigger_val,
                )


# =============================================================================
# Dependency Factory
# =============================================================================

def get_queue_service() -> QueueService:
    """
    Factory function for creating QueueService with injected repositories.

    Usage:
        queue_service: QueueService = Depends(get_queue_service)
    """
    return QueueService(
        store_repo=StoreRepository(),
        counter_repo=CounterRepository(),
        queue_repo=QueueRepository(),
        alert_repo=AlertRepository(),
    )
