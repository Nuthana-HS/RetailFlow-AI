"""
RetailFlow AI — Auth API Router

REST endpoints for authentication:
  POST /api/v1/auth/register   → Create a new account
  POST /api/v1/auth/login      → Authenticate + get JWT
  POST /api/v1/auth/refresh    → Rotate refresh token, get new access token
  POST /api/v1/auth/logout     → Revoke current session
  GET  /api/v1/auth/me         → Get current user profile

Cookie Configuration:
  - Refresh token is stored in 'rf_token' httpOnly cookie
  - httpOnly: not accessible by JavaScript (prevents XSS theft)
  - Secure: only sent over HTTPS (in production)
  - SameSite=Lax: prevents CSRF while allowing normal navigation
  - Path=/api/v1/auth/refresh: limits cookie scope to refresh endpoint
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.dependencies import (
    CurrentUser,
    get_refresh_token_from_cookie,
)
from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import (
    AuthTokenResponse,
    LogoutResponse,
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
)
from app.schemas.common import APIResponse
from app.services.auth_service import (
    AccountInactiveError,
    AuthService,
    AuthenticationError,
    DuplicateEmailError,
    TokenError,
    get_auth_service,
)

router = APIRouter()

# Cookie configuration constants
_COOKIE_NAME = "rf_token"
_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # Convert to seconds
_COOKIE_SECURE = settings.is_production   # Only HTTPS in production
_COOKIE_HTTPONLY = True
_COOKIE_SAMESITE = "lax"
_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_token_cookie(response: Response, raw_token: str) -> None:
    """Helper to set the httpOnly refresh token cookie."""
    response.set_cookie(
        key=_COOKIE_NAME,
        value=raw_token,
        max_age=_COOKIE_MAX_AGE,
        secure=_COOKIE_SECURE,
        httponly=_COOKIE_HTTPONLY,
        samesite=_COOKIE_SAMESITE,
        path=_COOKIE_PATH,
    )


def _clear_refresh_token_cookie(response: Response) -> None:
    """Helper to clear the httpOnly refresh token cookie (on logout)."""
    response.delete_cookie(
        key=_COOKIE_NAME,
        path=_COOKIE_PATH,
        secure=_COOKIE_SECURE,
        httponly=_COOKIE_HTTPONLY,
        samesite=_COOKIE_SAMESITE,
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=APIResponse[UserResponse],
    summary="Register a new user account",
    description=(
        "Creates a new RetailFlow AI user account. "
        "Returns the user profile (without password). "
        "Roles: admin, manager (default), customer."
    ),
    responses={
        201: {"description": "User registered successfully"},
        400: {"description": "Validation error (e.g., weak password)"},
        409: {"description": "Email address already registered"},
    },
)
async def register(
    data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> APIResponse[UserResponse]:
    """Register a new user account."""
    try:
        user = await auth_service.register_user(db, data)
    except DuplicateEmailError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_ALREADY_EXISTS", "message": str(e)},
        ) from e

    return APIResponse(
        data=UserResponse.model_validate(user),
        message="Account created successfully. Please log in.",
    )


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[AuthTokenResponse],
    summary="Log in and receive JWT access token",
    description=(
        "Authenticates a user with email and password. "
        "Returns a JWT access token in the response body and sets a "
        "refresh token as an httpOnly cookie named 'rf_token'."
    ),
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid email or password"},
        403: {"description": "Account suspended"},
    },
)
async def login(
    data: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> APIResponse[AuthTokenResponse]:
    """Authenticate a user and issue JWT + refresh token."""
    try:
        access_token, raw_refresh_token = await auth_service.authenticate_user(
            db, data.email, data.password
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": str(e)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except AccountInactiveError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_SUSPENDED", "message": str(e)},
        ) from e

    # Fetch the user for the response (we only got tokens above)
    from app.repositories.user_repository import UserRepository
    import uuid
    from app.core.security import decode_access_token
    payload = decode_access_token(access_token)
    user_repo = UserRepository()
    user = await user_repo.get_by_id(db, uuid.UUID(payload.sub))

    # Set httpOnly refresh token cookie
    _set_refresh_token_cookie(response, raw_refresh_token)

    return APIResponse(
        data=AuthTokenResponse(
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
            user=UserResponse.model_validate(user),
        ),
        message="Login successful",
    )


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[AuthTokenResponse],
    summary="Refresh access token using refresh token cookie",
    description=(
        "Exchanges the 'rf_token' httpOnly cookie for a new access token. "
        "The refresh token is rotated on each use (old token revoked, new token issued). "
        "Reusing a revoked token will terminate ALL active sessions."
    ),
    responses={
        200: {"description": "Token refreshed successfully"},
        401: {"description": "Missing, invalid, or expired refresh token"},
    },
)
async def refresh_token(
    response: Response,
    raw_token: str = Depends(get_refresh_token_from_cookie),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> APIResponse[AuthTokenResponse]:
    """Rotate refresh token and issue new access token."""
    try:
        new_access_token, new_raw_token = await auth_service.refresh_access_token(
            db, raw_token
        )
    except TokenError as e:
        # Clear the invalid cookie
        _clear_refresh_token_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "REFRESH_TOKEN_INVALID", "message": str(e)},
        ) from e

    # Fetch updated user profile
    from app.repositories.user_repository import UserRepository
    import uuid
    from app.core.security import decode_access_token
    payload = decode_access_token(new_access_token)
    user_repo = UserRepository()
    user = await user_repo.get_by_id(db, uuid.UUID(payload.sub))

    # Set the new refresh token cookie (rotated)
    _set_refresh_token_cookie(response, new_raw_token)

    return APIResponse(
        data=AuthTokenResponse(
            access_token=new_access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
            user=UserResponse.model_validate(user),
        ),
        message="Token refreshed successfully",
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[LogoutResponse],
    summary="Log out and revoke refresh token",
    description=(
        "Revokes the current refresh token session and clears the 'rf_token' cookie. "
        "The access token remains valid until it expires (15 minutes). "
        "The frontend should discard the access token from memory immediately."
    ),
)
async def logout(
    response: Response,
    raw_token: str = Depends(get_refresh_token_from_cookie),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    current_user: CurrentUser = None,  # Optional — token may be expired
) -> APIResponse[LogoutResponse]:
    """Revoke the current session."""
    await auth_service.logout(db, raw_token)
    _clear_refresh_token_cookie(response)

    return APIResponse(
        data=LogoutResponse(),
        message="Logged out successfully",
    )


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[UserResponse],
    summary="Get current user profile",
    description="Returns the profile of the currently authenticated user.",
)
async def get_me(
    current_user: CurrentUser,
) -> APIResponse[UserResponse]:
    """Get the current authenticated user's profile."""
    return APIResponse(
        data=UserResponse.model_validate(current_user),
        message="User profile retrieved",
    )
