"""The character behind an automated account.

An automated account is an ordinary ``User`` row -- it posts, follows, is
followed, and is read through exactly the same code paths as anyone else. This
table is what makes it act: who it is, what it talks about, and how often.

Keeping the two apart matters. Nothing in the timeline, privacy or notification
logic has to know that automation exists, so there is no second set of rules to
keep in step with the first.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntPrimaryKey, Timestamped

if TYPE_CHECKING:
    from app.models.user import User


class Persona(IntPrimaryKey, Timestamped, Base):
    __tablename__ = "personas"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # What the account is about, and who it reads as. The character is written
    # once at creation and then used as the system prompt for everything it
    # says, so its voice stays consistent across posts and replies.
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    character: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(
        String(8), server_default=text("'en'"), nullable=False
    )

    # --- behaviour ---------------------------------------------------------
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False, index=True
    )
    # Roughly how long between posts. The worker jitters around this so a group
    # of accounts created together does not post in lockstep.
    post_every_minutes: Mapped[int] = mapped_column(
        Integer, server_default=text("180"), nullable=False
    )
    # Chance of each engagement per tick, once the account is awake.
    reply_chance: Mapped[float] = mapped_column(
        Float, server_default=text("0.25"), nullable=False
    )
    like_chance: Mapped[float] = mapped_column(
        Float, server_default=text("0.5"), nullable=False
    )
    repulse_chance: Mapped[float] = mapped_column(
        Float, server_default=text("0.08"), nullable=False
    )

    # --- bookkeeping -------------------------------------------------------
    last_posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posts_made: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    replies_made: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    tokens_used: Mapped[int] = mapped_column(
        BigInteger, server_default=text("0"), nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "reply_chance BETWEEN 0 AND 1"
            " AND like_chance BETWEEN 0 AND 1"
            " AND repulse_chance BETWEEN 0 AND 1",
            name="chances_are_probabilities",
        ),
        CheckConstraint("post_every_minutes >= 5", name="cadence_is_sane"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Persona {self.id} user={self.user_id} topic={self.topic!r}>"
