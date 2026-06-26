"""
RetailFlow AI — User Repository

Data access layer for the User model.

Repository Pattern:
  - All database queries for users live here (no SQL in service or route layers)
  - Methods are typed and return domain objects (User model instances)
  - Unit tests mock this class to test the service layer without a real database
  - SQLAlchemy sessions are injected via dependency injection (not imported directly)
"""

import uuid
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.schemas.auth import UserRegisterRequest


class UserRepository:
    """
    Data access layer for User operations.

    All methods are async and take a db session as the first argument.
    This makes the repository stateless and easy to test.

    Usage:
        repo = UserRepository()
        user = await repo.get_by_email(db, "test@example.com")
    """

    async def create(
        self,
        db: AsyncSession,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        role: UserRole,
    ) -> User:
        """
        Create a new user record in the database.

        Note: password_hash must already be hashed before calling this method.
        The repository never handles raw passwords.

        Args:
            db: Active database session.
            email: Normalized (lowercase) email address.
            password_hash: bcrypt hash of the user's password.
            full_name: User's display name.
            role: RBAC role.

        Returns:
            The newly created User instance (refreshed from DB).
        """
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
        )
        db.add(user)
        await db.flush()   # Flush to get the generated UUID
        await db.refresh(user)
        return user

    async def get_by_id(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> User | None:
        """
        Fetch a user by their UUID primary key.

        Returns:
            User instance or None if not found.
        """
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(
        self,
        db: AsyncSession,
        email: str,
    ) -> User | None:
        """
        Fetch a user by their email address.

        Args:
            email: Should be normalized to lowercase before calling.

        Returns:
            User instance or None if not found.
        """
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def email_exists(
        self,
        db: AsyncSession,
        email: str,
    ) -> bool:
        """
        Check if an email address is already registered.

        More efficient than get_by_email() for existence checks
        as it uses a COUNT query rather than fetching all fields.

        Returns:
            True if the email is taken, False if available.
        """
        result = await db.execute(
            select(User.id).where(User.email == email).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def update_active_status(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        is_active: bool,
    ) -> User | None:
        """
        Activate or deactivate a user account.

        Used by admins to suspend accounts without deleting them.

        Returns:
            Updated User instance or None if not found.
        """
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_active=is_active)
        )
        await db.flush()
        return await self.get_by_id(db, user_id)

    async def list_by_role(
        self,
        db: AsyncSession,
        role: UserRole,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[User]:
        """
        List all users with a given role (paginated).

        Used by admins to list managers, etc.

        Returns:
            Sequence of User instances.
        """
        result = await db.execute(
            select(User)
            .where(User.role == role, User.is_active == True)  # noqa: E712
            .offset(skip)
            .limit(limit)
            .order_by(User.created_at.desc())
        )
        return result.scalars().all()
