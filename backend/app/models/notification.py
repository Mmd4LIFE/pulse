"""In-app notifications."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntPrimaryKey, Timestamped

if TYPE_CHECKING:
    from app.models.pulse import Pulse
    from app.models.user import User


class NotificationType(str, enum.Enum):
    LIKE = "like"
    REPLY = "reply"
    REPULSE = "repulse"
    QUOTE = "quote"
    FOLLOW = "follow"
    MENTION = "mention"


class Notification(IntPrimaryKey, Timestamped, Base):
    __tablename__ = "notifications"

    recipient_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", native_enum=True),
        nullable=False,
    )
    pulse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pulses.id", ondelete="CASCADE")
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )

    actor: Mapped[User] = relationship(foreign_keys=[actor_id], lazy="joined")
    pulse: Mapped[Pulse | None] = relationship(foreign_keys=[pulse_id], lazy="joined")

    __table_args__ = (
        Index(
            "ix_notifications_recipient_created", "recipient_id", text("created_at DESC")
        ),
        # Powers the unread badge without scanning read history.
        Index(
            "ix_notifications_unread",
            "recipient_id",
            postgresql_where=text("is_read = false"),
        ),
    )
