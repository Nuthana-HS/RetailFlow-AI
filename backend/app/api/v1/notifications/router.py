"""
RetailFlow AI — Notifications API Router

Manager notification inbox endpoints:

  GET  /api/v1/notifications/           → Paginated inbox (newest first)
  GET  /api/v1/notifications/unread-count → Badge count
  PATCH /api/v1/notifications/{id}/read → Mark single notification as read
  POST /api/v1/notifications/read-all   → Mark all as read
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.dependencies import ManagerUser
from app.core.database import get_db
from app.repositories.notification_repository import NotificationRepository
from app.schemas.common import APIResponse
from app.schemas.notification import NotificationInboxResponse, NotificationResponse

router = APIRouter()
_notification_repo = NotificationRepository()


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[NotificationInboxResponse],
    summary="Get notification inbox",
    description=(
        "Returns the current user's notifications, sorted newest first. "
        "Includes total count and unread count for badge display. "
        "Use unread_only=true to see only new alerts."
    ),
)
async def get_inbox(
    current_user: ManagerUser,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    unread_only: bool = Query(default=False, description="Return only unread notifications"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[NotificationInboxResponse]:
    """Get the current manager's notification inbox."""
    skip = (page - 1) * limit
    notifications, total, unread_count = await _notification_repo.get_inbox(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )
    return APIResponse(
        data=NotificationInboxResponse(
            notifications=[NotificationResponse.model_validate(n) for n in notifications],
            total=total,
            unread_count=unread_count,
            page=page,
            limit=limit,
        ),
        message=f"{unread_count} unread notification(s)",
    )


@router.get(
    "/unread-count",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[dict],
    summary="Get unread notification count",
    description="Lightweight endpoint for polling the dashboard badge counter. Returns only the count.",
)
async def get_unread_count(
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[dict]:
    """Get number of unread notifications (for badge display)."""
    count = await _notification_repo.get_unread_count(db, user_id=current_user.id)
    return APIResponse(
        data={"unread_count": count, "user_id": str(current_user.id)},
        message=f"{count} unread",
    )


@router.patch(
    "/{notification_id}/read",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[NotificationResponse],
    summary="Mark a notification as read",
)
async def mark_as_read(
    notification_id: uuid.UUID,
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[NotificationResponse]:
    """Mark a single notification as read. No-op if already read."""
    from fastapi import HTTPException

    notification = await _notification_repo.mark_as_read(
        db, notification_id=notification_id, user_id=current_user.id
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Notification {notification_id} not found"},
        )
    return APIResponse(
        data=NotificationResponse.model_validate(notification),
        message="Marked as read",
    )


@router.post(
    "/read-all",
    status_code=status.HTTP_200_OK,
    response_model=APIResponse[dict],
    summary="Mark all notifications as read",
    description="Clears the unread badge. Marks all unread notifications as read at once.",
)
async def mark_all_as_read(
    current_user: ManagerUser,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[dict]:
    """Mark all unread notifications as read for the current user."""
    count = await _notification_repo.mark_all_as_read(db, user_id=current_user.id)
    return APIResponse(
        data={"marked_read": count},
        message=f"Marked {count} notification(s) as read",
    )
