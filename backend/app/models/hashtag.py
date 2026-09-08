"""Hashtags and the pulses that carry them."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntPrimaryKey


class Hashtag(IntPrimaryKey, Base):
    __tablename__ = "hashtags"

    # Stored case-folded so that #Pulse and #pulse are one trend.
    tag: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    usage_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PulseHashtag(Base):
    __tablename__ = "pulse_hashtags"

    pulse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pulses.id", ondelete="CASCADE"), primary_key=True
    )
    hashtag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hashtags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        # Trend window scan: recent uses of each tag.
        Index("ix_pulse_hashtags_tag_created", "hashtag_id", "created_at"),
    )


class Mention(Base):
    __tablename__ = "mentions"

    pulse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pulses.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index("ix_mentions_user", "user_id"),)
