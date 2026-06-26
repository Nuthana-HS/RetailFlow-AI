"""
RetailFlow AI — Auth Pydantic Schemas

Defines request/response schemas for the authentication module.

Design Principles:
  - Request schemas validate at the boundary (before business logic sees the data)
  - Response schemas NEVER include sensitive fields (password_hash, token values)
  - Field validators use Pydantic v2 style (@field_validator, @model_validator)
  - All passwords validated for complexity before hitting the service layer
"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.user import UserRole


# =============================================================================
# Request Schemas
# =============================================================================

class UserRegisterRequest(BaseModel):
    """
    Request body for POST /api/v1/auth/register.

    Validates:
      - Email format (via EmailStr)
      - Password complexity (8+ chars, uppercase, number, special char)
      - Role is a valid UserRole enum value
    """

    email: EmailStr = Field(
        ...,
        description="User's email address (used as login identifier)",
        examples=["manager@dmart.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 chars, must contain uppercase, number, special char)",
        examples=["SecurePass123!"],
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="User's full display name",
        examples=["Aarav Mehta"],
    )
    role: UserRole = Field(
        default=UserRole.MANAGER,
        description="User role: admin | manager | customer",
    )

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, value: str) -> str:
        """
        Enforces password complexity requirements.

        Rules (NIST-aligned):
          - Minimum 8 characters (checked by min_length)
          - At least 1 uppercase letter
          - At least 1 digit
          - At least 1 special character from: !@#$%^&*()_+-=[]{}|;:,.<>?
        """
        errors: list[str] = []

        if not re.search(r"[A-Z]", value):
            errors.append("at least one uppercase letter")
        if not re.search(r"\d", value):
            errors.append("at least one digit")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", value):
            errors.append("at least one special character (!@#$%^&*...)")

        if errors:
            raise ValueError(f"Password must contain: {', '.join(errors)}")

        return value

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        """Strip whitespace and validate name contains only valid characters."""
        value = value.strip()
        if not re.match(r"^[a-zA-Z\s\-.']+$", value):
            raise ValueError(
                "Full name can only contain letters, spaces, hyphens, apostrophes, and periods"
            )
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Normalize email to lowercase."""
        return value.lower().strip()


class UserLoginRequest(BaseModel):
    """Request body for POST /api/v1/auth/login."""

    email: EmailStr = Field(
        ...,
        description="Registered email address",
        examples=["manager@dmart.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Account password",
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower().strip()


class RefreshTokenRequest(BaseModel):
    """
    Request for POST /api/v1/auth/refresh.

    Note: The refresh token itself comes from the httpOnly cookie,
    not the request body. This schema is a placeholder for documentation.
    """
    pass


# =============================================================================
# Response Schemas
# =============================================================================

class UserResponse(BaseModel):
    """
    User profile returned in API responses.

    IMPORTANT: Never includes password_hash or other sensitive fields.
    """

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {
        "from_attributes": True,  # Allow creating from SQLAlchemy model instances
        "use_enum_values": True,  # Serialize role as string, not enum object
    }


class TokenData(BaseModel):
    """
    Payload stored inside the JWT access token.

    Kept minimal to reduce token size.
    Store IDs are included to avoid DB lookups on every RBAC check.
    """

    user_id: str  # UUID as string
    email: str
    role: str


class AuthTokenResponse(BaseModel):
    """
    Response body for /auth/login and /auth/refresh.

    Note: The refresh token is NOT in this response body.
    It is set as an httpOnly, Secure cookie named 'rf_token'.
    """

    access_token: str = Field(
        description="JWT access token (Bearer). Store in memory only, NOT localStorage."
    )
    token_type: str = Field(default="bearer")
    expires_in: int = Field(
        description="Access token expiry in seconds from now"
    )
    user: UserResponse = Field(
        description="Authenticated user profile"
    )


class LogoutResponse(BaseModel):
    """Response for POST /auth/logout."""
    message: str = "Logged out successfully"


class MessageResponse(BaseModel):
    """Generic message-only response."""
    message: str


# =============================================================================
# Internal Schemas (not exposed via API)
# =============================================================================

class JWTPayload(BaseModel):
    """
    Full JWT payload (decoded from access token).
    Used internally by auth dependencies.
    """

    sub: str            # Subject: user_id (UUID as string)
    email: str
    role: str
    iat: int            # Issued at (Unix timestamp)
    exp: int            # Expiry (Unix timestamp)
    type: str = "access"  # Token type identifier
