"""Uploaded images attached to a pulse."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntPrimaryKey, Timestamped

if TYPE_CHECKING:
    from app.models.pulse import Pulse


class Media(IntPrimaryKey, Timestamped, Base):
    __tablename__ = "media"

    uploader_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Null until the upload is attached to a pulse; unattached rows are
    # collected by the media cleanup job.
    pulse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pulses.id", ondelete="CASCADE"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    alt_text: Mapped[str | None] = mapped_column(String(420))
    position: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)

    pulse: Mapped[Pulse | None] = relationship(back_populates="media")
