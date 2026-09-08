"""Notification payloads."""

from __future__ import annotations

from datetime import datetime

from app.models.notification import NotificationType
from app.schemas.common import ORMModel
from app.schemas.pulse import PulseRef
from app.schemas.user import UserSummary


class NotificationOut(ORMModel):
    id: int
    type: NotificationType
    actor: UserSummary
    pulse: PulseRef | None = None
    is_read: bool
    created_at: datetime


class UnreadCount(ORMModel):
    unread: int
