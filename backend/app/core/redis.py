"""
RetailFlow AI — Redis Client Factory

Provides an async Redis client configured from application settings.
Used for:
  - Queue state caching (sub-millisecond reads)
  - WebSocket event pub/sub
  - Rate limiting counters
  - ML prediction caching
"""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings


# =============================================================================
# Redis Client
# =============================================================================

redis_client: Redis = aioredis.from_url(
    settings.REDIS_URL,
    max_connections=settings.REDIS_MAX_CONNECTIONS,
    decode_responses=True,       # Return strings instead of bytes
    socket_timeout=5,            # Connection timeout (seconds)
    socket_connect_timeout=5,
    retry_on_timeout=True,
)


# =============================================================================
# Redis Key Builders
# =============================================================================

class RedisKeys:
    """
    Centralized Redis key naming conventions.

    Having all key patterns in one place prevents typos and makes it easy
    to understand what's stored in Redis at a glance.
    """

    @staticmethod
    def queue_counter(counter_id: str) -> str:
        """Hash: current queue state for a counter."""
        return f"queue:counter:{counter_id}"

    @staticmethod
    def queue_store_summary(store_id: str) -> str:
        """Hash: aggregated queue state for a store."""
        return f"queue:store:{store_id}:summary"

    @staticmethod
    def queue_events_channel(store_id: str) -> str:
        """Pub/Sub channel: real-time queue events for a store."""
        return f"queue:events:store:{store_id}"

    @staticmethod
    def ml_prediction(counter_id: str, queue_length: int) -> str:
        """Hash: cached ML prediction for a counter + queue length."""
        return f"ml:predict:{counter_id}:{queue_length}"

    @staticmethod
    def rate_limit_ip(ip_address: str) -> str:
        """String counter: rate limit tracking for an IP."""
        return f"rate_limit:ip:{ip_address}"

    @staticmethod
    def rate_limit_user(user_id: str) -> str:
        """String counter: rate limit tracking for an authenticated user."""
        return f"rate_limit:user:{user_id}"

    @staticmethod
    def analytics_daily(store_id: str, date: str) -> str:
        """Hash: cached daily analytics for a store (date: YYYY-MM-DD)."""
        return f"analytics:store:{store_id}:daily:{date}"

    @staticmethod
    def analytics_heatmap(store_id: str) -> str:
        """String (JSON): cached peak hours heatmap for a store."""
        return f"analytics:store:{store_id}:heatmap"


# =============================================================================
# Dependency: Redis Client
# =============================================================================

async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    FastAPI dependency that provides the Redis client.

    Usage in route handlers:
        @router.get("/")
        async def handler(redis: Redis = Depends(get_redis)):
            await redis.get("some-key")
    """
    try:
        yield redis_client
    finally:
        pass  # Connection is returned to pool automatically
