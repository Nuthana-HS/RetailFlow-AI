"""
RetailFlow AI — Unit Tests: WebSocket Connection Manager

Tests for ConnectionManager logic without a real WebSocket connection.
Uses MagicMock to simulate WebSocket objects.

Coverage:
  - connect() registers the connection
  - disconnect() removes it (and cleans up empty store entries)
  - broadcast_to_store() sends to all connected clients
  - broadcast_to_store() handles stale connections gracefully
  - get_connection_count() returns accurate count
  - get_total_connections() sums across stores
  - stats property returns correct structure
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.websockets import WebSocketState

from app.websocket.connection_manager import ConnectionManager


def _make_ws(connected: bool = True) -> MagicMock:
    """Create a mock WebSocket with controllable client_state."""
    ws = MagicMock()
    ws.client_state = WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
    ws.send_text = AsyncMock()
    return ws


# =============================================================================
# Test: connect() / disconnect()
# =============================================================================

class TestConnectionRegistration:

    @pytest.mark.asyncio
    async def test_connect_registers_websocket(self) -> None:
        """Connected WebSocket appears in the registry."""
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws, "store-a")
        assert mgr.get_connection_count("store-a") == 1

    @pytest.mark.asyncio
    async def test_connect_multiple_to_same_store(self) -> None:
        """Multiple connections to the same store are all tracked."""
        mgr = ConnectionManager()
        ws1, ws2, ws3 = _make_ws(), _make_ws(), _make_ws()
        await mgr.connect(ws1, "store-a")
        await mgr.connect(ws2, "store-a")
        await mgr.connect(ws3, "store-a")
        assert mgr.get_connection_count("store-a") == 3

    @pytest.mark.asyncio
    async def test_connect_different_stores(self) -> None:
        """Connections to different stores are isolated."""
        mgr = ConnectionManager()
        ws1, ws2 = _make_ws(), _make_ws()
        await mgr.connect(ws1, "store-a")
        await mgr.connect(ws2, "store-b")
        assert mgr.get_connection_count("store-a") == 1
        assert mgr.get_connection_count("store-b") == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self) -> None:
        """Disconnecting a WS removes it from the registry."""
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws, "store-a")
        await mgr.disconnect(ws, "store-a")
        assert mgr.get_connection_count("store-a") == 0

    @pytest.mark.asyncio
    async def test_disconnect_empty_store_clears_key(self) -> None:
        """After all connections leave, the store key is removed."""
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws, "store-x")
        await mgr.disconnect(ws, "store-x")
        assert "store-x" not in mgr._connections

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_is_safe(self) -> None:
        """Disconnecting a WS that was never registered does not raise."""
        mgr = ConnectionManager()
        ws = _make_ws()
        # Should not raise
        await mgr.disconnect(ws, "store-unknown")
        assert mgr.get_connection_count("store-unknown") == 0

    @pytest.mark.asyncio
    async def test_partial_disconnect_leaves_others(self) -> None:
        """Disconnecting one WS does not remove others from same store."""
        mgr = ConnectionManager()
        ws1, ws2 = _make_ws(), _make_ws()
        await mgr.connect(ws1, "store-a")
        await mgr.connect(ws2, "store-a")
        await mgr.disconnect(ws1, "store-a")
        assert mgr.get_connection_count("store-a") == 1


# =============================================================================
# Test: broadcast_to_store()
# =============================================================================

class TestBroadcast:

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connected(self) -> None:
        """Broadcast delivers message to all connected clients."""
        mgr = ConnectionManager()
        ws1, ws2 = _make_ws(), _make_ws()
        await mgr.connect(ws1, "store-a")
        await mgr.connect(ws2, "store-a")

        await mgr.broadcast_to_store("store-a", '{"event_type":"queue_update"}')

        ws1.send_text.assert_called_once_with('{"event_type":"queue_update"}')
        ws2.send_text.assert_called_once_with('{"event_type":"queue_update"}')

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_store_does_not_raise(self) -> None:
        """Broadcasting to a store with no connections does nothing."""
        mgr = ConnectionManager()
        # No connections registered for "store-empty"
        await mgr.broadcast_to_store("store-empty", '{"event_type":"test"}')
        # No exception = test passes

    @pytest.mark.asyncio
    async def test_broadcast_skips_disconnected_clients(self) -> None:
        """Disconnected WebSockets (state != CONNECTED) are skipped."""
        mgr = ConnectionManager()
        ws_dead = _make_ws(connected=False)
        ws_live = _make_ws(connected=True)

        await mgr.connect(ws_dead, "store-a")
        await mgr.connect(ws_live, "store-a")

        await mgr.broadcast_to_store("store-a", '{"event_type":"test"}')

        # Live WS got the message
        ws_live.send_text.assert_called_once()
        # Dead WS was skipped
        ws_dead.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_removes_stale_on_exception(self) -> None:
        """If send raises an exception, the stale WS is removed."""
        mgr = ConnectionManager()
        ws_stale = _make_ws()
        ws_stale.send_text = AsyncMock(side_effect=RuntimeError("Connection reset"))
        ws_good = _make_ws()

        await mgr.connect(ws_stale, "store-a")
        await mgr.connect(ws_good, "store-a")

        await mgr.broadcast_to_store("store-a", '{"event_type":"test"}')

        # Stale connection should be removed
        assert ws_stale not in mgr._connections.get("store-a", set())
        # Good connection should still be there
        assert ws_good in mgr._connections.get("store-a", set())


# =============================================================================
# Test: stats and count helpers
# =============================================================================

class TestStats:

    @pytest.mark.asyncio
    async def test_get_total_connections_sum(self) -> None:
        """get_total_connections sums across all stores."""
        mgr = ConnectionManager()
        for store in ["s1", "s2", "s3"]:
            ws = _make_ws()
            await mgr.connect(ws, store)
        assert mgr.get_total_connections() == 3

    @pytest.mark.asyncio
    async def test_get_connected_stores_list(self) -> None:
        """get_connected_stores returns stores with active connections."""
        mgr = ConnectionManager()
        ws1, ws2 = _make_ws(), _make_ws()
        await mgr.connect(ws1, "store-a")
        await mgr.connect(ws2, "store-b")
        stores = mgr.get_connected_stores()
        assert "store-a" in stores
        assert "store-b" in stores

    @pytest.mark.asyncio
    async def test_stats_structure(self) -> None:
        """stats property returns dict with expected keys."""
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws, "store-z")
        stats = mgr.stats
        assert "total_connections" in stats
        assert "connected_stores" in stats
        assert "connections_by_store" in stats
        assert stats["total_connections"] == 1
        assert stats["connected_stores"] == 1
        assert "store-z" in stats["connections_by_store"]

    @pytest.mark.asyncio
    async def test_empty_stats(self) -> None:
        """Empty ConnectionManager returns zero stats."""
        mgr = ConnectionManager()
        stats = mgr.stats
        assert stats["total_connections"] == 0
        assert stats["connected_stores"] == 0
        assert stats["connections_by_store"] == {}
