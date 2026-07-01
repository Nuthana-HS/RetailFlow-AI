"""
RetailFlow AI — Notification Pydantic Schemas
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    """Single notification as returned in the inbox."""

    id: uuid.UUID
    alert_config_id: uuid.UUID
    store_id: uuid.UUID
    counter_id: uuid.UUID | None
    user_id: uuid.UUID
    title: str
    message: str
    trigger_value: int
    threshold: int
    alert_type: str
    is_read: bool
    read_at: datetime | None
    email_sent: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationInboxResponse(BaseModel):
    """Paginated notification inbox for the current user."""

    notifications: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    limit: int
