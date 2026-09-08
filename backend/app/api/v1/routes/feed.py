"""Timelines."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, OptionalUser, Paging
from app.schemas.common import Page
from app.schemas.pulse import PulseOut, TrendOut
from app.services import serializers, timelines

router = APIRouter(prefix="/feed", tags=["feed"])


def _page(items: list[PulseOut], cursor: str | None) -> Page[PulseOut]:
    return Page(items=items, next_cursor=cursor, has_more=cursor is not None)


@router.get("/home", response_model=Page[PulseOut])
async def home(user: CurrentUser, db: DbSession, paging: Paging) -> Page[PulseOut]:
    """Everything from the accounts you follow, newest first."""
    rows, cursor = await timelines.home_feed(db, user, paging.limit, paging.cursor)
    return _page(await serializers.serialize_pulses(db, rows, user.id), cursor)


@router.get("/explore", response_model=Page[PulseOut])
async def explore(db: DbSession, viewer: OptionalUser, paging: Paging) -> Page[PulseOut]:
    """The public firehose, for people who follow nobody yet."""
    rows, cursor = await timelines.explore_feed(db, viewer, paging.limit, paging.cursor)
    viewer_id = viewer.id if viewer else None
    return _page(await serializers.serialize_pulses(db, rows, viewer_id), cursor)


@router.get("/bookmarks", response_model=Page[PulseOut])
async def bookmarks(user: CurrentUser, db: DbSession, paging: Paging) -> Page[PulseOut]:
    rows, cursor = await timelines.bookmarks(db, user, paging.limit, paging.cursor)
    return _page(await serializers.serialize_pulses(db, rows, user.id), cursor)


@router.get("/trends", response_model=list[TrendOut])
async def trends(db: DbSession, limit: int = 10) -> list[TrendOut]:
    return await timelines.trending(db, limit=min(limit, 25))


@router.get("/hashtag/{tag}", response_model=Page[PulseOut])
async def by_hashtag(
    tag: str, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[PulseOut]:
    rows, cursor = await timelines.by_hashtag(db, tag, viewer, paging.limit, paging.cursor)
    viewer_id = viewer.id if viewer else None
    return _page(await serializers.serialize_pulses(db, rows, viewer_id), cursor)
