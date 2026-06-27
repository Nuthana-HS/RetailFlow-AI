"""
RetailFlow AI — Queue Updater

HTTP client that pushes queue counts from the CV service
to the RetailFlow AI Queue Engine API.

Why HTTP (not direct Redis/DB write)?
    1. Single source of truth: all queue updates go through the same
       Queue Engine endpoint which handles Redis write + pub/sub + DB snapshot.
    2. RBAC: the CV service authenticates with its own service account JWT.
    3. Decoupling: the CV service doesn't need DB/Redis credentials.
    4. Observability: HTTP calls are logged, traced, and rate-limited.

Retry Strategy:
    Uses exponential backoff (1s, 2s, 4s) for transient failures.
    After max_retries failures, the update is dropped and logged.
    The next scheduled update will succeed if the API recovers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from cv_service.config import cv_config

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 1.0


class QueueUpdater:
    """
    Async HTTP client for pushing queue counts to the RetailFlow API.

    Uses a persistent httpx.AsyncClient session for connection reuse
    (avoids TCP handshake overhead on every update — important at 5s intervals).
    """

    def __init__(
        self,
        api_base_url: str | None = None,
        api_token: str | None = None,
    ) -> None:
        self._base_url = (api_base_url or cv_config.api_base_url).rstrip("/")
        self._token = api_token or cv_config.api_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create and return the shared HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                    "X-CV-Service": "retailflow-cv-v1",
                },
                timeout=httpx.Timeout(5.0, connect=2.0),
            )
        return self._client

    async def update_queue(
        self,
        store_id: str,
        counter_id: str,
        queue_length: int,
    ) -> bool:
        """
        POST a queue length update to the Queue Engine API.

        Args:
            store_id: UUID string of the store.
            counter_id: UUID string of the counter.
            queue_length: Detected number of people in queue.

        Returns:
            True if update was accepted (HTTP 200), False on failure.
        """
        endpoint = f"/api/v1/queues/stores/{store_id}/counters/{counter_id}/update"
        payload = {"queue_length": queue_length, "source": "cv"}

        for attempt in range(_MAX_RETRIES):
            try:
                client = await self._get_client()
                response = await client.post(endpoint, json=payload)

                if response.status_code == 200:
                    logger.debug(
                        "Queue update sent",
                        extra={
                            "counter_id": counter_id,
                            "queue_length": queue_length,
                            "attempt": attempt + 1,
                        },
                    )
                    return True

                elif response.status_code == 409:
                    # Counter is closed — log and skip (not a retry-able error)
                    logger.info(
                        "Counter is closed — skipping CV update",
                        extra={"counter_id": counter_id},
                    )
                    return False

                else:
                    logger.warning(
                        "Queue update failed",
                        extra={
                            "status": response.status_code,
                            "counter_id": counter_id,
                            "attempt": attempt + 1,
                        },
                    )

            except httpx.TimeoutException:
                logger.warning(
                    "Queue update timed out",
                    extra={"counter_id": counter_id, "attempt": attempt + 1},
                )
            except httpx.RequestError as exc:
                logger.error(
                    "Queue update network error",
                    extra={"error": str(exc), "counter_id": counter_id},
                )

            # Exponential backoff before retry
            if attempt < _MAX_RETRIES - 1:
                backoff = _BASE_BACKOFF_SECONDS * (2 ** attempt)
                await asyncio.sleep(backoff)

        logger.error(
            "Queue update dropped after max retries",
            extra={"counter_id": counter_id, "queue_length": queue_length},
        )
        return False

    async def close(self) -> None:
        """Close the HTTP client session (call on service shutdown)."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("QueueUpdater HTTP client closed")

    async def __aenter__(self) -> "QueueUpdater":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
