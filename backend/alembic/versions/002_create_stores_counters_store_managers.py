"""Create stores, counters, and store_managers tables

Revision ID: 002
Revises: 001
Create Date: 2026-06-27 00:00:00.000000

Description:
    Store management schema for Phase 4.

    Creates:
        - stores table: Physical store locations with operating hours
        - store_managers table: Manager-to-store assignment (many-to-many)
        - counters table: Billing counters with soft-delete support

    Indexes created:
        - idx_stores_admin_id: Fetch stores by owner
        - idx_stores_city: Filter stores by city
        - idx_counters_store_id: Fetch all counters for a store
        - idx_counters_status: Filter by open/closed/break
        - idx_counters_is_deleted: Exclude soft-deleted counters
        - idx_store_managers_user_id: Fetch all stores for a manager

    Constraints:
        - uq_store_managers_store_user: Manager can only be assigned once per store
        - uq_counters_store_number: Counter numbers unique per store
        - fk_stores_admin_id: References users.id (RESTRICT — can't delete admin with stores)
        - fk_counters_store_id: References stores.id (CASCADE)
        - fk_counters_cashier_id: References users.id (SET NULL)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stores, store_managers, and counters tables."""

    # -------------------------------------------------------------------------
    # Create counter_status enum type
    # -------------------------------------------------------------------------
    counter_status_enum = postgresql.ENUM(
        "open", "closed", "break",
        name="counter_status",
        create_type=True,
    )
    counter_status_enum.create(op.get_bind(), checkfirst=True)

    # -------------------------------------------------------------------------
    # Create stores table
    # -------------------------------------------------------------------------
    op.create_table(
        "stores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text, nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("zip_code", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column(
            "admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "open_time",
            sa.Time,
            nullable=False,
            server_default="09:00:00",
        ),
        sa.Column(
            "close_time",
            sa.Time,
            nullable=False,
            server_default="22:00:00",
        ),
        sa.Column(
            "avg_service_time",
            sa.Integer,
            nullable=False,
            server_default="180",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index("idx_stores_admin_id", "stores", ["admin_id"])
    op.create_index("idx_stores_city", "stores", ["city"])
    op.create_index(
        "idx_stores_active",
        "stores",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # -------------------------------------------------------------------------
    # Create store_managers table
    # -------------------------------------------------------------------------
    op.create_table(
        "store_managers",
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "store_id",
            "user_id",
            name="uq_store_managers_store_user",
        ),
    )

    op.create_index("idx_store_managers_user_id", "store_managers", ["user_id"])
    op.create_index("idx_store_managers_store_id", "store_managers", ["store_id"])

    # -------------------------------------------------------------------------
    # Create counters table
    # -------------------------------------------------------------------------
    op.create_table(
        "counters",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("counter_number", sa.Integer, nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column(
            "cashier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum("open", "closed", "break", name="counter_status"),
            nullable=False,
            server_default="closed",
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "store_id",
            "counter_number",
            name="uq_counters_store_number",
        ),
    )

    op.create_index("idx_counters_store_id", "counters", ["store_id"])
    op.create_index("idx_counters_status", "counters", ["status"])
    op.create_index(
        "idx_counters_active",
        "counters",
        ["is_deleted"],
        postgresql_where=sa.text("is_deleted = false"),  # Partial — only active counters
    )
    op.create_index(
        "idx_counters_open",
        "counters",
        ["store_id", "status"],
        postgresql_where=sa.text("is_deleted = false AND status = 'open'"),
    )


def downgrade() -> None:
    """Drop counters, store_managers, and stores tables."""
    op.drop_table("counters")
    op.drop_table("store_managers")
    op.drop_table("stores")

    postgresql.ENUM(name="counter_status").drop(op.get_bind(), checkfirst=True)
