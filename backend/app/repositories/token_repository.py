"""
RetailFlow AI — Refresh Token Repository

Data access layer for the RefreshToken model.

Token Rotation Security Pattern:
  1. On login → create new token record
  2. On refresh → mark old token as revoked, create new token
  3. If revoked token is reused → detect theft, revoke ALL user tokens
  4. Periodic cleanup → delete expired tokens (via cron or on-login cleanup)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_token_expiry, hash_refresh_token
from app.models.user import RefreshToken


class TokenRepository:
    """
    Data access layer for RefreshToken operations.

    The repository receives the RAW token but only stores its HASH.
    The raw token is handled entirely by the caller (AuthService).
    """

    async def create(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        raw_token: str,
    ) -> RefreshToken:
        """
        Create a new refresh token record.

        The raw token is hashed (SHA-256) before storage.
        The caller is responsible for sending the raw token to the client.

        Args:
            db: Active database session.
            user_id: The user this token belongs to.
            raw_token: The raw UUID token to be sent to the client.

        Returns:
            The created RefreshToken record (with hashed token_hash).
        """
        token = RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(raw_token),
            expires_at=get_token_expiry(),
        )
        db.add(token)
        await db.flush()
        await db.refresh(token)
        return token

    async def get_by_raw_token(
        self,
        db: AsyncSession,
        raw_token: str,
    ) -> RefreshToken | None:
        """
        Look up a refresh token record by its raw value.

        Hashes the raw token before querying (we only store hashes).

        Returns:
            RefreshToken instance or None if not found.
        """
        token_hash = hash_refresh_token(raw_token)
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(
        self,
        db: AsyncSession,
        token_id: uuid.UUID,
    ) -> None:
        """
        Mark a specific refresh token as revoked.

        Called after a token is successfully used (rotation).
        The revoked token cannot be used again.

        Args:
            db: Active database session.
            token_id: The UUID of the RefreshToken record to revoke.
        """
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token_id)
            .values(revoked=True)
        )
        await db.flush()

    async def revoke_all_for_user(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """
        Revoke ALL active refresh tokens for a user.

        Called when:
          - A token theft is detected (revoked token reuse)
          - User explicitly logs out of all sessions
          - Admin disables a user account

        Returns:
            Number of tokens revoked.
        """
        result = await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,  # noqa: E712
            )
            .values(revoked=True)
            .returning(RefreshToken.id)
        )
        await db.flush()
        return len(result.fetchall())

    async def delete_expired(
        self,
        db: AsyncSession,
    ) -> int:
        """
        Delete all expired refresh tokens from the database.

        Called by a maintenance cron job to keep the table clean.
        Expired tokens are functionally useless but take up space.

        Returns:
            Number of tokens deleted.
        """
        result = await db.execute(
            delete(RefreshToken)
            .where(RefreshToken.expires_at < datetime.now(tz=timezone.utc))
            .returning(RefreshToken.id)
        )
        await db.flush()
        return len(result.fetchall())

    async def get_active_count_for_user(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """
        Count active (non-revoked, non-expired) sessions for a user.

        Used to limit concurrent sessions per user if needed.
        """
        result = await db.execute(
            select(RefreshToken.id).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,  # noqa: E712
                RefreshToken.expires_at > datetime.now(tz=timezone.utc),
            )
        )
        return len(result.fetchall())
