"""Edges between accounts and pulses: follows, likes, bookmarks, blocks."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Follow(Base):
    __tablename__ = "follows"

    follower_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    followee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("follower_id <> followee_id", name="no_self_follow"),
        # "Who follows this account", newest first.
        Index("ix_follows_followee_created", "followee_id", "created_at"),
    )


class Like(Base):
    __tablename__ = "likes"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    pulse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pulses.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Drives the "liked" tab and the per-pulse liker list.
        Index("ix_likes_user_created", "user_id", "created_at"),
        Index("ix_likes_pulse", "pulse_id"),
    )


class Bookmark(Base):
    __tablename__ = "bookmarks"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    pulse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pulses.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_bookmarks_user_created", "user_id", "created_at"),)


class Block(Base):
    """A block hides both accounts from each other across every timeline."""

    __tablename__ = "blocks"

    blocker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    blocked_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("blocker_id <> blocked_id", name="no_self_block"),
        Index("ix_blocks_blocked", "blocked_id"),
    )
