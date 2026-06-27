"""
RetailFlow AI — WebSocket Connection Manager

Manages the in-memory registry of active WebSocket connections.

Design:
    Connections are stored in a dict: store_id → set[WebSocket]
    This allows O(1) lookup of all connections for a given store
    when broadcasting queue update events.

Scalability Note (for interview discussions):
    This in-memory implementation works for a SINGLE FastAPI process.
    For multi-process/multi-pod deployments, connections on different
    pods cannot see each other's in-memory state.

    Production solution options:
      Option A: Sticky sessions (load balancer routes same store to same pod)
      Option B: Redis Streams fan-out (all pods subscribe to the same channel
                and each broadcasts to its own connected clients)
      This is a known, documented trade-off — not a bug.

Thread Safety:
    asyncio.Lock is used to protect dict mutations from concurrent coroutines.
    Since FastAPI uses a single-threaded asyncio event loop, the lock is
    technically not necessary, but it documents concurrent access intent
    and future-proofs against potential ASGI concurrency models.
"""

import asyncio
from typing import Set

import structlog
from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """
    Thread-safe registry of active WebSocket connections, keyed by store_id.

    Usage:
        # On connect
        await connection_manager.connect(websocket, store_id)

        # On each queue update event
        await connection_manager.broadcast_to_store(store_id, json_message)

        # On disconnect
        await connection_manager.disconnect(websocket, store_id)
    """

    def __init__(self) -> None:
        # store_id (str) → set of active WebSocket connections
        self._connections: dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, store_id: str) -> None:
        """
        Register a WebSocket connection for a store.

        Called AFTER websocket.accept() — the connection is already open.

        Args:
            websocket: The accepted WebSocket connection object.
            store_id: UUID string of the store (used as registry key).
        """
        async with self._lock:
            if store_id not in self._connections:
                self._connections[store_id] = set()
            self._connections[store_id].add(websocket)

        logger.info(
            "WebSocket connected",
            store_id=store_id,
            total_for_store=self.get_connection_count(store_id),
        )

    async def disconnect(self, websocket: WebSocket, store_id: str) -> None:
        """
        Remove a WebSocket connection from the registry.

        Called in finally block to guarantee cleanup even on errors.
        Safe to call even if the connection was never registered.
        """
        async with self._lock:
            if store_id in self._connections:
                self._connections[store_id].discard(websocket)
                # Remove the store entry entirely if no connections remain
                if not self._connections[store_id]:
                    del self._connections[store_id]

        logger.info(
            "WebSocket disconnected",
            store_id=store_id,
            remaining=self.get_connection_count(store_id),
        )

    async def broadcast_to_store(self, store_id: str, message: str) -> None:
        """
        Broadcast a JSON message to all connected clients for a store.

        Uses a snapshot copy of the connection set to prevent mutation
        issues if a disconnect occurs during iteration.

        Failed sends (stale connections) are silently removed.

        Args:
            store_id: UUID string of the store to broadcast to.
            message: JSON string to send (typically a QueueUpdateEvent).
        """
        if store_id not in self._connections:
            return

        # Snapshot — prevent iteration issues if set changes
        connections = self._connections[store_id].copy()
        if not connections:
            return

        stale: list[WebSocket] = []

        for ws in connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
                else:
                    stale.append(ws)
            except Exception as exc:
                # Connection dropped without clean close
                logger.debug(
                    "WS send failed — marking stale",
                    store_id=store_id,
                    error=str(exc),
                )
                stale.append(ws)

        # Clean up stale connections
        if stale:
            async with self._lock:
                for ws in stale:
                    self._connections.get(store_id, set()).discard(ws)
                if store_id in self._connections and not self._connections[store_id]:
                    del self._connections[store_id]

    def get_connection_count(self, store_id: str) -> int:
        """Return number of active WebSocket connections for a store."""
        return len(self._connections.get(store_id, set()))

    def get_total_connections(self) -> int:
        """Return total active WebSocket connections across all stores."""
        return sum(len(conns) for conns in self._connections.values())

    def get_connected_stores(self) -> list[str]:
        """Return list of store IDs that have at least one active connection."""
        return list(self._connections.keys())

    @property
    def stats(self) -> dict:
        """Return a stats snapshot for the /health endpoint."""
        return {
            "total_connections": self.get_total_connections(),
            "connected_stores": len(self._connections),
            "connections_by_store": {
                store_id: len(conns)
                for store_id, conns in self._connections.items()
            },
        }


# Module-level singleton — shared across all FastAPI worker tasks
connection_manager = ConnectionManager()
