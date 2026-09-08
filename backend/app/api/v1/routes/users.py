"""Profiles and the follow graph."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, OptionalUser, Paging
from app.schemas.common import Message, Page
from app.schemas.pulse import PulseOut
from app.schemas.user import UserMe, UserPublic, UserUpdate
from app.services import serializers, timelines
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserMe)
async def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession) -> UserMe:
    updated = await user_service.update_profile(db, user, payload)
    return UserMe.model_validate(updated)


@router.get("/suggestions", response_model=list[UserPublic])
async def follow_suggestions(
    db: DbSession, viewer: OptionalUser, limit: int = 5
) -> list[UserPublic]:
    found = await user_service.suggestions(db, viewer, min(limit, 20))
    return await serializers.serialize_users(db, found, viewer.id if viewer else None)


@router.get("/{username}", response_model=UserPublic)
async def read_profile(username: str, db: DbSession, viewer: OptionalUser) -> UserPublic:
    user = await user_service.get_by_username(db, username)
    return await serializers.serialize_user(db, user, viewer.id if viewer else None)


@router.post("/{username}/follow", response_model=Message)
async def follow_user(username: str, user: CurrentUser, db: DbSession) -> Message:
    target = await user_service.get_by_username(db, username)
    created = await user_service.follow(db, user, target.id)
    return Message(message="Followed." if created else "Already following.")


@router.delete("/{username}/follow", response_model=Message)
async def unfollow_user(username: str, user: CurrentUser, db: DbSession) -> Message:
    target = await user_service.get_by_username(db, username)
    removed = await user_service.unfollow(db, user, target.id)
    return Message(message="Unfollowed." if removed else "Was not following.")


@router.post("/{username}/block", response_model=Message)
async def block_user(username: str, user: CurrentUser, db: DbSession) -> Message:
    target = await user_service.get_by_username(db, username)
    created = await user_service.block(db, user, target.id)
    return Message(message="Blocked." if created else "Already blocked.")


@router.delete("/{username}/block", response_model=Message)
async def unblock_user(username: str, user: CurrentUser, db: DbSession) -> Message:
    target = await user_service.get_by_username(db, username)
    removed = await user_service.unblock(db, user, target.id)
    return Message(message="Unblocked." if removed else "Was not blocked.")


@router.get("/{username}/followers", response_model=Page[UserPublic])
async def list_followers(
    username: str, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[UserPublic]:
    target = await user_service.get_by_username(db, username)
    rows = await user_service.list_followers(db, target.id, paging.limit + 1, paging.cursor)
    items = rows[: paging.limit]
    has_more = len(rows) > paging.limit
    return Page(
        items=await serializers.serialize_users(db, items, viewer.id if viewer else None),
        next_cursor=str(items[-1].id) if has_more and items else None,
        has_more=has_more,
    )


@router.get("/{username}/following", response_model=Page[UserPublic])
async def list_following(
    username: str, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[UserPublic]:
    target = await user_service.get_by_username(db, username)
    rows = await user_service.list_following(db, target.id, paging.limit + 1, paging.cursor)
    items = rows[: paging.limit]
    has_more = len(rows) > paging.limit
    return Page(
        items=await serializers.serialize_users(db, items, viewer.id if viewer else None),
        next_cursor=str(items[-1].id) if has_more and items else None,
        has_more=has_more,
    )


async def _page(db, rows, cursor, viewer) -> Page[PulseOut]:
    return Page(
        items=await serializers.serialize_pulses(db, rows, viewer.id if viewer else None),
        next_cursor=cursor,
        has_more=cursor is not None,
    )


@router.get("/{username}/pulses", response_model=Page[PulseOut])
async def user_pulses(
    username: str, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[PulseOut]:
    target = await user_service.get_by_username(db, username)
    rows, cursor = await timelines.user_pulses(
        db, target, viewer, paging.limit, paging.cursor
    )
    return await _page(db, rows, cursor, viewer)


@router.get("/{username}/replies", response_model=Page[PulseOut])
async def user_replies(
    username: str, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[PulseOut]:
    target = await user_service.get_by_username(db, username)
    rows, cursor = await timelines.user_replies(
        db, target, viewer, paging.limit, paging.cursor
    )
    return await _page(db, rows, cursor, viewer)


@router.get("/{username}/media", response_model=Page[PulseOut])
async def user_media(
    username: str, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[PulseOut]:
    target = await user_service.get_by_username(db, username)
    rows, cursor = await timelines.user_media(
        db, target, viewer, paging.limit, paging.cursor
    )
    return await _page(db, rows, cursor, viewer)


@router.get("/{username}/likes", response_model=Page[PulseOut])
async def user_likes(
    username: str, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[PulseOut]:
    target = await user_service.get_by_username(db, username)
    rows, cursor = await timelines.user_likes(
        db, target, viewer, paging.limit, paging.cursor
    )
    return await _page(db, rows, cursor, viewer)
