"""
RetailFlow AI — Integration Tests: Store & Counter API

Tests all store management endpoints with full RBAC enforcement.
Uses the in-memory SQLite test database from conftest.py.
"""

import uuid

import pytest
from httpx import AsyncClient


# =============================================================================
# Fixtures: Register and authenticate test users
# =============================================================================

@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    """Registers and logs in an admin user, returns access token."""
    admin_data = {
        "email": "admin@retailflow.test",
        "password": "AdminPass123!",
        "full_name": "Test Admin",
        "role": "admin",
    }
    await client.post("/api/v1/auth/register", json=admin_data)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_data["email"], "password": admin_data["password"]},
    )
    return login.json()["data"]["access_token"]


@pytest.fixture
async def manager_token(client: AsyncClient) -> str:
    """Registers and logs in a manager user, returns access token."""
    manager_data = {
        "email": "manager@retailflow.test",
        "password": "ManagerPass123!",
        "full_name": "Test Manager",
        "role": "manager",
    }
    await client.post("/api/v1/auth/register", json=manager_data)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": manager_data["email"], "password": manager_data["password"]},
    )
    return login.json()["data"]["access_token"]


@pytest.fixture
async def manager_user_id(client: AsyncClient, manager_token: str) -> str:
    """Returns the manager's user ID."""
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    return me.json()["data"]["id"]


@pytest.fixture
def store_payload() -> dict:
    """Valid store creation payload."""
    return {
        "name": "D-Mart Andheri",
        "address": "Lokhandwala Complex",
        "city": "Mumbai",
        "state": "Maharashtra",
        "zip_code": "400053",
        "open_time": "09:00",
        "close_time": "22:00",
        "avg_service_time": 180,
    }


@pytest.fixture
async def created_store_id(
    client: AsyncClient,
    admin_token: str,
    store_payload: dict,
) -> str:
    """Creates a store and returns its ID."""
    response = await client.post(
        "/api/v1/stores",
        json=store_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


# =============================================================================
# Test: POST /api/v1/stores
# =============================================================================

class TestCreateStore:

    async def test_admin_can_create_store(
        self,
        client: AsyncClient,
        admin_token: str,
        store_payload: dict,
    ) -> None:
        """Admin can create a store and receives full store details."""
        response = await client.post(
            "/api/v1/stores",
            json=store_payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["name"] == store_payload["name"]
        assert body["data"]["city"] == store_payload["city"]
        assert body["data"]["open_time"] == store_payload["open_time"]
        assert "id" in body["data"]

    async def test_manager_cannot_create_store(
        self,
        client: AsyncClient,
        manager_token: str,
        store_payload: dict,
    ) -> None:
        """Managers do not have permission to create stores."""
        response = await client.post(
            "/api/v1/stores",
            json=store_payload,
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert response.status_code == 403

    async def test_unauthenticated_cannot_create_store(
        self,
        client: AsyncClient,
        store_payload: dict,
    ) -> None:
        """Unauthenticated requests are rejected."""
        response = await client.post("/api/v1/stores", json=store_payload)
        assert response.status_code == 401

    async def test_create_store_invalid_time_returns_422(
        self,
        client: AsyncClient,
        admin_token: str,
        store_payload: dict,
    ) -> None:
        """close_time must be after open_time."""
        store_payload["open_time"] = "22:00"
        store_payload["close_time"] = "09:00"  # Invalid: before open_time
        response = await client.post(
            "/api/v1/stores",
            json=store_payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    async def test_create_store_missing_required_fields(
        self,
        client: AsyncClient,
        admin_token: str,
    ) -> None:
        """Missing required fields return 422."""
        response = await client.post(
            "/api/v1/stores",
            json={"name": "Incomplete Store"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422


# =============================================================================
# Test: GET /api/v1/stores
# =============================================================================

class TestListStores:

    async def test_admin_sees_all_stores(
        self,
        client: AsyncClient,
        admin_token: str,
        created_store_id: str,
    ) -> None:
        """Admin can list all stores."""
        response = await client.get(
            "/api/v1/stores",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "items" in body["data"]
        assert "meta" in body["data"]
        assert body["data"]["meta"]["total"] >= 1

    async def test_manager_sees_only_assigned_stores(
        self,
        client: AsyncClient,
        admin_token: str,
        manager_token: str,
        created_store_id: str,
    ) -> None:
        """Manager with no assigned stores sees empty list."""
        response = await client.get(
            "/api/v1/stores",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert response.status_code == 200
        # Manager has no assignments yet
        assert response.json()["data"]["meta"]["total"] == 0


# =============================================================================
# Test: GET /api/v1/stores/{store_id}
# =============================================================================

class TestGetStore:

    async def test_admin_can_get_any_store(
        self,
        client: AsyncClient,
        admin_token: str,
        created_store_id: str,
    ) -> None:
        """Admin can retrieve any store's details."""
        response = await client.get(
            f"/api/v1/stores/{created_store_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == created_store_id
        assert "managers" in body["data"]
        assert "counters" in body["data"]

    async def test_manager_cannot_access_unassigned_store(
        self,
        client: AsyncClient,
        manager_token: str,
        created_store_id: str,
    ) -> None:
        """Manager gets 403 when accessing a store they're not assigned to."""
        response = await client.get(
            f"/api/v1/stores/{created_store_id}",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert response.status_code == 403

    async def test_get_nonexistent_store_returns_404(
        self,
        client: AsyncClient,
        admin_token: str,
    ) -> None:
        """Non-existent store ID returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/stores/{fake_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


# =============================================================================
# Test: Manager Assignment
# =============================================================================

class TestManagerAssignment:

    async def test_admin_can_assign_manager(
        self,
        client: AsyncClient,
        admin_token: str,
        manager_token: str,
        manager_user_id: str,
        created_store_id: str,
    ) -> None:
        """Admin can assign a manager to a store."""
        response = await client.post(
            f"/api/v1/stores/{created_store_id}/managers",
            json={"manager_id": manager_user_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_manager_can_access_assigned_store(
        self,
        client: AsyncClient,
        admin_token: str,
        manager_token: str,
        manager_user_id: str,
        created_store_id: str,
    ) -> None:
        """After assignment, manager can access the store."""
        # Assign manager
        await client.post(
            f"/api/v1/stores/{created_store_id}/managers",
            json={"manager_id": manager_user_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Manager can now access the store
        response = await client.get(
            f"/api/v1/stores/{created_store_id}",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert response.status_code == 200

    async def test_cannot_assign_manager_twice(
        self,
        client: AsyncClient,
        admin_token: str,
        manager_user_id: str,
        created_store_id: str,
    ) -> None:
        """Assigning the same manager twice returns 409."""
        await client.post(
            f"/api/v1/stores/{created_store_id}/managers",
            json={"manager_id": manager_user_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        response = await client.post(
            f"/api/v1/stores/{created_store_id}/managers",
            json={"manager_id": manager_user_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 409


# =============================================================================
# Test: Counter Management
# =============================================================================

class TestCounterManagement:

    @pytest.fixture
    async def assigned_store_id(
        self,
        client: AsyncClient,
        admin_token: str,
        manager_token: str,
        manager_user_id: str,
        created_store_id: str,
    ) -> str:
        """Creates a store and assigns the manager to it."""
        await client.post(
            f"/api/v1/stores/{created_store_id}/managers",
            json={"manager_id": manager_user_id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        return created_store_id

    async def test_create_counter(
        self,
        client: AsyncClient,
        manager_token: str,
        assigned_store_id: str,
    ) -> None:
        """Assigned manager can create a counter."""
        response = await client.post(
            f"/api/v1/stores/{assigned_store_id}/counters",
            json={"counter_number": 1, "label": "Express Lane", "status": "closed"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["counter_number"] == 1
        assert body["data"]["label"] == "Express Lane"

    async def test_duplicate_counter_number_returns_409(
        self,
        client: AsyncClient,
        manager_token: str,
        assigned_store_id: str,
    ) -> None:
        """Same counter number in same store returns 409."""
        payload = {"counter_number": 5, "status": "closed"}
        await client.post(
            f"/api/v1/stores/{assigned_store_id}/counters",
            json=payload,
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        response = await client.post(
            f"/api/v1/stores/{assigned_store_id}/counters",
            json=payload,
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert response.status_code == 409

    async def test_update_counter_status(
        self,
        client: AsyncClient,
        admin_token: str,
        manager_token: str,
        assigned_store_id: str,
    ) -> None:
        """Counter status can be updated."""
        create_resp = await client.post(
            f"/api/v1/stores/{assigned_store_id}/counters",
            json={"counter_number": 10, "status": "closed"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        counter_id = create_resp.json()["data"]["id"]

        update_resp = await client.patch(
            f"/api/v1/stores/{assigned_store_id}/counters/{counter_id}",
            json={"status": "open"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["data"]["status"] == "open"

    async def test_list_counters_by_status(
        self,
        client: AsyncClient,
        manager_token: str,
        assigned_store_id: str,
    ) -> None:
        """Counters can be filtered by status."""
        # Create 2 counters
        await client.post(
            f"/api/v1/stores/{assigned_store_id}/counters",
            json={"counter_number": 20, "status": "open"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        await client.post(
            f"/api/v1/stores/{assigned_store_id}/counters",
            json={"counter_number": 21, "status": "closed"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )

        response = await client.get(
            f"/api/v1/stores/{assigned_store_id}/counters?status=open",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert response.status_code == 200
        items = response.json()["data"]
        assert all(c["status"] == "open" for c in items)
