"""
RetailFlow AI — Integration Tests: Notification API

Tests the full notification lifecycle:
1. Manager creates an alert config.
2. Queue length exceeds threshold.
3. Notification is generated in the inbox.
4. Manager marks it as read.
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def notification_setup(client: AsyncClient):
    """Creates admin, store, manager, counter, and alert config."""
    # 1. Admin login
    await client.post("/api/v1/auth/register", json={
        "email": "admin@notify.test",
        "password": "AdminPass123!",
        "full_name": "Notify Admin",
        "role": "admin",
    })
    admin_token = (await client.post("/api/v1/auth/login", json={
        "email": "admin@notify.test", "password": "AdminPass123!",
    })).json()["data"]["access_token"]

    # 2. Manager login
    await client.post("/api/v1/auth/register", json={
        "email": "manager@notify.test",
        "password": "ManagerPass123!",
        "full_name": "Notify Manager",
        "role": "manager",
    })
    manager_token = (await client.post("/api/v1/auth/login", json={
        "email": "manager@notify.test", "password": "ManagerPass123!",
    })).json()["data"]["access_token"]
    manager_id = (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {manager_token}"})).json()["data"]["id"]

    # 3. Create store and assign manager
    store_id = (await client.post("/api/v1/stores", json={
        "name": "Notify Store",
        "address": "123 Alert Ave",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "open_time": "08:00",
        "close_time": "20:00",
        "avg_service_time": 120,
    }, headers={"Authorization": f"Bearer {admin_token}"})).json()["data"]["id"]

    await client.post(f"/api/v1/stores/{store_id}/managers", json={
        "user_id": manager_id
    }, headers={"Authorization": f"Bearer {admin_token}"})

    # 4. Create counter and open it
    counter_id = (await client.post(f"/api/v1/stores/{store_id}/counters", json={
        "counter_number": 1, "status": "open",
    }, headers={"Authorization": f"Bearer {admin_token}"})).json()["data"]["id"]

    # 5. Create alert config (Threshold = 5 customers)
    alert_config = await client.post(f"/api/v1/queues/stores/{store_id}/alerts", json={
        "alert_type": "queue_length",
        "threshold": 5,
        "cooldown_minutes": 0,  # 0 for testing so we don't hit cooldown logic
        "is_active": True,
    }, headers={"Authorization": f"Bearer {manager_token}"})
    alert_id = alert_config.json()["data"]["id"]

    return {
        "admin_token": admin_token,
        "manager_token": manager_token,
        "store_id": store_id,
        "counter_id": counter_id,
        "alert_id": alert_id,
    }


class TestNotificationLifecycle:

    async def test_inbox_empty_initially(self, client: AsyncClient, notification_setup: dict) -> None:
        r = await client.get(
            "/api/v1/notifications/",
            headers={"Authorization": f"Bearer {notification_setup['manager_token']}"}
        )
        assert r.status_code == 200
        assert r.json()["data"]["total"] == 0

    async def test_trigger_alert_creates_notification(self, client: AsyncClient, notification_setup: dict) -> None:
        headers = {"Authorization": f"Bearer {notification_setup['manager_token']}"}
        
        # Trigger alert by setting queue length to 6 (threshold is 5)
        r_update = await client.post(
            f"/api/v1/queues/stores/{notification_setup['store_id']}/counters/{notification_setup['counter_id']}/update",
            json={"queue_length": 6, "source": "manual"},
            headers=headers
        )
        assert r_update.status_code == 200

        # Check inbox
        r_inbox = await client.get("/api/v1/notifications/", headers=headers)
        assert r_inbox.status_code == 200
        data = r_inbox.json()["data"]
        
        assert data["total"] == 1
        assert data["unread_count"] == 1
        
        notif = data["notifications"][0]
        assert notif["alert_type"] == "queue_length"
        assert notif["trigger_value"] == 6
        assert notif["threshold"] == 5
        assert notif["is_read"] is False

    async def test_mark_as_read(self, client: AsyncClient, notification_setup: dict) -> None:
        headers = {"Authorization": f"Bearer {notification_setup['manager_token']}"}
        
        # Trigger alert
        await client.post(
            f"/api/v1/queues/stores/{notification_setup['store_id']}/counters/{notification_setup['counter_id']}/update",
            json={"queue_length": 6, "source": "manual"},
            headers=headers
        )

        # Get notification ID
        r_inbox = await client.get("/api/v1/notifications/", headers=headers)
        notif_id = r_inbox.json()["data"]["notifications"][0]["id"]

        # Mark as read
        r_read = await client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers)
        assert r_read.status_code == 200
        assert r_read.json()["data"]["is_read"] is True

        # Verify unread count is 0
        r_count = await client.get("/api/v1/notifications/unread-count", headers=headers)
        assert r_count.status_code == 200
        assert r_count.json()["data"]["unread_count"] == 0

    async def test_mark_all_as_read(self, client: AsyncClient, notification_setup: dict) -> None:
        headers = {"Authorization": f"Bearer {notification_setup['manager_token']}"}
        
        # Trigger two alerts
        await client.post(
            f"/api/v1/queues/stores/{notification_setup['store_id']}/counters/{notification_setup['counter_id']}/update",
            json={"queue_length": 6, "source": "manual"},
            headers=headers
        )
        await client.post(
            f"/api/v1/queues/stores/{notification_setup['store_id']}/counters/{notification_setup['counter_id']}/update",
            json={"queue_length": 7, "source": "manual"},
            headers=headers
        )

        # Check unread count is 2
        r_count = await client.get("/api/v1/notifications/unread-count", headers=headers)
        assert r_count.json()["data"]["unread_count"] == 2

        # Mark all as read
        r_read_all = await client.post("/api/v1/notifications/read-all", headers=headers)
        assert r_read_all.status_code == 200
        assert r_read_all.json()["data"]["marked_read"] == 2

        # Verify unread count is 0
        r_count_after = await client.get("/api/v1/notifications/unread-count", headers=headers)
        assert r_count_after.json()["data"]["unread_count"] == 0
