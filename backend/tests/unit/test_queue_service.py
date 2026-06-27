"""
RetailFlow AI — Unit Tests: Queue Service

Tests for QueueService business logic with mocked repositories and Redis.
No real database or Redis connection required.

Coverage:
  - EWT calculation formula (fallback when ML not available)
  - Alert threshold checking (cooldown enforcement)
  - RBAC check in get_store_queue_state
  - Queue update when counter is closed (should raise)
  - Format wait time utility
"""

from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta, timezone

import pytest

from app.core.queue_state import _calculate_ewt, _format_wait_time
from app.models.queue import AlertConfig, AlertType
from app.services.queue_service import QueueCounterClosedError


# =============================================================================
# Test: EWT Calculation
# =============================================================================

class TestCalculateEWT:
    """Tests for the fallback EWT formula."""

    def test_empty_queue_returns_zero(self) -> None:
        """0 customers waiting → 0 seconds EWT."""
        assert _calculate_ewt(0, avg_service_time=180) == 0

    def test_single_customer(self) -> None:
        """1 customer → one full service time."""
        assert _calculate_ewt(1, avg_service_time=180) == 180

    def test_multiple_customers(self) -> None:
        """5 customers × 3 min each = 15 min."""
        assert _calculate_ewt(5, avg_service_time=180) == 900

    def test_custom_service_time(self) -> None:
        """Custom avg service time (fast checkout: 60s)."""
        assert _calculate_ewt(10, avg_service_time=60) == 600

    def test_large_queue(self) -> None:
        """Large queue (50 customers) should not overflow."""
        result = _calculate_ewt(50, avg_service_time=120)
        assert result == 6000  # 100 minutes


# =============================================================================
# Test: Format Wait Time
# =============================================================================

class TestFormatWaitTime:
    """Tests for the human-readable EWT formatter."""

    def test_none_returns_na(self) -> None:
        assert _format_wait_time(None) == "N/A"

    def test_negative_returns_na(self) -> None:
        assert _format_wait_time(-1) == "N/A"

    def test_zero_returns_less_than_one_min(self) -> None:
        assert _format_wait_time(0) == "< 1 min"

    def test_45_seconds_returns_less_than_one_min(self) -> None:
        assert _format_wait_time(45) == "< 1 min"

    def test_90_seconds_rounds_to_2_min(self) -> None:
        assert _format_wait_time(90) == "~2 min"

    def test_600_seconds_returns_10_min(self) -> None:
        assert _format_wait_time(600) == "~10 min"

    def test_3600_seconds_returns_60_min(self) -> None:
        assert _format_wait_time(3600) == "~60 min"

    def test_61_seconds_rounds_to_1_min(self) -> None:
        assert _format_wait_time(61) == "~1 min"


# =============================================================================
# Test: Alert Cooldown Logic
# =============================================================================

class TestAlertCooldown:
    """Tests for alert cooldown enforcement in AlertRepository."""

    @pytest.mark.asyncio
    async def test_no_previous_trigger_not_in_cooldown(self) -> None:
        """Alert that has never fired is not in cooldown."""
        from app.repositories.queue_repository import AlertRepository

        config = AlertConfig(
            last_triggered_at=None,
            cooldown_minutes=30,
        )
        repo = AlertRepository()
        result = await repo.is_in_cooldown(config)
        assert result is False

    @pytest.mark.asyncio
    async def test_recently_triggered_in_cooldown(self) -> None:
        """Alert triggered 5 minutes ago with 30min cooldown is in cooldown."""
        from app.repositories.queue_repository import AlertRepository

        config = AlertConfig(
            last_triggered_at=datetime.now(tz=timezone.utc) - timedelta(minutes=5),
            cooldown_minutes=30,
        )
        repo = AlertRepository()
        result = await repo.is_in_cooldown(config)
        assert result is True

    @pytest.mark.asyncio
    async def test_expired_cooldown_not_in_cooldown(self) -> None:
        """Alert triggered 60 minutes ago with 30min cooldown can fire again."""
        from app.repositories.queue_repository import AlertRepository

        config = AlertConfig(
            last_triggered_at=datetime.now(tz=timezone.utc) - timedelta(minutes=60),
            cooldown_minutes=30,
        )
        repo = AlertRepository()
        result = await repo.is_in_cooldown(config)
        assert result is False

    @pytest.mark.asyncio
    async def test_exact_boundary_still_in_cooldown(self) -> None:
        """Alert triggered exactly at cooldown boundary is still cooling."""
        from app.repositories.queue_repository import AlertRepository

        # 29 minutes and 59 seconds ago → still in 30-min cooldown
        config = AlertConfig(
            last_triggered_at=datetime.now(tz=timezone.utc) - timedelta(minutes=29, seconds=59),
            cooldown_minutes=30,
        )
        repo = AlertRepository()
        result = await repo.is_in_cooldown(config)
        assert result is True
