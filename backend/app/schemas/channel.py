"""Connected-channel payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ChannelConnect(BaseModel):
    reference: str = Field(
        ...,
        max_length=128,
        description="Channel @username, a t.me link, or a numeric -100… chat id.",
    )


class ChannelOut(ORMModel):
    id: int
    chat_id: int
    username: str | None = None
    title: str
    can_post: bool
    last_error: str | None = None
    last_posted_at: datetime | None = None

    # Progress of the last history import.
    import_status: str = "idle"
    import_total: int = 0
    import_done: int = 0
    import_error: str | None = None
    imported_at: datetime | None = None

    @property
    def display(self) -> str:
        return f"@{self.username}" if self.username else self.title
