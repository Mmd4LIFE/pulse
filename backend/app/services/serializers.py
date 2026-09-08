"""Turning ORM rows into API payloads.

Every timeline response goes through here. The viewer-relative flags
(``is_liked``, ``is_bookmarked``, ``is_repulsed``) are resolved for a whole page
in three set-membership queries rather than three queries per row, which is what
keeps a 30-item feed at a constant number of round trips.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Bookmark, Follow, Like, Media, Pulse, User
from app.schemas.pulse import MediaOut, PulseOut, PulseRef
from app.schemas.user import UserPublic, UserSummary


def media_url(item: Media) -> str:
    return f"{settings.MEDIA_URL_PREFIX}/{item.storage_key}"


def to_media_out(items: Iterable[Media]) -> list[MediaOut]:
    return [
        MediaOut(
            id=m.id,
            url=media_url(m),
            mime_type=m.mime_type,
            width=m.width,
            height=m.height,
            alt_text=m.alt_text,
        )
        for m in items
    ]


def to_user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_verified=user.is_verified,
    )


def to_pulse_ref(pulse: Pulse | None) -> PulseRef | None:
    if pulse is None:
        return None
    if pulse.is_deleted:
        # Keep the thread's shape but reveal nothing about removed content.
        return PulseRef(
            id=pulse.id,
            content="",
            author=to_user_summary(pulse.author),
            created_at=pulse.created_at,
            media=[],
            is_deleted=True,
        )
    return PulseRef(
        id=pulse.id,
        content=pulse.content,
        author=to_user_summary(pulse.author),
        created_at=pulse.created_at,
        media=to_media_out(pulse.media),
        is_deleted=False,
    )


class ViewerContext:
    """The caller's relationship to a specific page of pulses."""

    __slots__ = ("bookmarked", "liked", "repulsed", "viewer_id")

    def __init__(
        self,
        viewer_id: int | None,
        liked: set[int] | None = None,
        bookmarked: set[int] | None = None,
        repulsed: set[int] | None = None,
    ) -> None:
        self.viewer_id = viewer_id
        self.liked = liked or set()
        self.bookmarked = bookmarked or set()
        self.repulsed = repulsed or set()


async def build_viewer_context(
    db: AsyncSession, viewer_id: int | None, pulse_ids: Sequence[int]
) -> ViewerContext:
    if viewer_id is None or not pulse_ids:
        return ViewerContext(viewer_id)

    ids = list(set(pulse_ids))

    liked = set(
        (
            await db.scalars(
                select(Like.pulse_id).where(
                    Like.user_id == viewer_id, Like.pulse_id.in_(ids)
                )
            )
        ).all()
    )
    bookmarked = set(
        (
            await db.scalars(
                select(Bookmark.pulse_id).where(
                    Bookmark.user_id == viewer_id, Bookmark.pulse_id.in_(ids)
                )
            )
        ).all()
    )
    repulsed = set(
        (
            await db.scalars(
                select(Pulse.repulse_of_id).where(
                    Pulse.author_id == viewer_id,
                    Pulse.repulse_of_id.in_(ids),
                    Pulse.is_deleted.is_(False),
                )
            )
        ).all()
    )
    return ViewerContext(viewer_id, liked, bookmarked, repulsed)


def to_pulse_out(
    pulse: Pulse,
    ctx: ViewerContext,
    *,
    repulsed_by: User | None = None,
) -> PulseOut:
    return PulseOut(
        id=pulse.id,
        content="" if pulse.is_deleted else pulse.content,
        author=to_user_summary(pulse.author),
        created_at=pulse.created_at,
        reply_to_id=pulse.reply_to_id,
        quote_of_id=pulse.quote_of_id,
        like_count=pulse.like_count,
        reply_count=pulse.reply_count,
        repulse_count=pulse.repulse_count,
        quote_count=pulse.quote_count,
        bookmark_count=pulse.bookmark_count,
        view_count=pulse.view_count,
        media=[] if pulse.is_deleted else to_media_out(pulse.media),
        quote_of=to_pulse_ref(pulse.quote_of),
        reply_to=to_pulse_ref(pulse.reply_to),
        is_liked=pulse.id in ctx.liked,
        is_repulsed=pulse.id in ctx.repulsed,
        is_bookmarked=pulse.id in ctx.bookmarked,
        is_mine=ctx.viewer_id is not None and pulse.author_id == ctx.viewer_id,
        repulsed_by=to_user_summary(repulsed_by) if repulsed_by else None,
    )


async def serialize_pulses(
    db: AsyncSession, pulses: Sequence[Pulse], viewer_id: int | None
) -> list[PulseOut]:
    """Serialize a page of pulses, resolving a repost to the pulse it points at."""
    # A repost row renders as the original pulse, credited to the reposter.
    display: list[tuple[Pulse, User | None]] = []
    for p in pulses:
        if p.repulse_of_id and p.repulse_of is not None:
            display.append((p.repulse_of, p.author))
        else:
            display.append((p, None))

    ctx = await build_viewer_context(db, viewer_id, [d.id for d, _ in display])
    return [to_pulse_out(d, ctx, repulsed_by=by) for d, by in display]


async def serialize_user(db: AsyncSession, user: User, viewer_id: int | None) -> UserPublic:
    out = UserPublic.model_validate(user)
    if viewer_id is None or viewer_id == user.id:
        return out

    edges = (
        await db.execute(
            select(Follow.follower_id, Follow.followee_id).where(
                Follow.follower_id.in_([viewer_id, user.id]),
                Follow.followee_id.in_([viewer_id, user.id]),
            )
        )
    ).all()
    for follower_id, followee_id in edges:
        if follower_id == viewer_id:
            out.is_following = True
        if followee_id == viewer_id:
            out.is_followed_by = True
    return out


async def serialize_users(
    db: AsyncSession, users: Sequence[User], viewer_id: int | None
) -> list[UserPublic]:
    outs = [UserPublic.model_validate(u) for u in users]
    if viewer_id is None or not users:
        return outs

    ids = [u.id for u in users]
    following = set(
        (
            await db.scalars(
                select(Follow.followee_id).where(
                    Follow.follower_id == viewer_id, Follow.followee_id.in_(ids)
                )
            )
        ).all()
    )
    followers = set(
        (
            await db.scalars(
                select(Follow.follower_id).where(
                    Follow.followee_id == viewer_id, Follow.follower_id.in_(ids)
                )
            )
        ).all()
    )
    for out in outs:
        out.is_following = out.id in following
        out.is_followed_by = out.id in followers
    return outs
