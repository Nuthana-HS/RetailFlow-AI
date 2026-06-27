"""
RetailFlow AI — Redis Queue State Manager

This module is the performance-critical heart of the Queue Engine.

Architecture:
    Database (PostgreSQL) → QueueSnapshot rows (durable, time-series)
    Redis (Hash)          → Current queue state per counter (sub-ms reads)
    Redis (Pub/Sub)       → Real-time event broadcasting to WebSocket clients

Why Redis for queue state?
    The manager dashboard and customer displays poll or subscribe to queue state.
    Reading from PostgreSQL for every poll would be 5-20ms per query.
    Reading from Redis takes ~0.1ms — 50-200x faster.
    Redis also supports atomic counter increments (HINCRBY) for thread safety.

Key Design: Hash per Counter
    Key:   queue:counter:{counter_id}
    Fields:
        queue_length        → int (customers waiting)
        estimated_wait_sec  → int (EWT in seconds, -1 if unknown)
        counter_number      → int (display number)
        label               → str (friendly name, or empty)
        status              → str (open | closed | break)
        source              → str (cv | manual | simulation | ml)
        last_updated        → str (ISO 8601 UTC timestamp)

Store Summary (rebuilt on every counter update):
    Key:   queue:store:{store_id}:summary
    Fields:
        total_customers     → int
        open_counters       → int
        avg_wait_sec        → int
        last_updated        → str
"""

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from redis.asyncio import Redis

from app.core.redis import RedisKeys
from app.models.store import CounterStatus

logger = structlog.get_logger(__name__)

# Redis TTL for counter state (24 hours)
# If a counter is not updated for 24h, the key expires automatically
_COUNTER_STATE_TTL = 86_400

# Redis TTL for store summary (1 minute — rebuilt on every update)
_STORE_SUMMARY_TTL = 60


def _format_wait_time(seconds: int | None) -> str:
    """
    Convert seconds to a human-readable EWT string.

    Examples:
        None → "N/A"
        0    → "< 1 min"
        45   → "< 1 min"
        90   → "~2 min"
        3600 → "~60 min"
    """
    if seconds is None or seconds < 0:
        return "N/A"
    if seconds < 60:
        return "< 1 min"
    minutes = round(seconds / 60)
    return f"~{minutes} min"


def _calculate_ewt(queue_length: int, avg_service_time: int = 180) -> int:
    """
    Fallback EWT calculation when ML model is not available.

    Simple formula: EWT = queue_length × avg_service_time_per_customer

    The ML XGBoost model (Phase 9) will override this with a more accurate
    prediction that considers time-of-day, day-of-week, and historical data.

    Args:
        queue_length: Number of customers currently waiting.
        avg_service_time: Seconds per customer (from Store.avg_service_time).

    Returns:
        Estimated wait time in seconds.
    """
    return queue_length * avg_service_time


class QueueStateManager:
    """
    Manages real-time queue state in Redis.

    This is the ONLY class that writes to Redis queue keys.
    All other components (service, router, WebSocket) read through this class.

    Thread Safety:
        Redis HSET is atomic. Concurrent updates from multiple sources
        (CV, manual, ML) will not corrupt the state — last write wins.
    """

    async def initialize_counter(
        self,
        redis: Redis,
        *,
        counter_id: str,
        counter_number: int,
        label: str | None,
        store_id: str,
        status: str,
    ) -> None:
        """
        Initialize Redis state for a new counter.

        Called when a counter is created or the server restarts.
        Sets all fields to their default values.
        """
        key = RedisKeys.queue_counter(counter_id)
        await redis.hset(
            key,
            mapping={
                "queue_length": 0,
                "estimated_wait_sec": -1,
                "counter_number": counter_number,
                "label": label or "",
                "store_id": store_id,
                "status": status,
                "source": "manual",
                "last_updated": datetime.now(tz=timezone.utc).isoformat(),
            },
        )
        await redis.expire(key, _COUNTER_STATE_TTL)
        logger.debug("Counter state initialized", counter_id=counter_id)

    async def update_counter_state(
        self,
        redis: Redis,
        *,
        counter_id: str,
        store_id: str,
        queue_length: int,
        source: str,
        avg_service_time: int = 180,
        ml_wait_seconds: int | None = None,
    ) -> dict[str, Any]:
        """
        Update the queue state for a single counter.

        Flow:
            1. Compute EWT (ML if available, otherwise formula)
            2. HSET all fields atomically
            3. Refresh TTL
            4. Return the new state as a dict

        Args:
            counter_id: UUID string of the counter.
            store_id: UUID string of the store (for pub/sub).
            queue_length: New queue length.
            source: Update source (cv/manual/simulation/ml).
            avg_service_time: Fallback EWT calculation base (seconds/customer).
            ml_wait_seconds: ML-predicted wait time (overrides formula if provided).

        Returns:
            Dict with all current counter state fields.
        """
        # Compute EWT
        if ml_wait_seconds is not None:
            estimated_wait_sec = ml_wait_seconds
        else:
            estimated_wait_sec = _calculate_ewt(queue_length, avg_service_time)

        now_iso = datetime.now(tz=timezone.utc).isoformat()

        key = RedisKeys.queue_counter(counter_id)

        # Atomic HSET update
        updates = {
            "queue_length": queue_length,
            "estimated_wait_sec": estimated_wait_sec,
            "source": source,
            "last_updated": now_iso,
        }
        await redis.hset(key, mapping=updates)
        await redis.expire(key, _COUNTER_STATE_TTL)

        # Read the full state (to include static fields like counter_number)
        full_state = await redis.hgetall(key)
        logger.debug(
            "Counter state updated",
            counter_id=counter_id,
            queue_length=queue_length,
            source=source,
        )
        return dict(full_state)

    async def update_counter_status(
        self,
        redis: Redis,
        *,
        counter_id: str,
        status: str,
    ) -> None:
        """
        Update only the status field of a counter in Redis.

        Called when manager opens/closes/breaks a counter.
        Does not change queue_length.
        """
        key = RedisKeys.queue_counter(counter_id)
        await redis.hset(
            key,
            mapping={
                "status": status,
                "last_updated": datetime.now(tz=timezone.utc).isoformat(),
            },
        )
        if status in (CounterStatus.CLOSED.value, CounterStatus.BREAK.value):
            # Clear queue when counter closes
            await redis.hset(key, mapping={"queue_length": 0, "estimated_wait_sec": -1})
        await redis.expire(key, _COUNTER_STATE_TTL)

    async def get_counter_state(
        self,
        redis: Redis,
        counter_id: str,
    ) -> dict[str, Any] | None:
        """
        Get the current state for a single counter from Redis.

        Returns:
            Dict with counter state fields, or None if counter not in Redis.
        """
        key = RedisKeys.queue_counter(counter_id)
        state = await redis.hgetall(key)
        if not state:
            return None
        return dict(state)

    async def get_store_state(
        self,
        redis: Redis,
        counter_ids: list[str],
    ) -> list[dict[str, Any]]:
        """
        Get the state for all counters in a store using a Redis pipeline.

        Uses PIPELINE to batch all counter reads into a single round-trip.
        This is critical for stores with many counters — 1 round-trip instead of N.

        Args:
            counter_ids: List of counter UUID strings.

        Returns:
            List of counter state dicts (None entries for uninitialized counters).
        """
        if not counter_ids:
            return []

        # Use pipeline for batch reads
        async with redis.pipeline(transaction=False) as pipe:
            for cid in counter_ids:
                pipe.hgetall(RedisKeys.queue_counter(cid))
            results = await pipe.execute()

        return [dict(r) if r else {} for r in results]

    async def publish_queue_event(
        self,
        redis: Redis,
        *,
        store_id: str,
        counter_id: str,
        queue_length: int,
        estimated_wait_seconds: int | None,
        counter_number: int,
        status: str,
        source: str,
    ) -> None:
        """
        Publish a queue update event to the Redis Pub/Sub channel.

        Phase 7 (WebSocket) subscribes to this channel and forwards
        events to connected browser clients in real-time.

        Channel: queue:events:store:{store_id}
        """
        from app.schemas.queue import QueueUpdateEvent

        event = QueueUpdateEvent(
            event_type="queue_update",
            store_id=store_id,
            counter_id=counter_id,
            queue_length=queue_length,
            estimated_wait_seconds=estimated_wait_seconds,
            counter_number=counter_number,
            status=status,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            source=source,
        )

        channel = RedisKeys.queue_events_channel(store_id)
        await redis.publish(channel, event.model_dump_json())

        logger.debug(
            "Queue event published",
            store_id=store_id,
            counter_id=counter_id,
            queue_length=queue_length,
        )


# Module-level singleton
queue_state_manager = QueueStateManager()
