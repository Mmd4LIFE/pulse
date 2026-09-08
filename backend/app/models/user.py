"""The Pulse account, which is always backed by a Telegram identity."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntPrimaryKey, Timestamped

if TYPE_CHECKING:
    from app.models.pulse import Pulse


class User(IntPrimaryKey, Timestamped, Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    # The @handle within Pulse. Seeded from the Telegram username when free.
    username: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    bio: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(64))
    website: Mapped[str | None] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    banner_url: Mapped[str | None] = mapped_column(String(512))

    telegram_username: Mapped[str | None] = mapped_column(String(64))
    language_code: Mapped[str | None] = mapped_column(String(8))
    is_telegram_premium: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )

    # Denormalised counters. Kept in step by the service layer so that timeline
    # rendering never needs an aggregate query per row.
    followers_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    following_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    pulses_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pulses: Mapped[list[Pulse]] = relationship(
        back_populates="author",
        foreign_keys="Pulse.author_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.id} @{self.username}>"
