"""Create notifications table

Revision ID: 005
Revises: 004
Create Date: 2026-06-27 00:00:00.000000

Description:
    Phase 10 — Notification Service schema.

    Creates:
        - notifications: In-app alert notifications delivered to managers

    Indexes:
        - idx_notifications_user_id:     Fetch inbox for a user (fast unread count)
        - idx_notifications_store_id:    Admin view of all store notifications
        - idx_notifications_user_unread: Partial index for unread badge count

    Constraints:
        - fk_notifications_alert_config: References alert_configs.id (CASCADE)
        - fk_notifications_store:        References stores.id (CASCADE)
        - fk_notifications_counter:      References counters.id (SET NULL)
        - fk_notifications_user:         References users.id (CASCADE)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "alert_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alert_configs.id", ondelete="CASCADE"),
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
            sa.ForeignKey("counters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("trigger_value", sa.Integer, nullable=False),
        sa.Column("threshold", sa.Integer, nullable=False),
        sa.Column("alert_type", sa.String(20), nullable=False),
        sa.Column(
            "is_read",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "email_sent",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "email_failed",
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
    )

    op.create_index("idx_notifications_user_id", "notifications", ["user_id"])
    op.create_index("idx_notifications_store_id", "notifications", ["store_id"])
    op.create_index("idx_notifications_created_at", "notifications", ["created_at"])

    # Partial index: fast unread count query (badge counter)
    op.create_index(
        "idx_notifications_user_unread",
        "notifications",
        ["user_id", "created_at"],
        postgresql_where=sa.text("is_read = false"),
    )


def downgrade() -> None:
    op.drop_table("notifications")
