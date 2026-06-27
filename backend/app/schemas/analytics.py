"""
RetailFlow AI — Analytics Pydantic Schemas

All response schemas for the analytics dashboard.

Design Principle:
    Analytics responses are read-heavy and cache-friendly.
    They are NOT ORM models — they are assembled from raw SQL aggregations.
    Pydantic BaseModel (not from_attributes) is used for explicit field mapping.

Data Freshness:
    - Summary / Counter Comparison: 5-minute cache (near real-time)
    - Peak Hours Heatmap: 1-hour cache (changes slowly)
    - Trends: 5-minute cache (live data for charts)
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# Store Summary
# =============================================================================

class StoreSummaryAnalytics(BaseModel):
    """
    High-level KPI summary for a store over a given time period.

    Displayed as metric cards at the top of the analytics dashboard.
    """

    store_id: str
    store_name: str
    period_from: datetime
    period_to: datetime

    # Volume Metrics
    total_snapshots: int = Field(
        description="Total queue readings recorded in the period"
    )
    total_customers_estimated: int = Field(
        description="Sum of all queue_length values — approximate throughput indicator"
    )

    # Queue Metrics
    avg_queue_length: float = Field(
        description="Average queue length across all counters in the period"
    )
    peak_queue_length: int = Field(
        description="Highest recorded queue length in the period"
    )

    # Wait Time Metrics
    avg_wait_seconds: Optional[float] = Field(
        default=None,
        description="Average estimated wait time in seconds (None if no EWT data)"
    )
    avg_wait_formatted: str = Field(
        description="Human-readable average wait (e.g., '~4 min')"
    )
    peak_wait_seconds: Optional[int] = Field(
        default=None,
        description="Highest recorded estimated wait time in seconds"
    )

    # Insights
    busiest_hour: Optional[int] = Field(
        default=None,
        description="Hour of day (0-23) with the highest average queue in the period"
    )
    busiest_day_of_week: Optional[str] = Field(
        default=None,
        description="Day name (e.g., 'Saturday') with the highest average queue"
    )
    active_counters: int = Field(
        description="Number of counters that had at least one update in the period"
    )

    # Cache info
    cached: bool = Field(
        default=False,
        description="True if this response was served from cache"
    )


# =============================================================================
# Peak Hours Heatmap
# =============================================================================

class HeatmapCell(BaseModel):
    """
    A single cell in the peak hours heatmap.

    The heatmap is a 7 × 24 grid (day-of-week × hour-of-day).
    Each cell contains the average queue length for that combination.
    """

    day_of_week: int = Field(
        description="0=Sunday, 1=Monday, ..., 6=Saturday (PostgreSQL EXTRACT(dow))",
        ge=0,
        le=6,
    )
    day_name: str = Field(
        description="Human-readable day name (e.g., 'Monday')"
    )
    hour_of_day: int = Field(
        description="Hour (0-23) in 24-hour format",
        ge=0,
        le=23,
    )
    avg_queue_length: float = Field(
        description="Average queue length for this time slot"
    )
    sample_count: int = Field(
        description="Number of snapshots contributing to this average"
    )
    intensity: float = Field(
        description="Normalized intensity 0.0–1.0 for heatmap color scale"
    )


class PeakHoursHeatmap(BaseModel):
    """Full heatmap response."""

    store_id: str
    store_name: str
    days_back: int
    cells: list[HeatmapCell]
    max_avg_queue: float = Field(
        description="Maximum avg_queue_length in the heatmap (used to normalize intensity)"
    )
    cached: bool = False


# =============================================================================
# Queue Trends
# =============================================================================

class TrendBucket(BaseModel):
    """
    A single time bucket in the queue trend line chart.

    Buckets are typically 1 hour wide.
    Multiple counters are included per bucket for comparison charting.
    """

    bucket_time: datetime = Field(
        description="Start of the time bucket (UTC, truncated to bucket_minutes)"
    )
    counter_id: Optional[str] = Field(
        default=None,
        description="Counter UUID, or None if aggregated across all counters"
    )
    counter_number: Optional[int] = None
    avg_queue_length: float
    max_queue_length: int
    sample_count: int


class QueueTrendsResponse(BaseModel):
    """Trend data for line/area charts."""

    store_id: str
    store_name: str
    from_dt: datetime
    to_dt: datetime
    bucket_minutes: int = Field(
        description="Width of each time bucket in minutes (60 = hourly)"
    )
    buckets: list[TrendBucket]
    cached: bool = False


# =============================================================================
# Counter Comparison
# =============================================================================

class CounterStats(BaseModel):
    """
    Performance statistics for a single counter.

    Used in the counter comparison table on the analytics dashboard.
    Allows managers to identify underperforming counters.
    """

    counter_id: str
    counter_number: int
    label: Optional[str] = None
    avg_queue_length: float = Field(
        description="Average queue length during the period"
    )
    peak_queue_length: int = Field(
        description="Highest recorded queue length"
    )
    avg_wait_seconds: Optional[float] = Field(
        default=None,
        description="Average EWT during the period"
    )
    avg_wait_formatted: str
    total_updates: int = Field(
        description="Total manual/CV updates received (proxy for how active this counter was)"
    )
    efficiency_rank: int = Field(
        description="Rank by avg_queue_length (1 = shortest queues = most efficient)"
    )


class CounterComparisonResponse(BaseModel):
    """Counter comparison table response."""

    store_id: str
    store_name: str
    period_from: datetime
    period_to: datetime
    counters: list[CounterStats]
    cached: bool = False
