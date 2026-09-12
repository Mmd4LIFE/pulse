"""A pulse: the post, the reply, the quote, and the repost are all one row.

Modelling all four as a single table keeps the timeline a single scan over one
index. Which of the four a row is, is determined by the three nullable parent
columns:

===========  ================  ==================  ================
kind         reply_to_id       repulse_of_id       quote_of_id
===========  ================  ==================  ================
post         NULL              NULL                NULL
reply        set               NULL                NULL
repost       NULL              set                 NULL
quote        NULL              NULL                set
===========  ================  ==================  ================
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntPrimaryKey, Timestamped

if TYPE_CHECKING:
    from app.models.media import Media
    from app.models.user import User


class Pulse(IntPrimaryKey, Timestamped, Base):
    __tablename__ = "pulses"

    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(String(280), nullable=False, server_default="")

    reply_to_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pulses.id", ondelete="CASCADE")
    )
    repulse_of_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pulses.id", ondelete="CASCADE")
    )
    quote_of_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pulses.id", ondelete="CASCADE")
    )

    # Root of the thread this pulse belongs to; equals ``id`` for a top-level
    # pulse. Lets a whole conversation be fetched with one indexed lookup.
    conversation_id: Mapped[int | None] = mapped_column(BigInteger, index=True)

    like_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    reply_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    repulse_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    quote_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    bookmark_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    view_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )

    # Soft delete: a deleted parent must still anchor its replies in a thread.
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_sensitive: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    # Set once the pulse has been mirrored into the author's channel. Delivery
    # happens after the response is sent, so this is false at creation time.
    sent_to_channel: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )

    # --- imported from a Telegram channel --------------------------------
    # Set when the pulse came out of a channel export rather than being
    # written here. The pair is unique, so re-importing an export updates
    # what is already stored instead of duplicating the channel.
    source_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    source_message_id: Mapped[int | None] = mapped_column(BigInteger)
    # When it was posted to the channel, which is what the UI shows rather
    # than the moment the import happened to run.
    source_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The channel's own reactions, carried across as they were:
    # [{"emoji": "👍", "count": 12}, ...]
    reactions: Mapped[list | None] = mapped_column(JSONB)

    author: Mapped[User] = relationship(
        back_populates="pulses", foreign_keys=[author_id], lazy="joined"
    )
    reply_to: Mapped[Pulse | None] = relationship(
        remote_side="Pulse.id", foreign_keys=[reply_to_id]
    )
    repulse_of: Mapped[Pulse | None] = relationship(
        remote_side="Pulse.id", foreign_keys=[repulse_of_id]
    )
    quote_of: Mapped[Pulse | None] = relationship(
        remote_side="Pulse.id", foreign_keys=[quote_of_id]
    )
    media: Mapped[list[Media]] = relationship(
        back_populates="pulse", order_by="Media.position", lazy="selectin"
    )

    __table_args__ = (
        # A pulse is at most one of reply / repost / quote.
        CheckConstraint(
            "(reply_to_id IS NOT NULL)::int"
            " + (repulse_of_id IS NOT NULL)::int"
            " + (quote_of_id IS NOT NULL)::int <= 1",
            name="single_parent",
        ),
        # A repost carries no text of its own; a quote must say something.
        CheckConstraint(
            "repulse_of_id IS NULL OR content = ''", name="repost_has_no_content"
        ),
        # Author timeline, newest first.
        Index("ix_pulses_author_created", "author_id", text("created_at DESC")),
        # Reverse-chronological home/explore scans skip soft-deleted rows.
        Index(
            "ix_pulses_live_created",
            text("created_at DESC"),
            postgresql_where=text("is_deleted = false"),
        ),
        Index("ix_pulses_reply_to_created", "reply_to_id", text("created_at DESC")),
        # One repost of a given pulse per account.
        Index(
            "uq_pulses_author_repulse",
            "author_id",
            "repulse_of_id",
            unique=True,
            postgresql_where=text("repulse_of_id IS NOT NULL"),
        ),
        # Makes re-importing an export idempotent rather than duplicating it.
        Index(
            "uq_pulses_source_message",
            "source_channel_id",
            "source_message_id",
            unique=True,
            postgresql_where=text("source_channel_id IS NOT NULL"),
        ),
        # The profile's Channel tab, newest post first.
        Index(
            "ix_pulses_source_date",
            "author_id",
            text("source_date DESC"),
            postgresql_where=text("source_channel_id IS NOT NULL"),
        ),
    )

    @property
    def is_imported(self) -> bool:
        return self.source_channel_id is not None

    @property
    def is_repost(self) -> bool:
        return self.repulse_of_id is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Pulse {self.id} by {self.author_id}>"
