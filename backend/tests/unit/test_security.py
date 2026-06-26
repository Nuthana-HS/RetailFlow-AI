"""
RetailFlow AI — Unit Tests: Security Utilities

Tests for app.core.security:
  - Password hashing and verification
  - JWT creation and decoding
  - Refresh token generation and hashing

These are pure unit tests — no database, no Redis, no HTTP calls.
All functions are deterministic and testable in isolation.
"""

import time

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    get_token_expiry,
    hash_password,
    hash_refresh_token,
    verify_password,
)


# =============================================================================
# Password Hashing Tests
# =============================================================================

class TestPasswordHashing:
    """Tests for bcrypt password hashing."""

    def test_hash_password_returns_string(self) -> None:
        """hash_password should return a non-empty string."""
        result = hash_password("TestPass123!")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_password_is_not_plaintext(self) -> None:
        """The hash must not contain the original password."""
        password = "TestPass123!"
        hashed = hash_password(password)
        assert password not in hashed

    def test_hash_password_produces_different_hashes(self) -> None:
        """Same password should produce different hashes (due to bcrypt salt)."""
        hash1 = hash_password("TestPass123!")
        hash2 = hash_password("TestPass123!")
        # bcrypt includes random salt, so hashes should differ
        assert hash1 != hash2

    def test_hash_password_starts_with_bcrypt_prefix(self) -> None:
        """bcrypt hashes always start with $2b$ (cost factor 12 format)."""
        hashed = hash_password("TestPass123!")
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self) -> None:
        """verify_password should return True for matching password."""
        password = "CorrectHorse@Battery99"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self) -> None:
        """verify_password should return False for wrong password."""
        hashed = hash_password("CorrectPassword123!")
        assert verify_password("WrongPassword123!", hashed) is False

    def test_verify_password_case_sensitive(self) -> None:
        """Passwords are case-sensitive."""
        hashed = hash_password("Password123!")
        assert verify_password("password123!", hashed) is False

    def test_verify_empty_password_returns_false(self) -> None:
        """Verify against empty string should return False."""
        hashed = hash_password("ValidPass123!")
        assert verify_password("", hashed) is False


# =============================================================================
# JWT Access Token Tests
# =============================================================================

class TestJWTTokens:
    """Tests for JWT access token creation and decoding."""

    def test_create_access_token_returns_string(self) -> None:
        """create_access_token should return a non-empty string."""
        token = create_access_token(
            user_id="test-user-id",
            email="test@example.com",
            role="manager",
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token_returns_correct_payload(self) -> None:
        """Decoded token should contain the original claims."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        email = "manager@dmart.com"
        role = "manager"

        token = create_access_token(user_id=user_id, email=email, role=role)
        payload = decode_access_token(token)

        assert payload.sub == user_id
        assert payload.email == email
        assert payload.role == role
        assert payload.type == "access"

    def test_decode_access_token_has_valid_expiry(self) -> None:
        """Token expiry should be in the future."""
        token = create_access_token(
            user_id="user-id",
            email="test@example.com",
            role="admin",
        )
        payload = decode_access_token(token)

        now = int(time.time())
        assert payload.exp > now
        assert payload.iat <= now

    def test_decode_access_token_invalid_signature_raises(self) -> None:
        """Tampered token should raise JWTError."""
        token = create_access_token(
            user_id="user-id",
            email="test@example.com",
            role="admin",
        )
        # Corrupt the signature
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(JWTError):
            decode_access_token(tampered)

    def test_decode_access_token_random_string_raises(self) -> None:
        """Random string is not a valid JWT."""
        with pytest.raises(JWTError):
            decode_access_token("not.a.valid.jwt.token")

    def test_create_token_with_custom_expiry(self) -> None:
        """Custom expiry duration should be reflected in the token."""
        from datetime import timedelta
        token = create_access_token(
            user_id="user-id",
            email="test@example.com",
            role="manager",
            expires_delta=timedelta(hours=2),
        )
        payload = decode_access_token(token)
        expected_exp = int(time.time()) + 7200  # 2 hours
        # Allow 5 seconds of drift
        assert abs(payload.exp - expected_exp) < 5

    def test_access_token_type_field(self) -> None:
        """Token must have type='access' to prevent refresh token misuse."""
        token = create_access_token(
            user_id="user-id",
            email="test@example.com",
            role="manager",
        )
        payload = decode_access_token(token)
        assert payload.type == "access"


# =============================================================================
# Refresh Token Tests
# =============================================================================

class TestRefreshTokens:
    """Tests for opaque refresh token generation and hashing."""

    def test_generate_refresh_token_returns_string(self) -> None:
        """generate_refresh_token should return a non-empty string."""
        token = generate_refresh_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_refresh_token_is_unique(self) -> None:
        """Each generated token should be unique (UUIDs)."""
        tokens = {generate_refresh_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_hash_refresh_token_is_consistent(self) -> None:
        """Same input always produces same SHA-256 hash."""
        token = "550e8400-e29b-41d4-a716-446655440000"
        hash1 = hash_refresh_token(token)
        hash2 = hash_refresh_token(token)
        assert hash1 == hash2

    def test_hash_refresh_token_length(self) -> None:
        """SHA-256 hash is always 64 hex characters."""
        token = generate_refresh_token()
        hashed = hash_refresh_token(token)
        assert len(hashed) == 64

    def test_hash_refresh_token_different_inputs_different_hashes(self) -> None:
        """Different tokens produce different hashes."""
        token1 = generate_refresh_token()
        token2 = generate_refresh_token()
        assert hash_refresh_token(token1) != hash_refresh_token(token2)

    def test_hash_refresh_token_is_not_reversible(self) -> None:
        """The hash should not contain the original token."""
        token = "my-secret-token-value"
        hashed = hash_refresh_token(token)
        assert token not in hashed

    def test_get_token_expiry_is_in_future(self) -> None:
        """Token expiry should always be in the future."""
        from datetime import datetime, timezone
        expiry = get_token_expiry()
        assert expiry > datetime.now(tz=timezone.utc)
