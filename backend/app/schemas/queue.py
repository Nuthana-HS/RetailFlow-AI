"""
RetailFlow AI — Queue Engine Pydantic Schemas

Three categories of schemas:
  1. Request schemas: queue updates, alert config
  2. State schemas: real-time counter/store queue state (from Redis)
  3. Response schemas: snapshots history, alert configurations
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.queue import AlertType, QueueUpdateSource
from app.models.store import CounterStatus


# =============================================================================
# Request Schemas
# =============================================================================

class QueueUpdateRequest(BaseModel):
    """
    Request body for POST /api/v1/queues/counters/{id}/update

    Used by managers to manually set the queue length for a counter.
    Also used by the simulation endpoint for demo purposes.
    """

    queue_length: int = Field(
        ...,
        ge=0,
        le=999,
        description="Current number of customers waiting (0 = empty queue)",
        examples=[7],
    )
    source: Literal["manual", "simulation"] = Field(
        default="manual",
        description="Update source: 'manual' (manager) or 'simulation' (demo)",
    )
    note: str | None = Field(
        default=None,
        max_length=255,
        description="Optional manager note for the audit log",
    )


class AlertConfigRequest(BaseModel):
    """
    Request body for POST/PATCH alert config endpoints.

    Scope:
        counter_id = None → store-wide alert
        counter_id = UUID → counter-specific alert
    """

    alert_type: AlertType = Field(
        default=AlertType.QUEUE_LENGTH,
        description="What triggers the alert: 'queue_length' or 'wait_time'",
    )
    threshold: int = Field(
        ...,
        ge=1,
        le=100,
        description="Alert fires when metric >= threshold",
        examples=[8],
    )
    counter_id: uuid.UUID | None = Field(
        default=None,
        description="Target counter UUID. NULL = applies to all counters in store.",
    )
    cooldown_minutes: int = Field(
        default=30,
        ge=5,
        le=480,
        description="Minimum minutes between alerts for this config (5–480)",
    )
    is_active: bool = Field(
        default=True,
        description="Enable or disable this alert without deleting it",
    )


# =============================================================================
# Real-Time State Schemas (built from Redis)
# =============================================================================

class CounterQueueState(BaseModel):
    """
    Real-time queue state for a single counter.

    This is built from Redis — it's the hot path read by the dashboard.
    NOT a database record (that's QueueSnapshot).
    """

    counter_id: uuid.UUID
    counter_number: int
    label: str | None
    status: CounterStatus
    queue_length: int = Field(description="Current customers waiting")
    estimated_wait_seconds: int | None = Field(
        description="EWT in seconds (from ML or fallback formula)"
    )
    estimated_wait_formatted: str = Field(
        description="Human-readable EWT (e.g., '~8 min')"
    )
    last_updated: datetime | None
    source: QueueUpdateSource | None

    model_config = {"use_enum_values": True}


class StoreQueueState(BaseModel):
    """
    Aggregated real-time queue state for an entire store.

    This is the primary data structure returned by the dashboard endpoint.
    Built by aggregating CounterQueueState objects from Redis.
    """

    store_id: uuid.UUID
    store_name: str
    total_customers_waiting: int = Field(
        description="Sum of queue_length across all open counters"
    )
    open_counters: int = Field(
        description="Number of counters with status=open"
    )
    avg_wait_seconds: int | None = Field(
        description="Average EWT across open counters (None if no open counters)"
    )
    avg_wait_formatted: str = Field(
        description="Human-readable average EWT"
    )
    alert_active: bool = Field(
        default=False,
        description="True if any counter has exceeded alert threshold",
    )
    counters: list[CounterQueueState]
    last_updated: datetime | None


# =============================================================================
# History / Analytics Schemas
# =============================================================================

class QueueSnapshotResponse(BaseModel):
    """Single queue snapshot record returned from history endpoint."""

    id: uuid.UUID
    counter_id: uuid.UUID | None
    store_id: uuid.UUID
    queue_length: int
    estimated_wait_seconds: int | None
    source: QueueUpdateSource
    recorded_at: datetime

    model_config = {"from_attributes": True, "use_enum_values": True}


class QueueHistoryResponse(BaseModel):
    """Paginated queue history for analytics."""

    snapshots: list[QueueSnapshotResponse]
    total: int
    page: int
    limit: int


# =============================================================================
# Alert Config Schemas
# =============================================================================

class AlertConfigResponse(BaseModel):
    """Alert configuration returned in API responses."""

    id: uuid.UUID
    store_id: uuid.UUID
    counter_id: uuid.UUID | None
    alert_type: AlertType
    threshold: int
    cooldown_minutes: int
    is_active: bool
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "use_enum_values": True}


# =============================================================================
# WebSocket Event Schemas (used by Phase 7)
# =============================================================================

class QueueUpdateEvent(BaseModel):
    """
    Event payload published to Redis Pub/Sub and forwarded to WebSocket clients.

    Phase 7 (WebSocket) subscribes to Redis channel:
        queue:events:store:{store_id}

    And broadcasts this JSON to all connected dashboard clients.
    """

    event_type: Literal["queue_update", "counter_status", "alert"] = "queue_update"
    store_id: str
    counter_id: str
    queue_length: int
    estimated_wait_seconds: int | None
    counter_number: int
    status: str
    timestamp: str  # ISO 8601 UTC
    source: str
