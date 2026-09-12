"""Profiles and the follow graph."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, OptionalUser, Paging
from app.core.errors import PermissionDeniedError
from app.schemas.common import CountResponse, Message, Page
from app.schemas.pulse import PulseOut
from app.schemas.user import (
    AppearanceUpdate,
    PrivacyUpdate,
    UserMe,
    UserPublic,
    UserUpdate,
)
from app.services import serializers, timelines
from app.services import users as user_service
from app.services.visibility import may_view_account

router = APIRouter(prefix="/users", tags=["users"])


async def _me(db, user) -> UserMe:
    out = UserMe.model_validate(user)
    out.pending_follow_requests = await user_service.pending_request_count(db, user.id)
    return out


@router.patch("/me", response_model=UserMe)
async def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession) -> UserMe:
    updated = await user_service.update_profile(db, user, payload)
    return await _me(db, updated)


@router.put("/me/privacy", response_model=UserMe)
async def set_privacy(payload: PrivacyUpdate, user: CurrentUser, db: DbSession) -> UserMe:
    """Protect the account, or open it up again.

    Opening it up admits everyone already waiting, since the gate they were
    queued behind no longer exists.
    """
    updated = await user_service.set_private(db, user, payload.is_private)
    return await _me(db, updated)


@router.put("/me/appearance", response_model=UserMe)
async def set_appearance(
    payload: AppearanceUpdate, user: CurrentUser, db: DbSession
) -> UserMe:
    """Set the reading text size. Applies immediately, with no Save step."""
    user.text_size = payload.text_size
    await db.commit()
    await db.refresh(user)
    return await _me(db, user)


@router.get("/me/follow-requests", response_model=Page[UserPublic])
async def list_follow_requests(
    user: CurrentUser, db: DbSession, paging: Paging
) -> Page[UserPublic]:
    rows = await user_service.list_follow_requests(
        db, user, paging.limit + 1, paging.cursor
    )
    items = rows[: paging.limit]
    has_more = len(rows) > paging.limit
    return Page(
        items=await serializers.serialize_users(db, items, user.id),
        next_cursor=str(items[-1].id) if has_more and items else None,
        has_more=has_more,
    )


@router.get("/me/follow-requests/count", response_model=CountResponse)
async def count_follow_requests(user: CurrentUser, db: DbSession) -> CountResponse:
    return CountResponse(count=await user_service.pending_request_count(db, user.id))


@router.post("/me/follow-requests/{username}/approve", response_model=Message)
async def approve_follow_request(
    username: str, user: CurrentUser, db: DbSession
) -> Message:
    requester = await user_service.get_by_username(db, username)
    done = await user_service.approve_follow_request(db, user, requester.id)
    return Message(message="Approved." if done else "No pending request.")


@router.post("/me/follow-requests/{username}/decline", response_model=Message)
async def decline_follow_request(
    username: str, user: CurrentUser, db: DbSession
) -> Message:
    requester = await user_service.get_by_username(db, username)
    done = await user_service.decline_follow_request(db, user, requester.id)
    return Message(message="Declined." if done else "No pending request.")


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
    outcome = await user_service.follow(db, user, target.id)
    return Message(
        message={
            "following": "Followed.",
            "requested": "Follow request sent.",
            "already_following": "Already following.",
            "already_requested": "Request already sent.",
        }[outcome]
    )


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
    await _gate(db, target, viewer)
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
    await _gate(db, target, viewer)
    rows = await user_service.list_following(db, target.id, paging.limit + 1, paging.cursor)
    items = rows[: paging.limit]
    has_more = len(rows) > paging.limit
    return Page(
        items=await serializers.serialize_users(db, items, viewer.id if viewer else None),
        next_cursor=str(items[-1].id) if has_more and items else None,
        has_more=has_more,
    )


async def _gate(db, target, viewer) -> None:
    """Refuse a protected account's pulses to anyone it has not admitted."""
    if not await may_view_account(db, target, viewer.id if viewer else None):
        raise PermissionDeniedError(
            "This account is protected. Follow it to see its pulses.",
            code="protected_account",
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
    await _gate(db, target, viewer)
    rows, cursor = await timelines.user_pulses(
        db, target, viewer, paging.limit, paging.cursor
    )
    return await _page(db, rows, cursor, viewer)


@router.get("/{username}/replies", response_model=Page[PulseOut])
async def user_replies(
    username: str, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[PulseOut]:
    target = await user_service.get_by_username(db, username)
    await _gate(db, target, viewer)
    rows, cursor = await timelines.user_replies(
        db, target, viewer, paging.limit, paging.cursor
    )
    return await _page(db, rows, cursor, viewer)


@router.get("/{username}/media", response_model=Page[PulseOut])
async def user_media(
    username: str, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[PulseOut]:
    target = await user_service.get_by_username(db, username)
    await _gate(db, target, viewer)
    rows, cursor = await timelines.user_media(
        db, target, viewer, paging.limit, paging.cursor
    )
    return await _page(db, rows, cursor, viewer)


@router.get("/{username}/channel", response_model=Page[PulseOut])
async def user_channel_archive(
    username: str, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[PulseOut]:
    """Posts imported from this account's Telegram channel."""
    target = await user_service.get_by_username(db, username)
    await _gate(db, target, viewer)
    rows, cursor = await timelines.channel_archive(
        db, target, viewer, paging.limit, paging.cursor
    )
    return await _page(db, rows, cursor, viewer)


@router.get("/{username}/likes", response_model=Page[PulseOut])
async def user_likes(
    username: str, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[PulseOut]:
    target = await user_service.get_by_username(db, username)
    await _gate(db, target, viewer)
    rows, cursor = await timelines.user_likes(
        db, target, viewer, paging.limit, paging.cursor
    )
    return await _page(db, rows, cursor, viewer)
