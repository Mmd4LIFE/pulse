"""Posting, reading, and reacting to pulses."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, status

from app.api.deps import CurrentUser, DbSession, OptionalUser, Paging
from app.core.errors import PermissionDeniedError
from app.schemas.common import Message, Page
from app.schemas.pulse import PulseCreate, PulseOut, ThreadOut
from app.services import channels as channel_service
from app.services import pulses as pulse_service
from app.services import serializers, timelines
from app.services.visibility import may_view_pulse

router = APIRouter(prefix="/pulses", tags=["pulses"])


async def _gate(db, pulse, viewer) -> None:
    """Refuse a protected account's pulse to anyone it has not admitted."""
    if not await may_view_pulse(db, pulse, viewer.id if viewer else None):
        raise PermissionDeniedError(
            "This pulse belongs to a protected account.", code="protected_account"
        )


async def _one(db, pulse, viewer) -> PulseOut:
    items = await serializers.serialize_pulses(db, [pulse], viewer.id if viewer else None)
    return items[0]


@router.post("", response_model=PulseOut, status_code=status.HTTP_201_CREATED)
async def create_pulse(
    payload: PulseCreate,
    user: CurrentUser,
    db: DbSession,
    background: BackgroundTasks,
) -> PulseOut:
    pulse = await pulse_service.create_pulse(db, user, payload)

    # Mirroring is opt-in per pulse and runs after the response, so a slow or
    # failing Telegram call never delays or fails the post itself.
    if payload.post_to_channel:
        channel = await channel_service.get_for(db, user.id)
        if channel is not None:
            background.add_task(channel_service.deliver_in_background, pulse.id, user.id)

    return await _one(db, pulse, user)


@router.get("/{pulse_id}", response_model=PulseOut)
async def read_pulse(pulse_id: int, db: DbSession, viewer: OptionalUser) -> PulseOut:
    pulse = await pulse_service.get_pulse(db, pulse_id)
    await _gate(db, pulse, viewer)
    return await _one(db, pulse, viewer)


@router.get("/{pulse_id}/thread", response_model=ThreadOut)
async def read_thread(
    pulse_id: int, db: DbSession, viewer: OptionalUser, paging: Paging
) -> ThreadOut:
    """The pulse, the chain of replies above it, and its direct replies."""
    pulse = await pulse_service.get_pulse(db, pulse_id)
    await _gate(db, pulse, viewer)
    ancestors = await timelines.ancestors_of(db, pulse)
    replies, cursor = await timelines.replies_to(
        db, pulse_id, viewer, paging.limit, paging.cursor
    )

    viewer_id = viewer.id if viewer else None
    return ThreadOut(
        ancestors=await serializers.serialize_pulses(db, ancestors, viewer_id),
        pulse=(await serializers.serialize_pulses(db, [pulse], viewer_id))[0],
        replies=await serializers.serialize_pulses(db, replies, viewer_id),
        replies_next_cursor=cursor,
    )


@router.get("/{pulse_id}/replies", response_model=Page[PulseOut])
async def read_replies(
    pulse_id: int, db: DbSession, viewer: OptionalUser, paging: Paging
) -> Page[PulseOut]:
    await _gate(db, await pulse_service.get_pulse(db, pulse_id), viewer)
    rows, cursor = await timelines.replies_to(
        db, pulse_id, viewer, paging.limit, paging.cursor
    )
    return Page(
        items=await serializers.serialize_pulses(db, rows, viewer.id if viewer else None),
        next_cursor=cursor,
        has_more=cursor is not None,
    )


@router.delete("/{pulse_id}", response_model=Message)
async def delete_pulse(pulse_id: int, user: CurrentUser, db: DbSession) -> Message:
    await pulse_service.delete_pulse(db, user, pulse_id)
    return Message(message="Pulse deleted.")


@router.post("/{pulse_id}/like", response_model=Message)
async def like_pulse(pulse_id: int, user: CurrentUser, db: DbSession) -> Message:
    created = await pulse_service.like(db, user, pulse_id)
    return Message(message="Liked." if created else "Already liked.")


@router.delete("/{pulse_id}/like", response_model=Message)
async def unlike_pulse(pulse_id: int, user: CurrentUser, db: DbSession) -> Message:
    removed = await pulse_service.unlike(db, user, pulse_id)
    return Message(message="Unliked." if removed else "Was not liked.")


@router.post("/{pulse_id}/repulse", response_model=Message)
async def repulse_pulse(pulse_id: int, user: CurrentUser, db: DbSession) -> Message:
    created = await pulse_service.repulse(db, user, pulse_id)
    return Message(message="Repulsed." if created else "Already repulsed.")


@router.delete("/{pulse_id}/repulse", response_model=Message)
async def unrepulse_pulse(pulse_id: int, user: CurrentUser, db: DbSession) -> Message:
    removed = await pulse_service.unrepulse(db, user, pulse_id)
    return Message(message="Repulse removed." if removed else "Was not repulsed.")


@router.post("/{pulse_id}/bookmark", response_model=Message)
async def bookmark_pulse(pulse_id: int, user: CurrentUser, db: DbSession) -> Message:
    created = await pulse_service.bookmark(db, user, pulse_id)
    return Message(message="Bookmarked." if created else "Already bookmarked.")


@router.delete("/{pulse_id}/bookmark", response_model=Message)
async def unbookmark_pulse(pulse_id: int, user: CurrentUser, db: DbSession) -> Message:
    removed = await pulse_service.unbookmark(db, user, pulse_id)
    return Message(message="Bookmark removed." if removed else "Was not bookmarked.")


@router.post(
    "/{pulse_id}/view", response_model=Message, status_code=status.HTTP_202_ACCEPTED
)
async def register_view(pulse_id: int, db: DbSession) -> Message:
    await pulse_service.register_view(db, pulse_id)
    return Message(message="Recorded.")
