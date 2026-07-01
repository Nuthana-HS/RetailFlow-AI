"""
RetailFlow AI — Notification ORM Model

Stores in-app and email notifications generated when alert thresholds are crossed.

Relationship:
    AlertConfig  (1) → (many) Notification
    User         (1) → (many) Notification  (recipient)

Lifecycle:
    1. Queue update triggers alert check (_check_alerts in queue_service.py)
    2. Threshold exceeded → NotificationService creates Notification rows
    3. Manager sees unread count in dashboard badge
    4. Manager opens inbox → reads notifications (is_read = True)

Email delivery:
    email_sent = True  → SMTP email was dispatched (may still bounce in delivery)
    email_sent = False → Email not attempted (SMTP not configured or disabled)
    email_failed = True → SMTP delivery attempt failed
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Notification(Base):
    """
    An in-app (and optionally email) alert notification for a manager.

    One notification record is created PER MANAGER who has access to the
    triggered store. This ensures each manager has their own read/unread state.
    """

    __tablename__ = "notifications"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Context: which alert fired
    alert_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    counter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counters.id", ondelete="SET NULL"),
        nullable=True,
        comment="Which counter triggered this alert. NULL = store-level alert.",
    )

    # Recipient
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Manager who receives this notification",
    )

    # Notification Content
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Short headline: 'Queue Alert: Counter #2 has 12 customers'",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full alert message with store name, counter, and action suggestion",
    )

    # Trigger Context (for detailed view)
    trigger_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="The metric value that triggered the alert (queue_length or wait_seconds)",
    )
    threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="The configured threshold that was exceeded",
    )
    alert_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="queue_length or wait_time",
    )

    # Delivery State
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True when manager has opened/acknowledged this notification",
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    email_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    email_failed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Notification user={self.user_id} store={self.store_id} "
            f"read={self.is_read} '{self.title[:40]}'>"
        )
