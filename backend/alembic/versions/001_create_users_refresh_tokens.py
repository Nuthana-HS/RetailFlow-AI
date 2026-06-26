"""Create users and refresh_tokens tables

Revision ID: 001
Revises:
Create Date: 2026-06-27 00:00:00.000000

Description:
    Initial database schema for Phase 3 (Authentication).

    Creates:
        - users table: Core user accounts with RBAC roles
        - refresh_tokens table: JWT refresh token management

    Indexes created:
        - idx_users_email: Fast login lookups by email
        - idx_users_role: Admin queries for filtering by role
        - idx_refresh_tokens_user_id: Fast token revocation by user
        - idx_refresh_tokens_token_hash: Fast token lookup during refresh

    Constraints:
        - uq_users_email: Email must be unique
        - uq_refresh_tokens_token_hash: Token hash must be unique
        - fk_refresh_tokens_user_id: Tokens deleted when user is deleted (CASCADE)
        - ck_users_role: Role must be one of: admin, manager, customer
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users and refresh_tokens tables with all indexes and constraints."""

    # -------------------------------------------------------------------------
    # Create user_role enum type
    # -------------------------------------------------------------------------
    user_role_enum = postgresql.ENUM(
        "admin", "manager", "customer",
        name="user_role",
        create_type=True,
    )
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # -------------------------------------------------------------------------
    # Create users table
    # -------------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "manager", "customer", name="user_role"),
            nullable=False,
            server_default="manager",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
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
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # Indexes for users table
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_role", "users", ["role"])

    # -------------------------------------------------------------------------
    # Create refresh_tokens table
    # -------------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )

    # Indexes for refresh_tokens table
    op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("idx_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
    op.create_index(
        "idx_refresh_tokens_revoked",
        "refresh_tokens",
        ["revoked"],
        postgresql_where=sa.text("revoked = false"),  # Partial index — only non-revoked tokens
    )


def downgrade() -> None:
    """Drop refresh_tokens and users tables."""
    op.drop_table("refresh_tokens")
    op.drop_table("users")

    # Drop the enum type
    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)
