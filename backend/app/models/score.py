"""Scores given to a pulse.

A row per verdict rather than a column on ``pulses``, because a score is a
thing in its own right and is expected to grow: where it came from, which model
gave it, and -- if rating ever replaces liking -- one row per person who rated,
with the number shown on the pulse being what those rows average.

Today there is one source and one row per pulse, but nothing here assumes that.
"""

from __future__ import annotations

import enum
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntPrimaryKey, Timestamped

if TYPE_CHECKING:
    from app.models.pulse import Pulse
    from app.models.user import User


class ScoreSource(str, enum.Enum):
    """Who gave the score."""

    AI = "ai"
    HUMAN = "human"


class PulseScore(IntPrimaryKey, Timestamped, Base):
    __tablename__ = "pulse_scores"

    pulse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pulses.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[ScoreSource] = mapped_column(
        Enum(ScoreSource, name="score_source", native_enum=True), nullable=False
    )
    # Set when a person gave the score; null for the model's own.
    rater_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE")
    )

    # 0.0 to 10.0. Numeric rather than a float: the value is shown verbatim and
    # 8.8 should stay 8.8.
    value: Mapped[Decimal] = mapped_column(Numeric(3, 1), nullable=False)

    # Which model produced it, so a change of model is visible in the data
    # rather than being something you have to remember.
    model: Mapped[str | None] = mapped_column(String(64))

    pulse: Mapped[Pulse] = relationship(back_populates="scores")
    rater: Mapped[User | None] = relationship()

    __table_args__ = (
        # A pulse's scores are read a page at a time, by pulse.
        Index("ix_pulse_scores_pulse_created", "pulse_id", text("created_at DESC")),
        # The model gets one say per pulse...
        Index(
            "uq_pulse_scores_ai",
            "pulse_id",
            unique=True,
            postgresql_where=text("rater_id IS NULL"),
        ),
        # ...and so, when people can rate, does each person.
        Index(
            "uq_pulse_scores_rater",
            "pulse_id",
            "rater_id",
            unique=True,
            postgresql_where=text("rater_id IS NOT NULL"),
        ),
    )
