"""
RetailFlow AI — Test: Health Check

Simple smoke test to verify the FastAPI app is configured correctly
and the /health endpoint returns expected responses.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestHealthCheck:
    """Tests for the /health endpoint."""

    async def test_health_check_returns_200(self, client: AsyncClient) -> None:
        """Health endpoint should return HTTP 200."""
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_health_check_returns_correct_body(self, client: AsyncClient) -> None:
        """Health endpoint should return expected JSON structure."""
        response = await client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
        assert data["service"] == "retailflow-ai-backend"

    async def test_nonexistent_route_returns_404(self, client: AsyncClient) -> None:
        """Non-existent routes should return 404."""
        response = await client.get("/api/v1/nonexistent")
        assert response.status_code == 404
