"""Search."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import DbSession, OptionalUser, Paging
from app.schemas.common import Page
from app.schemas.pulse import PulseOut
from app.schemas.user import UserPublic
from app.services import search as search_service
from app.services import serializers

router = APIRouter(prefix="/search", tags=["search"])


class HashtagResult(BaseModel):
    tag: str
    usage_count: int


class SearchResults(BaseModel):
    users: list[UserPublic]
    pulses: list[PulseOut]
    hashtags: list[HashtagResult]


@router.get("", response_model=SearchResults)
async def search_everything(
    db: DbSession,
    viewer: OptionalUser,
    q: str = Query(min_length=1, max_length=100),
) -> SearchResults:
    """A blended result set for the search screen's landing state."""
    viewer_id = viewer.id if viewer else None
    users = await search_service.search_users(db, q, viewer, 5, None)
    pulses, _ = await search_service.search_pulses(db, q, viewer, 10, None)
    hashtags = await search_service.search_hashtags(db, q, 5)
    return SearchResults(
        users=await serializers.serialize_users(db, users, viewer_id),
        pulses=await serializers.serialize_pulses(db, pulses, viewer_id),
        hashtags=[HashtagResult(tag=h.tag, usage_count=h.usage_count) for h in hashtags],
    )


@router.get("/users", response_model=Page[UserPublic])
async def search_users(
    db: DbSession,
    viewer: OptionalUser,
    paging: Paging,
    q: str = Query(min_length=1, max_length=100),
) -> Page[UserPublic]:
    rows = await search_service.search_users(db, q, viewer, paging.limit + 1, paging.cursor)
    items = rows[: paging.limit]
    has_more = len(rows) > paging.limit
    return Page(
        items=await serializers.serialize_users(db, items, viewer.id if viewer else None),
        next_cursor=str(items[-1].id) if has_more and items else None,
        has_more=has_more,
    )


@router.get("/pulses", response_model=Page[PulseOut])
async def search_pulses(
    db: DbSession,
    viewer: OptionalUser,
    paging: Paging,
    q: str = Query(min_length=1, max_length=100),
) -> Page[PulseOut]:
    rows, cursor = await search_service.search_pulses(
        db, q, viewer, paging.limit, paging.cursor
    )
    return Page(
        items=await serializers.serialize_pulses(db, rows, viewer.id if viewer else None),
        next_cursor=cursor,
        has_more=cursor is not None,
    )
