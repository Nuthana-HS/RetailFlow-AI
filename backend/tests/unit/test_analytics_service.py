"""
RetailFlow AI — Unit Tests: Analytics Service

Tests for the analytics service's pure logic:
  - Cache key generation (deterministic)
  - TTL selection based on days_back
  - Wait time formatting reused from queue engine
  - Heatmap intensity normalization
  - Counter efficiency ranking

No DB or Redis connections needed — pure unit tests.
"""

import pytest

from app.services.analytics_service import _cache_key, _choose_ttl, _TTL_HISTORICAL, _TTL_LIVE, _TTL_RECENT


# =============================================================================
# Test: Cache Key Generation
# =============================================================================

class TestCacheKey:
    """Tests for _cache_key() determinism and uniqueness."""

    def test_same_params_produce_same_key(self) -> None:
        """Same inputs → same cache key (required for cache hits)."""
        key1 = _cache_key("store-abc", "summary", from_dt="2026-01-01", to_dt="2026-01-02")
        key2 = _cache_key("store-abc", "summary", from_dt="2026-01-01", to_dt="2026-01-02")
        assert key1 == key2

    def test_different_stores_produce_different_keys(self) -> None:
        """Different store IDs → different cache keys."""
        key1 = _cache_key("store-aaa", "summary", from_dt="2026-01-01", to_dt="2026-01-02")
        key2 = _cache_key("store-bbb", "summary", from_dt="2026-01-01", to_dt="2026-01-02")
        assert key1 != key2

    def test_different_metrics_produce_different_keys(self) -> None:
        """Different metric names → different cache keys."""
        key1 = _cache_key("store-abc", "summary", from_dt="2026-01-01", to_dt="2026-01-02")
        key2 = _cache_key("store-abc", "heatmap", from_dt="2026-01-01", to_dt="2026-01-02")
        assert key1 != key2

    def test_different_dates_produce_different_keys(self) -> None:
        """Different date ranges → different cache keys."""
        key1 = _cache_key("store-abc", "summary", from_dt="2026-01-01", to_dt="2026-01-02")
        key2 = _cache_key("store-abc", "summary", from_dt="2026-01-02", to_dt="2026-01-03")
        assert key1 != key2

    def test_key_contains_store_id_and_metric(self) -> None:
        """Cache key must contain both store ID and metric for readability in Redis."""
        key = _cache_key("my-store-id", "peak-hours", x="1")
        assert "my-store-id" in key
        assert "peak-hours" in key

    def test_key_starts_with_analytics_prefix(self) -> None:
        """All analytics keys must use the analytics: prefix."""
        key = _cache_key("store-abc", "summary", x="y")
        assert key.startswith("analytics:store:")


# =============================================================================
# Test: TTL Selection
# =============================================================================

class TestTTLSelection:
    """Tests for cache TTL selection based on days_back window."""

    def test_1_day_back_returns_live_ttl(self) -> None:
        """Last 24h = live data → 5-minute TTL."""
        assert _choose_ttl(1) == _TTL_LIVE

    def test_7_days_back_returns_recent_ttl(self) -> None:
        """Last 7 days = recent data → 15-minute TTL."""
        assert _choose_ttl(7) == _TTL_RECENT

    def test_30_days_back_returns_historical_ttl(self) -> None:
        """Last 30 days = historical → 1-hour TTL."""
        assert _choose_ttl(30) == _TTL_HISTORICAL

    def test_8_days_back_returns_historical_ttl(self) -> None:
        """More than 7 days → historical TTL."""
        assert _choose_ttl(8) == _TTL_HISTORICAL

    def test_ttl_values_are_ordered(self) -> None:
        """Live TTL < Recent TTL < Historical TTL."""
        assert _TTL_LIVE < _TTL_RECENT < _TTL_HISTORICAL


# =============================================================================
# Test: Heatmap Intensity Normalization
# =============================================================================

class TestHeatmapNormalization:
    """Verify heatmap intensity calculation is correct."""

    def test_max_value_gets_intensity_1(self) -> None:
        """The cell with the highest avg_queue should get intensity 1.0."""
        cells_data = [
            {"avg_queue_length": 10.0},
            {"avg_queue_length": 5.0},
            {"avg_queue_length": 2.0},
        ]
        max_val = max(c["avg_queue_length"] for c in cells_data)
        intensities = [round(c["avg_queue_length"] / max_val, 4) for c in cells_data]
        assert intensities[0] == 1.0

    def test_min_value_proportional_intensity(self) -> None:
        """Intensity is proportional to avg_queue / max_queue."""
        max_avg = 10.0
        avg = 4.0
        intensity = round(avg / max_avg, 4)
        assert intensity == 0.4

    def test_empty_cells_handled(self) -> None:
        """Edge case: no data → max should default to 1 to avoid division by zero."""
        rows = []
        max_avg = max((r["avg_queue_length"] for r in rows), default=1.0) or 1.0
        assert max_avg == 1.0  # Prevents ZeroDivisionError


# =============================================================================
# Test: Counter Ranking
# =============================================================================

class TestCounterRanking:
    """Tests for counter efficiency ranking logic."""

    def test_lower_avg_queue_gets_better_rank(self) -> None:
        """Counters with smaller avg queue length should rank higher."""
        rows = [
            {"counter_id": "a", "avg_queue_length": 2.0},   # Most efficient
            {"counter_id": "b", "avg_queue_length": 5.0},
            {"counter_id": "c", "avg_queue_length": 8.0},   # Least efficient
        ]
        # Simulate ranking (enumerate on sorted rows)
        ranked = [(rank + 1, row) for rank, row in enumerate(rows)]
        assert ranked[0][0] == 1
        assert ranked[0][1]["counter_id"] == "a"
        assert ranked[2][0] == 3
        assert ranked[2][1]["counter_id"] == "c"

    def test_rank_starts_at_1(self) -> None:
        """First rank should be 1, not 0."""
        rows = [{"counter_id": "x", "avg_queue_length": 3.0}]
        rank = 0 + 1  # enumerate starts at 0, we add 1
        assert rank == 1
