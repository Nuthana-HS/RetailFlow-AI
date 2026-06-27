"""
RetailFlow AI — Integration Tests: Camera Zone API

Tests for zone configuration endpoints.
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def camera_setup(client: AsyncClient):
    """Creates admin + store + counter for camera zone tests."""
    await client.post("/api/v1/auth/register", json={
        "email": "admin@camera.test",
        "password": "AdminPass123!",
        "full_name": "Camera Admin",
        "role": "admin",
    })
    admin_token = (await client.post("/api/v1/auth/login", json={
        "email": "admin@camera.test", "password": "AdminPass123!",
    })).json()["data"]["access_token"]

    store_id = (await client.post("/api/v1/stores", json={
        "name": "Camera Test Store",
        "address": "99 CV Street",
        "city": "Hyderabad",
        "state": "Telangana",
        "open_time": "09:00",
        "close_time": "22:00",
        "avg_service_time": 150,
    }, headers={"Authorization": f"Bearer {admin_token}"})).json()["data"]["id"]

    counter_id = (await client.post(f"/api/v1/stores/{store_id}/counters", json={
        "counter_number": 1, "status": "closed",
    }, headers={"Authorization": f"Bearer {admin_token}"})).json()["data"]["id"]

    return {"admin_token": admin_token, "store_id": store_id, "counter_id": counter_id}


@pytest.fixture
def valid_zone_payload() -> dict:
    return {
        "camera_source": "simulation",
        "zone_x1": 100.0, "zone_y1": 50.0,
        "zone_x2": 600.0, "zone_y2": 500.0,
        "frame_width": 1280, "frame_height": 720,
        "min_confidence": 0.50,
        "update_interval_seconds": 5,
    }


class TestCreateCameraZone:

    async def test_create_zone_returns_201(
        self, client: AsyncClient, camera_setup: dict, valid_zone_payload: dict
    ) -> None:
        r = await client.post(
            f"/api/v1/cameras/stores/{camera_setup['store_id']}/counters/{camera_setup['counter_id']}/zone",
            json=valid_zone_payload,
            headers={"Authorization": f"Bearer {camera_setup['admin_token']}"},
        )
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["zone_x1"] == 100.0
        assert data["camera_source"] == "simulation"

    async def test_duplicate_zone_returns_409(
        self, client: AsyncClient, camera_setup: dict, valid_zone_payload: dict
    ) -> None:
        headers = {"Authorization": f"Bearer {camera_setup['admin_token']}"}
        url = f"/api/v1/cameras/stores/{camera_setup['store_id']}/counters/{camera_setup['counter_id']}/zone"
        await client.post(url, json=valid_zone_payload, headers=headers)
        r = await client.post(url, json=valid_zone_payload, headers=headers)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "ZONE_EXISTS"

    async def test_invalid_coordinates_returns_422(
        self, client: AsyncClient, camera_setup: dict, valid_zone_payload: dict
    ) -> None:
        """x2 < x1 should fail validation."""
        bad_payload = {**valid_zone_payload, "zone_x2": 50.0}  # x2 < x1=100
        r = await client.post(
            f"/api/v1/cameras/stores/{camera_setup['store_id']}/counters/{camera_setup['counter_id']}/zone",
            json=bad_payload,
            headers={"Authorization": f"Bearer {camera_setup['admin_token']}"},
        )
        assert r.status_code == 422

    async def test_rtsp_source_requires_url(
        self, client: AsyncClient, camera_setup: dict, valid_zone_payload: dict
    ) -> None:
        """RTSP source without camera_url returns 422."""
        bad_payload = {**valid_zone_payload, "camera_source": "rtsp", "camera_url": None}
        r = await client.post(
            f"/api/v1/cameras/stores/{camera_setup['store_id']}/counters/{camera_setup['counter_id']}/zone",
            json=bad_payload,
            headers={"Authorization": f"Bearer {camera_setup['admin_token']}"},
        )
        assert r.status_code == 422


class TestGetCameraZone:

    async def test_get_existing_zone(
        self, client: AsyncClient, camera_setup: dict, valid_zone_payload: dict
    ) -> None:
        headers = {"Authorization": f"Bearer {camera_setup['admin_token']}"}
        url = f"/api/v1/cameras/stores/{camera_setup['store_id']}/counters/{camera_setup['counter_id']}/zone"
        await client.post(url, json=valid_zone_payload, headers=headers)
        r = await client.get(url, headers=headers)
        assert r.status_code == 200
        assert r.json()["data"]["counter_id"] == camera_setup["counter_id"]

    async def test_get_nonexistent_zone_returns_404(
        self, client: AsyncClient, camera_setup: dict
    ) -> None:
        r = await client.get(
            f"/api/v1/cameras/stores/{camera_setup['store_id']}/counters/{camera_setup['counter_id']}/zone",
            headers={"Authorization": f"Bearer {camera_setup['admin_token']}"},
        )
        assert r.status_code == 404


class TestListCameraZones:

    async def test_list_zones_for_store(
        self, client: AsyncClient, camera_setup: dict, valid_zone_payload: dict
    ) -> None:
        headers = {"Authorization": f"Bearer {camera_setup['admin_token']}"}
        await client.post(
            f"/api/v1/cameras/stores/{camera_setup['store_id']}/counters/{camera_setup['counter_id']}/zone",
            json=valid_zone_payload, headers=headers,
        )
        r = await client.get(
            f"/api/v1/cameras/stores/{camera_setup['store_id']}/zones",
            headers=headers,
        )
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1


class TestDeleteCameraZone:

    async def test_delete_zone_removes_it(
        self, client: AsyncClient, camera_setup: dict, valid_zone_payload: dict
    ) -> None:
        headers = {"Authorization": f"Bearer {camera_setup['admin_token']}"}
        url = f"/api/v1/cameras/stores/{camera_setup['store_id']}/counters/{camera_setup['counter_id']}/zone"
        await client.post(url, json=valid_zone_payload, headers=headers)
        r = await client.delete(url, headers=headers)
        assert r.status_code == 200
        # Zone is now gone
        r2 = await client.get(url, headers=headers)
        assert r2.status_code == 404
