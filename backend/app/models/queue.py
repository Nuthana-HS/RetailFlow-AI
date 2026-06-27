"""
RetailFlow AI — SQLAlchemy ORM Models: QueueSnapshot & AlertConfig

Two models supporting the Queue Engine:

QueueSnapshot:
    Time-series record written every time a counter's queue length is updated.
    Used by:
      - Analytics (Phase 6): peak hour charts, daily trends
      - ML Training (Phase 9): XGBoost training data
      - Historical view: replay queue states over time

AlertConfig:
    Configurable thresholds that trigger notifications when queue length
    or wait time exceeds a defined limit.
    Scope:
      - Store-level: counter_id IS NULL → applies to all counters in store
      - Counter-level: counter_id IS NOT NULL → specific counter only

Data Volume Note:
    QueueSnapshots are high-frequency writes (~1 per counter per 5 seconds).
    A store with 10 counters generates 120 rows/minute → 172,800 rows/day.
    Plan: Partition by month in Phase 9 or use TimescaleDB for production scale.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.store import Counter, Store  # noqa: F401


# =============================================================================
# Enums
# =============================================================================

class QueueUpdateSource(str, enum.Enum):
    """
    Indicates who or what updated the queue state.

    CV:         Computer Vision (YOLOv8) — Phase 8
    MANUAL:     Manager override via the dashboard
    SIMULATION: Synthetic data for testing/demo
    ML:         Predicted value from XGBoost — Phase 9
    """
    CV = "cv"
    MANUAL = "manual"
    SIMULATION = "simulation"
    ML = "ml"


class AlertType(str, enum.Enum):
    """
    What metric triggers the alert.

    QUEUE_LENGTH: Alert when customer count >= threshold
    WAIT_TIME:    Alert when estimated wait (seconds) >= threshold
    """
    QUEUE_LENGTH = "queue_length"
    WAIT_TIME = "wait_time"


# =============================================================================
# QueueSnapshot Model
# =============================================================================

class QueueSnapshot(Base):
    """
    Immutable time-series record of a counter's queue state at a point in time.

    Write pattern: append-only (never updated or deleted in normal operation).
    Read pattern: time-range queries with counter_id or store_id filter.

    Future optimization: Partition by recorded_at month.
    """

    __tablename__ = "queue_snapshots"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Context
    counter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counters.id", ondelete="SET NULL"),
        nullable=True,  # SET NULL if counter deleted (preserves snapshot value)
        index=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Measurements
    queue_length: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of customers waiting at this counter at recorded_at",
    )
    estimated_wait_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Predicted wait time in seconds (NULL if ML not available)",
    )
    people_served: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Customers served since last snapshot (for throughput analytics)",
    )

    # Provenance
    source: Mapped[QueueUpdateSource] = mapped_column(
        Enum(QueueUpdateSource, name="queue_update_source"),
        nullable=False,
        default=QueueUpdateSource.MANUAL,
        comment="What triggered this snapshot (cv | manual | simulation | ml)",
    )

    # Timestamp
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="When this snapshot was recorded (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<QueueSnapshot counter={self.counter_id} "
            f"length={self.queue_length} at={self.recorded_at}>"
        )


# =============================================================================
# AlertConfig Model
# =============================================================================

class AlertConfig(Base):
    """
    Configurable threshold for triggering queue alerts.

    Scope:
        counter_id IS NULL  → Store-level alert (applies to all counters)
        counter_id NOT NULL → Counter-specific alert (overrides store-level)

    Cooldown:
        After an alert fires, no new alert for the same config is sent
        within cooldown_minutes. This prevents alert spam.
    """

    __tablename__ = "alert_configs"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Scope
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    counter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counters.id", ondelete="CASCADE"),
        nullable=True,
        comment="NULL = store-wide alert. NOT NULL = counter-specific.",
    )

    # Threshold Configuration
    alert_type: Mapped[AlertType] = mapped_column(
        Enum(AlertType, name="alert_type"),
        nullable=False,
        default=AlertType.QUEUE_LENGTH,
    )
    threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Alert triggers when metric >= threshold",
    )
    cooldown_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment="Min minutes between alert notifications for this config",
    )

    # State
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this alert last fired (used for cooldown enforcement)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        scope = f"counter={self.counter_id}" if self.counter_id else f"store={self.store_id}"
        return f"<AlertConfig {scope} type={self.alert_type} threshold={self.threshold}>"
