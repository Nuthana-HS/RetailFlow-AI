"""Create camera_zones table

Revision ID: 004
Revises: 003
Create Date: 2026-06-27 00:00:00.000000

Description:
    Computer Vision schema for Phase 8.

    Creates:
        - camera_zones: Maps counter → camera source + queue zone ROI

    Indexes:
        - idx_camera_zones_counter_id: Lookup zone for a specific counter
        - idx_camera_zones_store_id:   Fetch all zones for a store (CV service startup)
        - uq_camera_zones_counter_id:  Enforce one zone per counter

    Constraints:
        - fk_camera_zones_counter: References counters.id (CASCADE)
        - fk_camera_zones_store:   References stores.id (CASCADE)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "camera_zones",
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
            sa.ForeignKey("counters.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "camera_source",
            sa.String(20),
            nullable=False,
            server_default="simulation",
        ),
        sa.Column("camera_url", sa.String(500), nullable=True),
        sa.Column("zone_x1", sa.Float, nullable=False),
        sa.Column("zone_y1", sa.Float, nullable=False),
        sa.Column("zone_x2", sa.Float, nullable=False),
        sa.Column("zone_y2", sa.Float, nullable=False),
        sa.Column(
            "frame_width",
            sa.Integer,
            nullable=False,
            server_default="1280",
        ),
        sa.Column(
            "frame_height",
            sa.Integer,
            nullable=False,
            server_default="720",
        ),
        sa.Column(
            "min_confidence",
            sa.Float,
            nullable=False,
            server_default="0.45",
        ),
        sa.Column(
            "update_interval_seconds",
            sa.Integer,
            nullable=False,
            server_default="5",
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

    op.create_index("idx_camera_zones_counter_id", "camera_zones", ["counter_id"])
    op.create_index("idx_camera_zones_store_id", "camera_zones", ["store_id"])
    op.create_index(
        "idx_camera_zones_active",
        "camera_zones",
        ["store_id", "is_active"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_table("camera_zones")
