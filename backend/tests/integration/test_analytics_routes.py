"""
RetailFlow AI — Integration Tests: Analytics API

Tests all analytics endpoints with authenticated users and actual data flow.
Seeds the database with queue snapshots, then asserts analytics results.

IMPORTANT: These tests depend on the full setup (auth → store → counter → queue updates)
so they are designed to run in sequence using the shared full_setup fixture.
"""

import pytest
from httpx import AsyncClient


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
async def analytics_setup(client: AsyncClient):
    """
    Full analytics test setup:
    1. Admin + Manager registered and logged in
    2. Store created and manager assigned
    3. Counter created (open)
    4. Several queue updates inserted (seeds QueueSnapshot records)
    """
    # Admin
    await client.post("/api/v1/auth/register", json={
        "email": "admin@analytics.test",
        "password": "AdminPass123!",
        "full_name": "Analytics Admin",
        "role": "admin",
    })
    admin_token = (await client.post("/api/v1/auth/login", json={
        "email": "admin@analytics.test", "password": "AdminPass123!",
    })).json()["data"]["access_token"]

    # Manager
    await client.post("/api/v1/auth/register", json={
        "email": "manager@analytics.test",
        "password": "ManagerPass123!",
        "full_name": "Analytics Manager",
        "role": "manager",
    })
    mgr_resp = await client.post("/api/v1/auth/login", json={
        "email": "manager@analytics.test", "password": "ManagerPass123!",
    })
    mgr_token = mgr_resp.json()["data"]["access_token"]
    mgr_id = (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {mgr_token}"})).json()["data"]["id"]

    # Store
    store_id = (await client.post("/api/v1/stores", json={
        "name": "Analytics Test Store",
        "address": "100 Analytics Ave",
        "city": "Bangalore",
        "state": "Karnataka",
        "open_time": "08:00",
        "close_time": "22:00",
        "avg_service_time": 120,
    }, headers={"Authorization": f"Bearer {admin_token}"})).json()["data"]["id"]

    # Assign manager
    await client.post(f"/api/v1/stores/{store_id}/managers",
        json={"manager_id": mgr_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Counter
    counter_id = (await client.post(f"/api/v1/stores/{store_id}/counters",
        json={"counter_number": 1, "status": "open"},
        headers={"Authorization": f"Bearer {mgr_token}"},
    )).json()["data"]["id"]

    # Seed queue updates (creates QueueSnapshot records)
    for length in [2, 4, 6, 8, 3, 5, 7, 1, 9, 4]:
        await client.post(
            f"/api/v1/queues/stores/{store_id}/counters/{counter_id}/update",
            json={"queue_length": length, "source": "manual"},
            headers={"Authorization": f"Bearer {mgr_token}"},
        )

    return {
        "admin_token": admin_token,
        "mgr_token": mgr_token,
        "store_id": store_id,
        "counter_id": counter_id,
    }


# =============================================================================
# Test: GET /api/v1/analytics/stores/{store_id}/summary
# =============================================================================

class TestStoreSummary:

    async def test_summary_returns_200(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        """Analytics summary returns HTTP 200."""
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/summary",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        assert response.status_code == 200

    async def test_summary_has_required_fields(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        """Summary response contains all KPI metric fields."""
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/summary",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        data = response.json()["data"]
        required_fields = [
            "store_id", "store_name", "total_snapshots",
            "avg_queue_length", "peak_queue_length",
            "active_counters", "cached",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    async def test_summary_reflects_seeded_data(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        """Summary values match the seeded queue updates."""
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/summary",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        data = response.json()["data"]
        # We seeded 10 updates → at least 10 snapshots
        assert data["total_snapshots"] >= 10
        # Peak value was 9
        assert data["peak_queue_length"] >= 9
        # Average of [2,4,6,8,3,5,7,1,9,4] = 4.9
        assert 4.0 <= data["avg_queue_length"] <= 6.0

    async def test_summary_unassigned_manager_gets_403(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        """Unassigned manager cannot view analytics."""
        # Create an unassigned manager
        await client.post("/api/v1/auth/register", json={
            "email": "other@analytics.test",
            "password": "OtherPass123!",
            "full_name": "Other Manager",
            "role": "manager",
        })
        token = (await client.post("/api/v1/auth/login", json={
            "email": "other@analytics.test", "password": "OtherPass123!",
        })).json()["data"]["access_token"]

        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_summary_nonexistent_store_returns_404(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        """Non-existent store ID returns 404."""
        import uuid
        response = await client.get(
            f"/api/v1/analytics/stores/{uuid.uuid4()}/summary",
            headers={"Authorization": f"Bearer {analytics_setup['admin_token']}"},
        )
        assert response.status_code == 404


# =============================================================================
# Test: GET /api/v1/analytics/stores/{store_id}/peak-hours
# =============================================================================

class TestPeakHoursHeatmap:

    async def test_heatmap_returns_200(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/peak-hours",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        assert response.status_code == 200

    async def test_heatmap_has_cells_and_max(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        """Heatmap includes cells and max_avg_queue."""
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/peak-hours",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        data = response.json()["data"]
        assert "cells" in data
        assert "max_avg_queue" in data
        # There should be at least 1 cell with data (since we seeded updates)
        assert len(data["cells"]) >= 1

    async def test_heatmap_intensity_between_0_and_1(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        """All heatmap cells have intensity in [0.0, 1.0]."""
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/peak-hours",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        cells = response.json()["data"]["cells"]
        for cell in cells:
            assert 0.0 <= cell["intensity"] <= 1.0, f"Invalid intensity: {cell['intensity']}"


# =============================================================================
# Test: GET /api/v1/analytics/stores/{store_id}/trends
# =============================================================================

class TestQueueTrends:

    async def test_trends_returns_200(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/trends?days_back=1&bucket_minutes=60",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        assert response.status_code == 200

    async def test_trends_returns_buckets(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        """Trend response has time buckets."""
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/trends",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        data = response.json()["data"]
        assert "buckets" in data
        assert "bucket_minutes" in data
        # We seeded data within the last hour → should have ≥1 bucket
        assert len(data["buckets"]) >= 1

    async def test_invalid_bucket_minutes_returns_400(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        """Invalid bucket_minutes value returns 400."""
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/trends?bucket_minutes=45",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        assert response.status_code == 400


# =============================================================================
# Test: GET /api/v1/analytics/stores/{store_id}/counters
# =============================================================================

class TestCounterComparison:

    async def test_comparison_returns_200(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/counters",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        assert response.status_code == 200

    async def test_comparison_has_ranked_counters(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        """Counter comparison includes ranked counters with required fields."""
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/counters",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        data = response.json()["data"]
        assert "counters" in data
        assert len(data["counters"]) >= 1
        counter = data["counters"][0]
        assert "efficiency_rank" in counter
        assert counter["efficiency_rank"] == 1  # Best performer is rank 1

    async def test_comparison_rank_starts_at_1(
        self,
        client: AsyncClient,
        analytics_setup: dict,
    ) -> None:
        """Efficiency ranks start at 1, not 0."""
        response = await client.get(
            f"/api/v1/analytics/stores/{analytics_setup['store_id']}/counters",
            headers={"Authorization": f"Bearer {analytics_setup['mgr_token']}"},
        )
        counters = response.json()["data"]["counters"]
        ranks = [c["efficiency_rank"] for c in counters]
        assert min(ranks) == 1
