"""Notification payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.notification import NotificationType
from app.schemas.common import ORMModel
from app.schemas.pulse import PulseRef
from app.schemas.user import UserSummary


class NotificationOut(ORMModel):
    """A single notification, as stored."""

    id: int
    type: NotificationType
    actor: UserSummary
    pulse: PulseRef | None = None
    is_read: bool
    created_at: datetime


class NotificationGroup(BaseModel):
    """A row of the inbox: one thing that happened, and everyone who did it.

    ``actors`` holds only the few faces the row shows; ``actor_count`` is how
    many there really were, which is what "and 12 others" is counted from.
    """

    key: str
    type: NotificationType
    actors: list[UserSummary]
    actor_count: int
    pulse: PulseRef | None = None
    is_read: bool
    created_at: datetime


class UnreadCounts(BaseModel):
    """Unread per tab, so each can carry its own badge."""

    all: int = 0
    mentions: int = 0
    requests: int = 0
    total: int = 0


class UnreadCount(ORMModel):
    unread: int
