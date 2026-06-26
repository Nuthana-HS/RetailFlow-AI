"""
RetailFlow AI — SQLAlchemy ORM Models: User & RefreshToken

These are the database models for authentication and authorization.
All models inherit from Base (defined in app.core.database).

Architecture Notes:
- UUIDs are used as primary keys for security (prevents enumeration attacks)
- Passwords are NEVER stored in plaintext — only bcrypt hashes
- Refresh tokens are stored as SHA-256 hashes, not raw values
- Soft-delete is NOT used on users — GDPR allows full deletion
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# =============================================================================
# Enums
# =============================================================================

class UserRole(str, enum.Enum):
    """
    User roles for Role-Based Access Control (RBAC).

    Inherits from str so the enum value is used in JSON serialization,
    database storage, and JWT payload without manual conversion.

    Hierarchy:
        ADMIN   → Full system access (create stores, manage all users)
        MANAGER → Store-level access (manage their assigned stores)
        CUSTOMER → Read-only access (view queue status)
    """
    ADMIN = "admin"
    MANAGER = "manager"
    CUSTOMER = "customer"


# =============================================================================
# User Model
# =============================================================================

class User(Base):
    """
    Represents a registered user of the RetailFlow AI platform.

    Relationships:
        - stores: Stores administered by this user (if role=admin)
        - managed_stores: Stores this user manages (if role=manager)
        - refresh_tokens: Active refresh token sessions
        - notifications: In-app notifications
    """

    __tablename__ = "users"

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique user identifier (UUID v4)",
    )

    # Identity
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User's email address — used as login identifier",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt hash of the user's password (cost factor 12)",
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User's full display name",
    )

    # Authorization
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.CUSTOMER,
        index=True,
        comment="RBAC role: admin | manager | customer",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False = account suspended (soft disable)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Account creation timestamp (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last profile update timestamp (UTC)",
    )

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",  # Delete tokens when user is deleted
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"


# =============================================================================
# RefreshToken Model
# =============================================================================

class RefreshToken(Base):
    """
    Stores hashed refresh tokens for JWT session management.

    Security Design:
        - Raw refresh token is NEVER stored in the database
        - Only the SHA-256 hash of the token is stored
        - Tokens are invalidated (revoked=True) after use (rotation)
        - Expired tokens are periodically cleaned up by a cron job

    Rotation Strategy (prevents refresh token theft):
        1. Client sends refresh token
        2. Server looks up hash → finds valid token
        3. Server marks old token as revoked=True
        4. Server issues new access token + new refresh token
        5. If old token is used again → detected as theft → revoke all user tokens
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )

    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign Key
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Token
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="SHA-256 hash of the raw refresh token",
    )

    # Lifecycle
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Token expiry timestamp (UTC)",
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="True = token has been used or explicitly invalidated",
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="refresh_tokens",
    )

    @property
    def is_expired(self) -> bool:
        """Check if this token has passed its expiry time."""
        return datetime.now(tz=timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """A token is valid if it is neither revoked nor expired."""
        return not self.revoked and not self.is_expired

    def __repr__(self) -> str:
        return (
            f"<RefreshToken id={self.id} user_id={self.user_id} "
            f"revoked={self.revoked} expired={self.is_expired}>"
        )
