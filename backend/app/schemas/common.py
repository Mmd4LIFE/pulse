"""Shared response envelopes."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    """Cursor-paginated results.

    Timelines are ordered by a monotonic id, so the cursor is just the last id
    seen. That keeps paging stable while new pulses arrive at the head, which
    offset paging cannot do.
    """

    items: list[T]
    next_cursor: str | None = Field(
        default=None, description="Pass as ?cursor= to fetch the next page."
    )
    has_more: bool = False


class Message(BaseModel):
    message: str


class CountResponse(BaseModel):
    count: int
