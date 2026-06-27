"""
RetailFlow AI — SQLAlchemy ORM Models: Store, Counter, StoreManager

Models for the store management system.

Relationships:
    Store ──< Counter            (one store has many counters)
    Store ──< StoreManager >── User  (many-to-many: stores ↔ managers)
    User (admin) ──< Store       (one admin owns many stores)
    User (cashier) ──o Counter   (optional: one cashier per open counter)

Design Notes:
    - Store is the top-level entity; everything else references it
    - Counters are soft-deleted (is_deleted=True) to preserve queue history
    - StoreManager is a full model (not just many-to-many) to capture assigned_at
    - CounterStatus is a string enum for readability in the database
"""

import enum
import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import User  # noqa: F401 — imported so Alembic sees the FK target


# =============================================================================
# Enums
# =============================================================================

class CounterStatus(str, enum.Enum):
    """
    Operational status of a billing counter.

    State Machine:
        Closed → Open  (manager opens counter, assigns cashier)
        Open → Break   (cashier on break)
        Open → Closed  (manager closes counter)
        Break → Open   (break ends)
        Break → Closed (counter closed while on break)
    """
    OPEN = "open"
    CLOSED = "closed"
    BREAK = "break"


# =============================================================================
# Store Model
# =============================================================================

class Store(Base):
    """
    Represents a physical retail store location.

    Each store is administered by one admin user and can have
    multiple managers assigned via the StoreManager association.
    """

    __tablename__ = "stores"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Store Identity
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name of the store (e.g., 'D-Mart Andheri West')",
    )
    address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Street address of the store",
    )
    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    state: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    zip_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Ownership
    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),  # Don't delete store if admin deleted
        nullable=False,
        index=True,
    )

    # Operating Hours
    open_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        server_default="09:00:00",
        comment="Daily opening time (store's local timezone)",
    )
    close_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        server_default="22:00:00",
        comment="Daily closing time",
    )

    # Queue Engine Settings
    avg_service_time: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=180,
        comment="Average seconds per customer (used for EWT when ML unavailable)",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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

    # Relationships
    counters: Mapped[list["Counter"]] = relationship(
        "Counter",
        back_populates="store",
        cascade="all, delete-orphan",
        lazy="select",
        primaryjoin="and_(Counter.store_id == Store.id, Counter.is_deleted == False)",
    )
    manager_associations: Mapped[list["StoreManager"]] = relationship(
        "StoreManager",
        back_populates="store",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Store id={self.id} name={self.name!r} city={self.city!r}>"


# =============================================================================
# StoreManager Model (Association Table with metadata)
# =============================================================================

class StoreManager(Base):
    """
    Associates managers (users with role=manager) to specific stores.

    This is NOT a simple many-to-many join table because we need:
    - The `assigned_at` timestamp for audit purposes
    - The ability to query "which stores does manager X manage?"
    - The ability to check if a manager has access to a given store

    Access Control Rule:
        A manager can only perform operations on stores where
        a StoreManager record exists with their user_id.
    """

    __tablename__ = "store_managers"
    __table_args__ = (
        UniqueConstraint("store_id", "user_id", name="uq_store_managers_store_user"),
    )

    # Composite Primary Key
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    store: Mapped[Store] = relationship("Store", back_populates="manager_associations")

    def __repr__(self) -> str:
        return f"<StoreManager store_id={self.store_id} user_id={self.user_id}>"


# =============================================================================
# Counter Model
# =============================================================================

class Counter(Base):
    """
    Represents a billing counter (checkout lane) within a store.

    Counters are SOFT-DELETED (is_deleted=True) rather than hard-deleted
    because queue_snapshots reference counter_ids. Deleting a counter
    would orphan historical data needed for analytics and ML training.

    The unique constraint (store_id, counter_number) is enforced only on
    non-deleted counters — a deleted counter's number can be reused.
    """

    __tablename__ = "counters"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "counter_number",
            name="uq_counters_store_number",
        ),
    )

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Store Association
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Counter Identity
    counter_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Display number shown to customers (e.g., Counter 3)",
    )
    label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Optional friendly label (e.g., 'Express Lane', 'Customer Service')",
    )

    # Staff Assignment
    cashier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="The cashier currently assigned to this counter (NULL if unassigned)",
    )

    # Operational State
    status: Mapped[CounterStatus] = mapped_column(
        Enum(CounterStatus, name="counter_status"),
        nullable=False,
        default=CounterStatus.CLOSED,
        index=True,
    )

    # Soft Delete
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="True = counter has been removed (soft delete to preserve history)",
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

    # Relationships
    store: Mapped[Store] = relationship(
        "Store",
        back_populates="counters",
        primaryjoin="and_(Counter.store_id == Store.id, Counter.is_deleted == False)",
    )

    def __repr__(self) -> str:
        return (
            f"<Counter id={self.id} store_id={self.store_id} "
            f"number={self.counter_number} status={self.status}>"
        )
