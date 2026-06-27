"""
RetailFlow AI — WebSocket Router

Single WebSocket endpoint that bridges Redis Pub/Sub to browser clients.

Endpoint:
    WS  /ws/stores/{store_id}/queue?token=<JWT>

Authentication:
    JWT is passed as a query parameter because browsers cannot set custom
    HTTP headers on WebSocket upgrade requests.
    The token is validated the same way as REST endpoints (same decode_access_token).

Connection Lifecycle:
    1. Client connects with ?token=<JWT>
    2. Server validates JWT (close 4001 if invalid)
    3. Server checks RBAC (close 4003 if forbidden)
    4. Server accepts connection + sends welcome message with current store state
    5. Server subscribes to Redis channel: queue:events:store:{store_id}
    6. Server runs two concurrent loops:
         ├── Redis loop:  forwards pub/sub messages → WebSocket
         └── Client loop: handles client messages (ping → pong)
    7. When either loop exits (disconnect/error), both are cancelled
    8. Cleanup: unregister from ConnectionManager + unsubscribe from Redis

WebSocket Close Codes (RFC 6455 + private range 4000-4999):
    1000: Normal close
    1011: Internal server error
    4001: Unauthorized (invalid/expired JWT)
    4003: Forbidden (RBAC check failed — not assigned to this store)
    4004: Store not found

Message Format (server → client):
    Queue update events (from Phase 5 QueueUpdateEvent):
        {
            "event_type": "queue_update",
            "store_id": "...",
            "counter_id": "...",
            "queue_length": 7,
            "estimated_wait_seconds": 840,
            "counter_number": 3,
            "status": "open",
            "timestamp": "2026-06-27T10:00:00Z",
            "source": "manual"
        }

    Welcome message (sent on connect):
        {
            "event_type": "connected",
            "store_id": "...",
            "message": "Connected to RetailFlow AI queue stream",
            "timestamp": "..."
        }

    Pong response (heartbeat):
        {"event_type": "pong", "timestamp": "..."}

Message Format (client → server):
    Ping (heartbeat):
        {"type": "ping"}
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import RedisKeys, get_redis
from app.core.security import decode_access_token
from app.models.user import UserRole
from app.repositories.store_repository import StoreRepository
from app.repositories.user_repository import UserRepository
from app.websocket.connection_manager import connection_manager

logger = structlog.get_logger(__name__)

router = APIRouter()

# Heartbeat interval: send ping to detect stale connections
_HEARTBEAT_INTERVAL_SECONDS = 30
_HEARTBEAT_TIMEOUT_SECONDS = 10


# =============================================================================
# Helper: Send JSON message to a WebSocket
# =============================================================================

async def _send_json(ws: WebSocket, data: dict) -> None:
    """Send a JSON-serialized message to a WebSocket client."""
    await ws.send_text(json.dumps(data, default=str))


# =============================================================================
# Helper: Authenticate WebSocket request
# =============================================================================

async def _authenticate_ws(
    token: str,
    db: AsyncSession,
    store_id: uuid.UUID,
) -> tuple:
    """
    Validate JWT token and RBAC for a WebSocket connection.

    Returns:
        Tuple of (user, store) if valid.

    Raises:
        ValueError: With a message describing the failure.
    """
    user_repo = UserRepository()
    store_repo = StoreRepository()

    # Decode JWT
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload.sub)
    except (JWTError, ValueError, AttributeError) as exc:
        raise ValueError("Invalid or expired access token") from exc

    # Fetch user
    user = await user_repo.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise ValueError("User not found or account inactive")

    # Fetch store
    store = await store_repo.get_by_id(db, store_id)
    if store is None:
        raise ValueError("Store not found")

    # RBAC: managers can only connect to their assigned stores
    if user.role == UserRole.MANAGER:
        is_assigned = await store_repo.is_manager_of_store(db, user.id, store_id)
        if not is_assigned:
            raise PermissionError(
                f"Manager {user.email!r} is not assigned to store {store_id}"
            )

    return user, store


# =============================================================================
# Helper: Redis Pub/Sub → WebSocket listener
# =============================================================================

async def _redis_to_ws_loop(
    websocket: WebSocket,
    redis: Redis,
    store_id: str,
) -> None:
    """
    Subscribe to the store's Redis Pub/Sub channel and forward messages
    to the connected WebSocket client.

    This coroutine runs until:
      - The WebSocket closes (WebSocketDisconnect)
      - The Redis connection drops (Exception)
      - The parent task cancels it (asyncio.CancelledError)

    Note on Redis PubSub:
        pubsub.listen() is an async generator. Each iteration returns a
        message dict with keys: type, channel, data.
        type == "message" means it's a real event (not subscribe/unsubscribe).
    """
    channel = RedisKeys.queue_events_channel(store_id)
    pubsub = redis.pubsub()

    try:
        await pubsub.subscribe(channel)
        logger.info("Redis subscribed", store_id=store_id, channel=channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                # Forward the raw JSON string from Redis directly to WS
                payload = message["data"]
                try:
                    await websocket.send_text(payload)
                    logger.debug(
                        "WS message forwarded",
                        store_id=store_id,
                        payload_preview=payload[:80],
                    )
                except WebSocketDisconnect:
                    logger.info("WS disconnected during send", store_id=store_id)
                    return
                except Exception as exc:
                    logger.warning("WS send failed", store_id=store_id, error=str(exc))
                    return

    except asyncio.CancelledError:
        logger.debug("Redis listener cancelled", store_id=store_id)
    except Exception as exc:
        logger.error("Redis listener error", store_id=store_id, error=str(exc))
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:
            pass  # Best effort cleanup


# =============================================================================
# Helper: Client → Server message handler (heartbeat)
# =============================================================================

async def _client_message_loop(websocket: WebSocket) -> None:
    """
    Listen for messages from the WebSocket client.

    Handles:
        ping → responds with pong (heartbeat for connection liveness)
        close → exits naturally (WebSocketDisconnect raised)

    All unknown messages are silently ignored.
    """
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue  # Ignore malformed messages

            if msg.get("type") == "ping":
                await _send_json(
                    websocket,
                    {
                        "event_type": "pong",
                        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    },
                )

    except WebSocketDisconnect:
        logger.info("Client disconnected (receive loop ended)")
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.warning("Client message loop error", error=str(exc))


# =============================================================================
# Helper: Heartbeat sender
# =============================================================================

async def _heartbeat_loop(websocket: WebSocket, store_id: str) -> None:
    """
    Periodically send a server-side ping to detect stale connections.

    If the client has gone away without a clean close (e.g., browser tab crash),
    the send will raise an exception, which exits the loop and triggers cleanup.
    """
    try:
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)
            await _send_json(
                websocket,
                {
                    "event_type": "heartbeat",
                    "store_id": store_id,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "connections": connection_manager.get_connection_count(store_id),
                },
            )
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as exc:
        logger.debug("Heartbeat failed — connection likely dropped", error=str(exc))


# =============================================================================
# WebSocket Endpoint
# =============================================================================

@router.websocket("/stores/{store_id}/queue")
async def ws_queue_endpoint(
    websocket: WebSocket,
    store_id: uuid.UUID,
    token: str = Query(..., description="JWT access token for authentication"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> None:
    """
    WebSocket endpoint: real-time queue state stream for a store.

    Connect: ws://host/ws/stores/{store_id}/queue?token=<JWT>

    On connect:
      - Authenticates the JWT token
      - Checks RBAC (manager must be assigned to this store)
      - Sends welcome message with store info
      - Subscribes to Redis channel queue:events:store:{store_id}
      - Forwards all queue update events to this client

    On disconnect:
      - Unregisters from ConnectionManager
      - Unsubscribes from Redis channel
    """
    log = logger.bind(store_id=str(store_id), client=websocket.client)

    # ── Authentication & RBAC ─────────────────────────────────────────────────
    try:
        user, store = await _authenticate_ws(token, db, store_id)
    except PermissionError as exc:
        log.warning("WS connection forbidden", error=str(exc))
        await websocket.close(code=4003, reason="Forbidden")
        return
    except ValueError as exc:
        log.warning("WS auth failed", error=str(exc))
        await websocket.close(code=4001, reason="Unauthorized")
        return
    except Exception as exc:
        log.error("WS auth internal error", error=str(exc))
        await websocket.close(code=1011, reason="Internal server error")
        return

    # ── Accept Connection ─────────────────────────────────────────────────────
    await websocket.accept()
    await connection_manager.connect(websocket, str(store_id))
    log.info(
        "WS connection accepted",
        user_id=str(user.id),
        email=user.email,
        total_for_store=connection_manager.get_connection_count(str(store_id)),
    )

    # ── Welcome Message ───────────────────────────────────────────────────────
    await _send_json(
        websocket,
        {
            "event_type": "connected",
            "store_id": str(store_id),
            "store_name": store.name,
            "user_id": str(user.id),
            "message": "Connected to RetailFlow AI real-time queue stream",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "hint": (
                "Poll GET /api/v1/queues/stores/{store_id} for current state. "
                "This stream will push updates as they occur."
            ),
        },
    )

    # ── Start Concurrent Loops ────────────────────────────────────────────────
    # Three tasks run simultaneously:
    #   1. redis_task:     Redis pub/sub → WebSocket (main data pipeline)
    #   2. client_task:    client → server messages (ping/pong handler)
    #   3. heartbeat_task: server → client periodic ping (liveness check)
    #
    # When ANY one task exits (disconnect/error/cancel), the others are cancelled.

    redis_task = asyncio.create_task(
        _redis_to_ws_loop(websocket, redis, str(store_id)),
        name=f"redis_ws_{store_id}",
    )
    client_task = asyncio.create_task(
        _client_message_loop(websocket),
        name=f"client_ws_{store_id}",
    )
    heartbeat_task = asyncio.create_task(
        _heartbeat_loop(websocket, str(store_id)),
        name=f"heartbeat_ws_{store_id}",
    )

    try:
        # Wait for the FIRST task to complete, then cancel the rest
        done, pending = await asyncio.wait(
            [redis_task, client_task, heartbeat_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Log which task finished first
        for task in done:
            if task.exception():
                log.warning(
                    "WS task exited with error",
                    task=task.get_name(),
                    error=str(task.exception()),
                )
            else:
                log.debug("WS task completed normally", task=task.get_name())

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    except Exception as exc:
        log.error("WS handler unexpected error", error=str(exc))

    finally:
        # ── Cleanup (always runs) ─────────────────────────────────────────────
        await connection_manager.disconnect(websocket, str(store_id))

        # Close WebSocket if still open
        try:
            await websocket.close()
        except Exception:
            pass  # Already closed

        log.info(
            "WS connection closed",
            user_id=str(user.id),
            remaining_for_store=connection_manager.get_connection_count(str(store_id)),
        )
