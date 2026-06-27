"""
RetailFlow AI — Integration Tests: Queue Engine API

Tests all queue endpoints with full flow:
  register → login → create store → assign manager → create counter
  → open counter → update queue → read state → check history → configure alert

These tests use the fake Redis client from conftest.py to avoid requiring
a real Redis instance in CI.
"""

import pytest
from httpx import AsyncClient


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
async def full_setup(client: AsyncClient):
    """
    End-to-end fixture: creates admin + manager + store + counter.

    Returns dict with all the IDs and tokens needed for queue tests.
    """
    # Create admin
    await client.post("/api/v1/auth/register", json={
        "email": "admin@queue.test",
        "password": "AdminPass123!",
        "full_name": "Queue Admin",
        "role": "admin",
    })
    admin_login = await client.post("/api/v1/auth/login", json={
        "email": "admin@queue.test", "password": "AdminPass123!",
    })
    admin_token = admin_login.json()["data"]["access_token"]

    # Create manager
    await client.post("/api/v1/auth/register", json={
        "email": "manager@queue.test",
        "password": "ManagerPass123!",
        "full_name": "Queue Manager",
        "role": "manager",
    })
    mgr_login = await client.post("/api/v1/auth/login", json={
        "email": "manager@queue.test", "password": "ManagerPass123!",
    })
    mgr_token = mgr_login.json()["data"]["access_token"]
    mgr_id = (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {mgr_token}"})).json()["data"]["id"]

    # Create store
    store_resp = await client.post("/api/v1/stores", json={
        "name": "Queue Test Store",
        "address": "123 Main St",
        "city": "Mumbai",
        "state": "Maharashtra",
        "open_time": "09:00",
        "close_time": "22:00",
        "avg_service_time": 120,
    }, headers={"Authorization": f"Bearer {admin_token}"})
    store_id = store_resp.json()["data"]["id"]

    # Assign manager
    await client.post(f"/api/v1/stores/{store_id}/managers",
        json={"manager_id": mgr_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Create counter
    counter_resp = await client.post(f"/api/v1/stores/{store_id}/counters",
        json={"counter_number": 1, "status": "open"},
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    counter_id = counter_resp.json()["data"]["id"]

    return {
        "admin_token": admin_token,
        "mgr_token": mgr_token,
        "mgr_id": mgr_id,
        "store_id": store_id,
        "counter_id": counter_id,
    }


# =============================================================================
# Test: GET /api/v1/queues/stores/{store_id}
# =============================================================================

class TestGetStoreQueueState:

    async def test_admin_can_get_store_queue_state(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """Admin gets the real-time queue state for a store."""
        response = await client.get(
            f"/api/v1/queues/stores/{full_setup['store_id']}",
            headers={"Authorization": f"Bearer {full_setup['admin_token']}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "store_id" in body["data"]
        assert "counters" in body["data"]
        assert isinstance(body["data"]["counters"], list)
        assert "total_customers_waiting" in body["data"]
        assert "open_counters" in body["data"]

    async def test_assigned_manager_can_get_store_queue(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """Assigned manager gets the queue state."""
        response = await client.get(
            f"/api/v1/queues/stores/{full_setup['store_id']}",
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        assert response.status_code == 200

    async def test_unassigned_manager_cannot_get_queue(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """Unassigned manager gets 403."""
        # Create another manager without store assignment
        await client.post("/api/v1/auth/register", json={
            "email": "other@queue.test",
            "password": "OtherPass123!",
            "full_name": "Other Manager",
            "role": "manager",
        })
        other_login = await client.post("/api/v1/auth/login", json={
            "email": "other@queue.test", "password": "OtherPass123!",
        })
        other_token = other_login.json()["data"]["access_token"]

        response = await client.get(
            f"/api/v1/queues/stores/{full_setup['store_id']}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 403

    async def test_unauthenticated_cannot_get_queue(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """No token → 401."""
        response = await client.get(
            f"/api/v1/queues/stores/{full_setup['store_id']}",
        )
        assert response.status_code == 401


# =============================================================================
# Test: POST /api/v1/queues/stores/{store_id}/counters/{id}/update
# =============================================================================

class TestUpdateCounterQueue:

    async def test_manager_can_update_open_counter(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """Assigned manager can update queue length for open counter."""
        response = await client.post(
            f"/api/v1/queues/stores/{full_setup['store_id']}/counters/{full_setup['counter_id']}/update",
            json={"queue_length": 7, "source": "manual"},
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["queue_length"] == 7
        assert body["data"]["counter_id"] == full_setup["counter_id"]
        assert "estimated_wait_seconds" in body["data"]
        assert "estimated_wait_formatted" in body["data"]

    async def test_estimated_wait_time_calculated(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """EWT is auto-calculated from avg_service_time (120s × 5 = 600s = ~10 min)."""
        response = await client.post(
            f"/api/v1/queues/stores/{full_setup['store_id']}/counters/{full_setup['counter_id']}/update",
            json={"queue_length": 5, "source": "manual"},
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        # avg_service_time = 120s, 5 customers → 600s EWT
        assert data["estimated_wait_seconds"] == 600
        assert data["estimated_wait_formatted"] == "~10 min"

    async def test_zero_queue_length_is_valid(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """Queue length of 0 (empty) is valid."""
        response = await client.post(
            f"/api/v1/queues/stores/{full_setup['store_id']}/counters/{full_setup['counter_id']}/update",
            json={"queue_length": 0, "source": "manual"},
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["queue_length"] == 0

    async def test_negative_queue_length_returns_422(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """Negative queue length fails validation."""
        response = await client.post(
            f"/api/v1/queues/stores/{full_setup['store_id']}/counters/{full_setup['counter_id']}/update",
            json={"queue_length": -1, "source": "manual"},
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        assert response.status_code == 422

    async def test_closed_counter_returns_409(
        self,
        client: AsyncClient,
        full_setup: dict,
        admin_token: str,
    ) -> None:
        """Cannot update queue for a closed counter (returns 409)."""
        # Close the counter
        await client.patch(
            f"/api/v1/stores/{full_setup['store_id']}/counters/{full_setup['counter_id']}",
            json={"status": "closed"},
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        # Try to update closed counter
        response = await client.post(
            f"/api/v1/queues/stores/{full_setup['store_id']}/counters/{full_setup['counter_id']}/update",
            json={"queue_length": 5, "source": "manual"},
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "COUNTER_CLOSED"


# =============================================================================
# Test: GET /api/v1/queues/stores/{store_id}/history
# =============================================================================

class TestQueueHistory:

    async def test_history_returns_snapshots(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """After updates, history endpoint returns snapshots."""
        # Create some snapshots
        for length in [3, 5, 8, 2]:
            await client.post(
                f"/api/v1/queues/stores/{full_setup['store_id']}/counters/{full_setup['counter_id']}/update",
                json={"queue_length": length, "source": "manual"},
                headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
            )

        response = await client.get(
            f"/api/v1/queues/stores/{full_setup['store_id']}/history",
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["total"] >= 4
        assert len(body["data"]["snapshots"]) >= 4

    async def test_history_respects_hours_filter(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """Hours filter is applied (1 hour look-back)."""
        response = await client.get(
            f"/api/v1/queues/stores/{full_setup['store_id']}/history?hours=1",
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        assert response.status_code == 200


# =============================================================================
# Test: Alert Configuration
# =============================================================================

class TestAlertConfig:

    async def test_create_store_level_alert(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """Create a store-wide alert for queue_length >= 10."""
        response = await client.post(
            f"/api/v1/queues/stores/{full_setup['store_id']}/alerts",
            json={
                "alert_type": "queue_length",
                "threshold": 10,
                "cooldown_minutes": 15,
                "is_active": True,
            },
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["threshold"] == 10
        assert body["data"]["alert_type"] == "queue_length"
        assert body["data"]["counter_id"] is None  # Store-level

    async def test_list_alerts_for_store(
        self,
        client: AsyncClient,
        full_setup: dict,
    ) -> None:
        """Can list all alerts for a store."""
        # Create alert first
        await client.post(
            f"/api/v1/queues/stores/{full_setup['store_id']}/alerts",
            json={"alert_type": "queue_length", "threshold": 8, "cooldown_minutes": 30},
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        response = await client.get(
            f"/api/v1/queues/stores/{full_setup['store_id']}/alerts",
            headers={"Authorization": f"Bearer {full_setup['mgr_token']}"},
        )
        assert response.status_code == 200
        assert len(response.json()["data"]) >= 1
