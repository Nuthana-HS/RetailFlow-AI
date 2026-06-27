"""Create queue_snapshots and alert_configs tables

Revision ID: 003
Revises: 002
Create Date: 2026-06-27 00:00:00.000000

Description:
    Queue Engine schema for Phase 5.

    Creates:
        - queue_snapshots: High-frequency time-series records per counter
        - alert_configs: Configurable alert thresholds (store or counter scope)

    New enum types:
        - queue_update_source: cv | manual | simulation | ml
        - alert_type: queue_length | wait_time

    Indexes:
        - idx_snapshots_counter_time: Time-series query by counter
        - idx_snapshots_store_time: Time-series query by store
        - idx_snapshots_recorded_at: General time-range queries
        - idx_alerts_store_id: Fetch all alerts for a store
        - idx_alerts_active: Filter active alerts (partial index)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # -------------------------------------------------------------------------
    # Create enum types
    # -------------------------------------------------------------------------
    queue_update_source_enum = postgresql.ENUM(
        "cv", "manual", "simulation", "ml",
        name="queue_update_source",
        create_type=True,
    )
    queue_update_source_enum.create(op.get_bind(), checkfirst=True)

    alert_type_enum = postgresql.ENUM(
        "queue_length", "wait_time",
        name="alert_type",
        create_type=True,
    )
    alert_type_enum.create(op.get_bind(), checkfirst=True)

    # -------------------------------------------------------------------------
    # Create queue_snapshots table
    # -------------------------------------------------------------------------
    op.create_table(
        "queue_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "counter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("counters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("queue_length", sa.Integer, nullable=False),
        sa.Column("estimated_wait_seconds", sa.Integer, nullable=True),
        sa.Column("people_served", sa.Integer, nullable=True),
        sa.Column(
            "source",
            sa.Enum("cv", "manual", "simulation", "ml", name="queue_update_source"),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Composite index: the primary analytics query pattern
    op.create_index(
        "idx_snapshots_counter_time",
        "queue_snapshots",
        ["counter_id", "recorded_at"],
    )
    op.create_index(
        "idx_snapshots_store_time",
        "queue_snapshots",
        ["store_id", "recorded_at"],
    )
    op.create_index(
        "idx_snapshots_recorded_at",
        "queue_snapshots",
        ["recorded_at"],
    )

    # -------------------------------------------------------------------------
    # Create alert_configs table
    # -------------------------------------------------------------------------
    op.create_table(
        "alert_configs",
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
        sa.Column(
            "counter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("counters.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "alert_type",
            sa.Enum("queue_length", "wait_time", name="alert_type"),
            nullable=False,
            server_default="queue_length",
        ),
        sa.Column("threshold", sa.Integer, nullable=False),
        sa.Column(
            "cooldown_minutes",
            sa.Integer,
            nullable=False,
            server_default="30",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
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

    op.create_index("idx_alerts_store_id", "alert_configs", ["store_id"])
    op.create_index(
        "idx_alerts_active",
        "alert_configs",
        ["store_id", "is_active"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_table("alert_configs")
    op.drop_table("queue_snapshots")
    postgresql.ENUM(name="alert_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="queue_update_source").drop(op.get_bind(), checkfirst=True)
