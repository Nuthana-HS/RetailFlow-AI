"""
RetailFlow AI — Security Utilities

Handles all cryptographic operations:
  - Password hashing (bcrypt)
  - JWT access token creation and verification
  - Refresh token generation and hashing

Design Notes:
  - Bcrypt cost factor = 12 (OWASP recommendation for modern hardware)
  - Access token uses HS256 (symmetric) — acceptable for single-backend deployment
  - Refresh tokens are opaque UUIDs (not JWT) — hashed before DB storage
  - All token operations are synchronous (bcrypt/jose are CPU-bound, not I/O)
"""

import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.schemas.auth import JWTPayload


# =============================================================================
# Password Hashing (bcrypt)
# =============================================================================

# CryptContext manages the hashing scheme and deprecation handling.
# Using bcrypt with deprecated="auto" allows future algorithm migration
# without invalidating existing hashes (they will be rehashed on next login).
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,          # Cost factor: ~300ms on modern hardware
)


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Args:
        plain_password: The raw password string from the user.

    Returns:
        A bcrypt hash string suitable for database storage.

    Security:
        - Cost factor 12 is resistant to modern GPU-based brute force
        - bcrypt includes a random salt (no need to manage salt separately)
        - Never call this with an empty string
    """
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        plain_password: Raw password from login form.
        hashed_password: bcrypt hash from the database.

    Returns:
        True if the password matches, False otherwise.
    """
    return _pwd_context.verify(plain_password, hashed_password)


# =============================================================================
# JWT Access Tokens
# =============================================================================

def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    The token payload includes:
        sub   → User ID (UUID string) — standard JWT "subject" claim
        email → User's email
        role  → RBAC role (admin/manager/customer)
        type  → "access" (to distinguish from other token types)
        iat   → Issued at timestamp
        exp   → Expiry timestamp

    Args:
        user_id: The user's UUID as a string.
        email: The user's email address.
        role: The user's RBAC role.
        expires_delta: Optional custom expiry duration.
                       Defaults to ACCESS_TOKEN_EXPIRE_SECONDS from settings.

    Returns:
        A signed JWT string.
    """
    now = int(time.time())
    expire_seconds = (
        int(expires_delta.total_seconds())
        if expires_delta
        else settings.ACCESS_TOKEN_EXPIRE_SECONDS
    )

    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + expire_seconds,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> JWTPayload:
    """
    Decode and validate a JWT access token.

    Validates:
        - Signature (using JWT_SECRET_KEY)
        - Expiry (exp claim)
        - Token type (must be "access")

    Args:
        token: The raw JWT string from the Authorization header.

    Returns:
        JWTPayload with decoded claims.

    Raises:
        JWTError: If the token is invalid, expired, or tampered with.
        ValueError: If token type is not "access".
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )

    if payload.get("type") != "access":
        raise ValueError("Invalid token type — expected 'access'")

    return JWTPayload(**payload)


# =============================================================================
# Refresh Tokens (Opaque, not JWT)
# =============================================================================

def generate_refresh_token() -> str:
    """
    Generate a cryptographically secure opaque refresh token.

    Returns a URL-safe UUID string. This value is sent to the client
    as an httpOnly cookie but is NEVER stored in the database directly.

    Returns:
        A UUID4 string (e.g., "550e8400-e29b-41d4-a716-446655440000").
    """
    return str(uuid.uuid4())


def hash_refresh_token(raw_token: str) -> str:
    """
    Hash a raw refresh token using SHA-256 for database storage.

    Why SHA-256 (not bcrypt)?
        - Refresh tokens are already high-entropy (UUID = 128 bits of randomness)
        - bcrypt is designed for low-entropy passwords; SHA-256 is faster and
          appropriate for high-entropy tokens
        - This is the same approach used by Django and Laravel

    Args:
        raw_token: The UUID string refresh token.

    Returns:
        A hexadecimal SHA-256 hash string (64 characters).
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


def get_token_expiry() -> datetime:
    """
    Calculate the expiry datetime for a new refresh token.

    Returns:
        UTC datetime REFRESH_TOKEN_EXPIRE_DAYS days from now.
    """
    return datetime.now(tz=timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
