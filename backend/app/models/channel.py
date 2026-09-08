"""A Telegram channel a user has connected to their account.

Pulse can mirror a user's posts into a channel they own. That is only possible
while the bot is an administrator there with permission to post, so the chat id
is resolved and the permission verified before the row is written.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntPrimaryKey, Timestamped

if TYPE_CHECKING:
    from app.models.user import User


class Channel(IntPrimaryKey, Timestamped, Base):
    __tablename__ = "channels"

    # One connected channel per account; the unique constraint enforces it.
    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    # Telegram channel ids are large and negative (-100…), hence BigInteger.
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Whether the bot could still post last time we tried. Cleared to false
    # when Telegram rejects a delivery, so the UI can prompt a re-check.
    can_post: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(String(255))
    last_posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship()

    @property
    def display(self) -> str:
        return f"@{self.username}" if self.username else self.title
