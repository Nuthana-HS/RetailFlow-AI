"""
RetailFlow AI — Auth FastAPI Dependencies (RBAC)

Provides reusable FastAPI dependencies for:
  1. Extracting and validating the current user from a JWT
  2. Enforcing role-based access control (RBAC) on route handlers

Usage in route handlers:
    # Any authenticated user
    @router.get("/me")
    async def get_me(user: User = Depends(get_current_active_user)):
        ...

    # Admin only
    @router.post("/stores")
    async def create_store(
        db: AsyncSession = Depends(get_db),
        user: User = Depends(require_role(UserRole.ADMIN)),
    ):
        ...

    # Admin or Manager
    @router.get("/dashboard")
    async def dashboard(
        user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))
    ):
        ...
"""

from typing import Annotated

import structlog
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

logger = structlog.get_logger(__name__)

# OAuth2 Bearer scheme for Swagger UI "Authorize" button support
_bearer_scheme = HTTPBearer(auto_error=False)


# =============================================================================
# Current User Extraction
# =============================================================================

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: Extract and validate the current user from JWT.

    Reads the Bearer token from the Authorization header, decodes it,
    and returns the corresponding User from the database.

    This is the BASE auth dependency. All other auth dependencies
    build on top of this one.

    Raises:
        HTTP 401: If token is missing, invalid, or expired.
        HTTP 401: If the user referenced in the token no longer exists.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "UNAUTHORIZED",
            "message": "Authentication required. Please provide a valid access token.",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.sub
    except (JWTError, ValueError) as e:
        logger.debug("JWT decode failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "TOKEN_EXPIRED" if "expired" in str(e).lower() else "UNAUTHORIZED",
                "message": "Your session has expired. Please log in again."
                if "expired" in str(e).lower()
                else "Invalid access token.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Fetch user from database
    user_repo = UserRepository()
    import uuid
    user = await user_repo.get_by_id(db, uuid.UUID(user_id))

    if user is None:
        logger.warning("Token references non-existent user", user_id=user_id)
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    FastAPI dependency: Ensure the current user's account is active.

    Raises:
        HTTP 403: If the user account has been suspended.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ACCOUNT_SUSPENDED",
                "message": (
                    "Your account has been suspended. "
                    "Please contact support at support@retailflow.ai"
                ),
            },
        )
    return current_user


# =============================================================================
# Role-Based Access Control
# =============================================================================

def require_role(*allowed_roles: UserRole):
    """
    Factory function that creates a FastAPI dependency for role checking.

    Creates a dependency that validates the current user has one of the
    allowed roles. Raises HTTP 403 if the user's role is insufficient.

    Args:
        *allowed_roles: One or more UserRole values that are permitted.

    Returns:
        A FastAPI dependency function.

    Example:
        # Admin only
        Depends(require_role(UserRole.ADMIN))

        # Admin or Manager
        Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))
    """
    async def _check_role(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                "RBAC check failed",
                user_id=str(current_user.id),
                user_role=current_user.role,
                required_roles=[r.value for r in allowed_roles],
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": (
                        f"Access denied. This action requires one of these roles: "
                        f"{', '.join(r.value for r in allowed_roles)}"
                    ),
                },
            )
        return current_user

    return _check_role


# =============================================================================
# Refresh Token Extraction (from httpOnly cookie)
# =============================================================================

def get_refresh_token_from_cookie(
    rf_token: Annotated[str | None, Cookie()] = None,
) -> str:
    """
    FastAPI dependency: Extract the refresh token from the httpOnly cookie.

    The cookie is named 'rf_token' and is set by the login endpoint.
    It is httpOnly (not accessible from JavaScript) and Secure (HTTPS only).

    Raises:
        HTTP 401: If the cookie is missing.
    """
    if rf_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "REFRESH_TOKEN_MISSING",
                "message": "Refresh token not found. Please log in again.",
            },
        )
    return rf_token


# =============================================================================
# Convenience Type Aliases
# =============================================================================

# Use these as type annotations in route handlers for cleaner code:
#   async def endpoint(user: CurrentUser): ...
#   async def endpoint(user: AdminUser): ...
#   async def endpoint(user: ManagerUser): ...

CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
ManagerUser = Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))]
