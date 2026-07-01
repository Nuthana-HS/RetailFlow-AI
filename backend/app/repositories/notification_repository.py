"""
RetailFlow AI — Notification Repository

Data access layer for Notification records.

Query Design:
    inbox() uses a composite index (user_id + created_at) for fast,
    paginated inbox loading. The partial index on is_read=false makes
    unread_count virtually free (index-only scan).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


class NotificationRepository:
    """CRUD for Notification records."""

    async def create_bulk(
        self,
        db: AsyncSession,
        notifications: list[dict],
    ) -> list[Notification]:
        """
        Create multiple notifications in a single batch insert.

        One notification is created per manager of the affected store.

        Args:
            notifications: List of dicts with all Notification field values.
        """
        records = [Notification(**n) for n in notifications]
        db.add_all(records)
        await db.flush()
        # Refresh to get server-generated created_at timestamps
        for r in records:
            await db.refresh(r)
        return records

    async def get_inbox(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int, int]:
        """
        Get paginated notifications for a user.

        Args:
            user_id: The manager's user ID.
            skip: Offset for pagination.
            limit: Page size.
            unread_only: If True, returns only unread notifications.

        Returns:
            Tuple of (notifications, total_count, unread_count).
        """
        base_filter = Notification.user_id == user_id

        # Unread count (uses partial index)
        unread_q = await db.execute(
            select(func.count(Notification.id)).where(
                and_(base_filter, Notification.is_read == False)  # noqa: E712
            )
        )
        unread_count = unread_q.scalar_one()

        # Total count
        count_filter = and_(base_filter, Notification.is_read == False) \
            if unread_only else base_filter

        total_q = await db.execute(
            select(func.count(Notification.id)).where(count_filter)
        )
        total = total_q.scalar_one()

        # Notifications (sorted newest first)
        result = await db.execute(
            select(Notification)
            .where(count_filter)
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        notifications = list(result.scalars().all())

        return notifications, total, unread_count

    async def mark_as_read(
        self,
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification | None:
        """
        Mark a single notification as read.

        User ID check ensures managers can only read their own notifications.
        """
        result = await db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
        )
        notification = result.scalar_one_or_none()
        if notification and not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(tz=timezone.utc)
            await db.flush()
        return notification

    async def mark_all_as_read(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """
        Mark all unread notifications for a user as read.

        Returns:
            Number of notifications marked as read.
        """
        result = await db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,  # noqa: E712
                )
            )
            .values(
                is_read=True,
                read_at=datetime.now(tz=timezone.utc),
            )
            .returning(Notification.id)
        )
        rows = result.fetchall()
        return len(rows)

    async def get_unread_count(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """Fast unread count for notification badge (uses partial index)."""
        result = await db.execute(
            select(func.count(Notification.id)).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,  # noqa: E712
                )
            )
        )
        return result.scalar_one()
