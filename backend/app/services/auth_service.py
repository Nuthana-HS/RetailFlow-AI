"""
RetailFlow AI — Auth Service

Business logic layer for authentication and user management.

Clean Architecture Rules:
  - AuthService never imports from app.api (no upward dependency)
  - AuthService never constructs database sessions (injected via constructor)
  - AuthService calls repositories, not SQLAlchemy directly
  - AuthService raises domain exceptions, not HTTP exceptions (those live in the router)

Exception Hierarchy:
  - AuthenticationError  → Invalid credentials (maps to 401)
  - AccountInactiveError → Account suspended (maps to 403)
  - DuplicateEmailError  → Email taken (maps to 409)
  - TokenError           → Invalid/expired/revoked token (maps to 401)
"""

import uuid
from typing import Tuple

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    generate_refresh_token,
    verify_password,
    hash_password,
)
from app.models.user import User, UserRole
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserRegisterRequest

logger = structlog.get_logger(__name__)


# =============================================================================
# Domain Exceptions
# =============================================================================

class AuthenticationError(Exception):
    """Raised when credentials are invalid (wrong email/password)."""
    pass


class AccountInactiveError(Exception):
    """Raised when a user attempts to log into a suspended account."""
    pass


class DuplicateEmailError(Exception):
    """Raised when attempting to register with an already-used email."""
    pass


class TokenError(Exception):
    """Raised for invalid, expired, or revoked tokens."""
    pass


# =============================================================================
# Auth Service
# =============================================================================

class AuthService:
    """
    Orchestrates authentication business logic.

    Coordinates between:
      - UserRepository (user data access)
      - TokenRepository (refresh token data access)
      - Security utilities (hashing, JWT generation)

    All methods are async to support the async SQLAlchemy session.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: TokenRepository,
    ) -> None:
        self._user_repo = user_repo
        self._token_repo = token_repo

    async def register_user(
        self,
        db: AsyncSession,
        data: UserRegisterRequest,
    ) -> User:
        """
        Register a new user account.

        Flow:
          1. Check email uniqueness
          2. Hash the password
          3. Create user record
          4. Return the created user

        Args:
            db: Database session.
            data: Validated registration request schema.

        Returns:
            The created User instance.

        Raises:
            DuplicateEmailError: If the email is already registered.
        """
        log = logger.bind(email=data.email, role=data.role)
        log.info("Attempting user registration")

        # Check for duplicate email
        if await self._user_repo.email_exists(db, data.email):
            log.warning("Registration failed: email already exists")
            raise DuplicateEmailError(
                f"An account with email '{data.email}' already exists"
            )

        # Hash password before storing
        password_hash = hash_password(data.password)

        # Create user record
        user = await self._user_repo.create(
            db,
            email=data.email,
            password_hash=password_hash,
            full_name=data.full_name,
            role=data.role,
        )

        log.info("User registered successfully", user_id=str(user.id))
        return user

    async def authenticate_user(
        self,
        db: AsyncSession,
        email: str,
        password: str,
    ) -> Tuple[str, str]:
        """
        Authenticate a user and issue JWT + refresh token.

        Flow:
          1. Look up user by email
          2. Verify password (constant-time comparison)
          3. Check account is active
          4. Generate access token (JWT)
          5. Generate refresh token (opaque UUID, hashed in DB)
          6. Return (access_token, raw_refresh_token)

        Security: Steps 1 and 2 return the SAME error message to prevent
        user enumeration attacks (can't tell if email exists or password wrong).

        Args:
            db: Database session.
            email: User's email (normalized to lowercase).
            password: Raw password from login form.

        Returns:
            Tuple of (access_token, raw_refresh_token).

        Raises:
            AuthenticationError: If credentials are invalid.
            AccountInactiveError: If account is suspended.
        """
        log = logger.bind(email=email)
        log.info("Attempting authentication")

        # Look up user (same error for missing user and wrong password)
        user = await self._user_repo.get_by_email(db, email)

        # SECURITY: Verify password even if user is None to prevent timing attacks
        # (bcrypt verify always takes ~300ms regardless)
        dummy_hash = "$2b$12$dummy.hash.to.prevent.timing.attack.xxxxxxxxxx"
        stored_hash = user.password_hash if user else dummy_hash

        if not verify_password(password, stored_hash) or user is None:
            log.warning("Authentication failed: invalid credentials")
            raise AuthenticationError("Invalid email or password")

        # Check account is active
        if not user.is_active:
            log.warning("Authentication failed: account inactive", user_id=str(user.id))
            raise AccountInactiveError(
                "Your account has been suspended. Please contact support."
            )

        # Generate tokens
        access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            role=user.role.value,
        )
        raw_refresh_token = generate_refresh_token()
        await self._token_repo.create(db, user.id, raw_refresh_token)

        log.info("Authentication successful", user_id=str(user.id), role=user.role)
        return access_token, raw_refresh_token

    async def refresh_access_token(
        self,
        db: AsyncSession,
        raw_refresh_token: str,
    ) -> Tuple[str, str]:
        """
        Exchange a valid refresh token for a new access token and rotated refresh token.

        Token Rotation (Security):
          - Old refresh token is revoked immediately
          - A brand new refresh token is issued
          - If a revoked token is submitted → ALL user tokens revoked (theft detected)

        Args:
            db: Database session.
            raw_refresh_token: The raw refresh token from the httpOnly cookie.

        Returns:
            Tuple of (new_access_token, new_raw_refresh_token).

        Raises:
            TokenError: If the token is not found, revoked, or expired.
        """
        log = logger.bind(refresh_token_prefix=raw_refresh_token[:8])

        # Look up the token record
        token_record = await self._token_repo.get_by_raw_token(db, raw_refresh_token)

        if token_record is None:
            log.warning("Refresh failed: token not found")
            raise TokenError("Invalid refresh token")

        # SECURITY: Detect token reuse (possible theft)
        if token_record.revoked:
            log.error(
                "SECURITY ALERT: Revoked refresh token reused — possible theft",
                user_id=str(token_record.user_id),
            )
            # Revoke ALL tokens for this user (session termination)
            revoked_count = await self._token_repo.revoke_all_for_user(
                db, token_record.user_id
            )
            log.error("All user tokens revoked", count=revoked_count)
            raise TokenError(
                "Refresh token has already been used. "
                "All sessions have been terminated for security. Please log in again."
            )

        if token_record.is_expired:
            log.info("Refresh failed: token expired", user_id=str(token_record.user_id))
            raise TokenError("Refresh token has expired. Please log in again.")

        # Revoke the old token (rotation)
        await self._token_repo.revoke(db, token_record.id)

        # Fetch the user (to include up-to-date role in the new token)
        user = await self._user_repo.get_by_id(db, token_record.user_id)
        if user is None or not user.is_active:
            raise TokenError("User account not found or inactive")

        # Issue new tokens
        new_access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            role=user.role.value,
        )
        new_raw_refresh_token = generate_refresh_token()
        await self._token_repo.create(db, user.id, new_raw_refresh_token)

        log.info("Token refreshed successfully", user_id=str(user.id))
        return new_access_token, new_raw_refresh_token

    async def logout(
        self,
        db: AsyncSession,
        raw_refresh_token: str,
    ) -> None:
        """
        Logout by revoking the current refresh token session.

        Args:
            db: Database session.
            raw_refresh_token: The raw refresh token from the httpOnly cookie.
        """
        token_record = await self._token_repo.get_by_raw_token(db, raw_refresh_token)

        if token_record and not token_record.revoked:
            await self._token_repo.revoke(db, token_record.id)
            logger.info(
                "User logged out",
                user_id=str(token_record.user_id),
            )

    async def logout_all_sessions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> None:
        """
        Logout from all devices by revoking all refresh tokens.

        Args:
            db: Database session.
            user_id: The user whose sessions should all be terminated.
        """
        count = await self._token_repo.revoke_all_for_user(db, user_id)
        logger.info(
            "All sessions terminated",
            user_id=str(user_id),
            sessions_revoked=count,
        )


# =============================================================================
# Dependency Factory
# =============================================================================

def get_auth_service() -> AuthService:
    """
    Factory function for creating AuthService instances.

    Used as a FastAPI dependency:
        auth_service: AuthService = Depends(get_auth_service)

    Returns:
        A fully configured AuthService with repositories injected.
    """
    return AuthService(
        user_repo=UserRepository(),
        token_repo=TokenRepository(),
    )
