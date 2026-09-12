"""Pulse payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.schemas.common import ORMModel
from app.schemas.user import UserSummary


class MediaOut(ORMModel):
    id: int
    url: str
    mime_type: str
    width: int | None = None
    height: int | None = None
    alt_text: str | None = None


class PulseCreate(BaseModel):
    content: str = Field(default="", max_length=settings.MAX_PULSE_LENGTH)
    reply_to_id: int | None = None
    quote_of_id: int | None = None
    media_ids: list[int] = Field(
        default_factory=list, max_length=settings.MAX_MEDIA_PER_PULSE
    )
    # Opt in per pulse: the composer asks "also post to @channel?" each time,
    # so mirroring is never a silent default.
    post_to_channel: bool = False

    @model_validator(mode="after")
    def _check(self) -> PulseCreate:
        if self.reply_to_id and self.quote_of_id:
            raise ValueError("A pulse cannot be both a reply and a quote.")
        if not self.content.strip() and not self.media_ids:
            raise ValueError("A pulse needs text or an image.")
        return self


class PulseRef(ORMModel):
    """A parent pulse rendered inline, without recursing any further."""

    id: int
    content: str
    author: UserSummary
    created_at: datetime
    media: list[MediaOut] = Field(default_factory=list)
    is_deleted: bool = False


class ChannelReaction(BaseModel):
    emoji: str
    count: int


class PulseOut(ORMModel):
    id: int
    content: str
    author: UserSummary
    created_at: datetime

    reply_to_id: int | None = None
    quote_of_id: int | None = None

    like_count: int = 0
    reply_count: int = 0
    repulse_count: int = 0
    quote_count: int = 0
    bookmark_count: int = 0
    view_count: int = 0

    media: list[MediaOut] = Field(default_factory=list)
    quote_of: PulseRef | None = None
    reply_to: PulseRef | None = None

    # Relative to the caller.
    is_liked: bool = False
    is_repulsed: bool = False
    is_bookmarked: bool = False
    is_mine: bool = False

    # Set when this timeline entry is somebody's repost of the pulse above.
    repulsed_by: UserSummary | None = None

    # Whether this pulse was mirrored into the author's channel.
    sent_to_channel: bool = False

    # Set when the pulse was imported from a Telegram channel rather than
    # written here, along with the reactions it carried across.
    is_imported: bool = False
    source_date: datetime | None = None
    reactions: list[ChannelReaction] = Field(default_factory=list)


class ThreadOut(BaseModel):
    """A pulse with its ancestors and its immediate replies."""

    ancestors: list[PulseOut]
    pulse: PulseOut
    replies: list[PulseOut]
    replies_next_cursor: str | None = None


class TrendOut(BaseModel):
    tag: str
    pulse_count: int
    rank: int


FeedKind = Literal["home", "explore"]
