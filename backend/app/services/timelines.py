"""Feed and timeline queries.

All timelines page on the pulse id rather than an offset: ids are monotonic, so
a cursor stays correct even as new pulses land at the head of the feed.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Bookmark,
    Follow,
    Hashtag,
    Like,
    Pulse,
    PulseHashtag,
    User,
)
from app.schemas.pulse import TrendOut
from app.services import users as user_service
from app.services.pulses import _load_options
from app.services.visibility import restrict_to_visible


def _base(viewer_hidden: Sequence[int]) -> Select:
    stmt = (
        select(Pulse)
        .options(*_load_options())
        .where(Pulse.is_deleted.is_(False))
        .order_by(Pulse.id.desc())
    )
    if viewer_hidden:
        stmt = stmt.where(Pulse.author_id.not_in(viewer_hidden))
    return stmt


def _is_orphan_repost(pulse: Pulse) -> bool:
    """True when a repost has nothing left to point at.

    Covers both a hard-deleted original and a soft-deleted one: the latter is
    still loadable, so checking only for a missing row let deleted pulses
    render as empty cards.
    """
    if not pulse.repulse_of_id:
        return False
    return pulse.repulse_of is None or pulse.repulse_of.is_deleted


def _paginate(stmt: Select, limit: int, cursor: int | None) -> Select:
    if cursor:
        stmt = stmt.where(Pulse.id < cursor)
    # Fetch one extra row to learn whether another page exists.
    return stmt.limit(limit + 1)


def split_page(rows: Sequence[Pulse], limit: int) -> tuple[list[Pulse], str | None]:
    items = list(rows[:limit])
    has_more = len(rows) > limit
    next_cursor = str(items[-1].id) if has_more and items else None
    return items, next_cursor


def _collapse_reposts(items: Sequence[Pulse]) -> list[Pulse]:
    """Show a pulse once per page, however many people reposted it.

    Three followees boosting the same pulse should not fill the screen with
    three copies of it. Run this *after* ``split_page`` so the cursor is still
    taken from the last row actually read, and paging stays exact.
    """
    seen: set[int] = set()
    kept: list[Pulse] = []
    for pulse in items:
        display_id = pulse.repulse_of_id or pulse.id
        if display_id in seen:
            continue
        seen.add(display_id)
        kept.append(pulse)
    return kept


async def home_feed(
    db: AsyncSession, viewer: User, limit: int, cursor: int | None
) -> tuple[list[Pulse], str | None]:
    """Pulses and reposts from the accounts the viewer follows, plus their own."""
    hidden = await user_service.blocked_ids(db, viewer.id)
    followees = select(Follow.followee_id).where(Follow.follower_id == viewer.id)

    stmt = _base(hidden).where(
        or_(Pulse.author_id.in_(followees), Pulse.author_id == viewer.id),
        # Replies belong in the thread view, not the feed.
        Pulse.reply_to_id.is_(None),
    )
    rows = list((await db.scalars(_paginate(stmt, limit, cursor))).unique().all())
    rows = [p for p in rows if not _is_orphan_repost(p)]
    items, next_cursor = split_page(rows, limit)
    return _collapse_reposts(items), next_cursor


async def explore_feed(
    db: AsyncSession, viewer: User | None, limit: int, cursor: int | None
) -> tuple[list[Pulse], str | None]:
    """Recent top-level pulses from across the network."""
    hidden = await user_service.blocked_ids(db, viewer.id) if viewer else []
    stmt = restrict_to_visible(
        _base(hidden).where(Pulse.reply_to_id.is_(None), Pulse.repulse_of_id.is_(None)),
        viewer.id if viewer else None,
    )
    rows = list((await db.scalars(_paginate(stmt, limit, cursor))).unique().all())
    return split_page(rows, limit)


async def user_pulses(
    db: AsyncSession,
    author: User,
    viewer: User | None,
    limit: int,
    cursor: int | None,
    *,
    include_replies: bool = False,
) -> tuple[list[Pulse], str | None]:
    hidden = await user_service.blocked_ids(db, viewer.id) if viewer else []
    stmt = _base(hidden).where(Pulse.author_id == author.id)
    if not include_replies:
        stmt = stmt.where(Pulse.reply_to_id.is_(None))
    rows = list((await db.scalars(_paginate(stmt, limit, cursor))).unique().all())
    rows = [p for p in rows if not _is_orphan_repost(p)]
    items, next_cursor = split_page(rows, limit)
    return _collapse_reposts(items), next_cursor


async def user_replies(
    db: AsyncSession, author: User, viewer: User | None, limit: int, cursor: int | None
) -> tuple[list[Pulse], str | None]:
    hidden = await user_service.blocked_ids(db, viewer.id) if viewer else []
    stmt = _base(hidden).where(Pulse.author_id == author.id, Pulse.reply_to_id.is_not(None))
    rows = list((await db.scalars(_paginate(stmt, limit, cursor))).unique().all())
    return split_page(rows, limit)


async def user_media(
    db: AsyncSession, author: User, viewer: User | None, limit: int, cursor: int | None
) -> tuple[list[Pulse], str | None]:
    from app.models import Media

    hidden = await user_service.blocked_ids(db, viewer.id) if viewer else []
    with_media = select(Media.pulse_id).where(Media.pulse_id.is_not(None))
    stmt = _base(hidden).where(Pulse.author_id == author.id, Pulse.id.in_(with_media))
    rows = list((await db.scalars(_paginate(stmt, limit, cursor))).unique().all())
    return split_page(rows, limit)


async def user_likes(
    db: AsyncSession, owner: User, viewer: User | None, limit: int, cursor: int | None
) -> tuple[list[Pulse], str | None]:
    hidden = await user_service.blocked_ids(db, viewer.id) if viewer else []
    liked = select(Like.pulse_id).where(Like.user_id == owner.id)
    stmt = restrict_to_visible(
        _base(hidden).where(Pulse.id.in_(liked)), viewer.id if viewer else None
    )
    rows = list((await db.scalars(_paginate(stmt, limit, cursor))).unique().all())
    return split_page(rows, limit)


async def bookmarks(
    db: AsyncSession, viewer: User, limit: int, cursor: int | None
) -> tuple[list[Pulse], str | None]:
    hidden = await user_service.blocked_ids(db, viewer.id)
    saved = select(Bookmark.pulse_id).where(Bookmark.user_id == viewer.id)
    stmt = _base(hidden).where(Pulse.id.in_(saved))
    rows = list((await db.scalars(_paginate(stmt, limit, cursor))).unique().all())
    return split_page(rows, limit)


async def replies_to(
    db: AsyncSession, pulse_id: int, viewer: User | None, limit: int, cursor: int | None
) -> tuple[list[Pulse], str | None]:
    hidden = await user_service.blocked_ids(db, viewer.id) if viewer else []
    stmt = (
        select(Pulse)
        .options(*_load_options())
        .where(Pulse.is_deleted.is_(False), Pulse.reply_to_id == pulse_id)
        # Replies read top-down, oldest first.
        .order_by(Pulse.id.asc())
    )
    if hidden:
        stmt = stmt.where(Pulse.author_id.not_in(hidden))
    stmt = restrict_to_visible(stmt, viewer.id if viewer else None)
    if cursor:
        stmt = stmt.where(Pulse.id > cursor)
    rows = list((await db.scalars(stmt.limit(limit + 1))).unique().all())
    return split_page(rows, limit)


async def ancestors_of(db: AsyncSession, pulse: Pulse, max_depth: int = 10) -> list[Pulse]:
    """Walk up the reply chain, oldest first."""
    chain: list[Pulse] = []
    current = pulse
    for _ in range(max_depth):
        if not current.reply_to_id:
            break
        parent = await db.scalar(
            select(Pulse).options(*_load_options()).where(Pulse.id == current.reply_to_id)
        )
        if parent is None:
            break
        chain.append(parent)
        current = parent
    return list(reversed(chain))


async def trending(
    db: AsyncSession, limit: int = 10, window_hours: int = 48
) -> list[TrendOut]:
    """Hashtags ranked by use within the recent window."""
    since = datetime.now(UTC) - timedelta(hours=window_hours)
    rows = (
        await db.execute(
            select(Hashtag.tag, func.count(PulseHashtag.pulse_id).label("uses"))
            .join(PulseHashtag, PulseHashtag.hashtag_id == Hashtag.id)
            .join(Pulse, Pulse.id == PulseHashtag.pulse_id)
            .where(
                PulseHashtag.created_at >= since,
                Pulse.is_deleted.is_(False),
                # A protected account's hashtags must not shape public trends.
                Pulse.author_id.not_in(select(User.id).where(User.is_private.is_(True))),
            )
            .group_by(Hashtag.tag)
            .order_by(func.count(PulseHashtag.pulse_id).desc(), Hashtag.tag.asc())
            .limit(limit)
        )
    ).all()
    return [
        TrendOut(tag=tag, pulse_count=uses, rank=i + 1)
        for i, (tag, uses) in enumerate(rows)
    ]


async def by_hashtag(
    db: AsyncSession, tag: str, viewer: User | None, limit: int, cursor: int | None
) -> tuple[list[Pulse], str | None]:
    hidden = await user_service.blocked_ids(db, viewer.id) if viewer else []
    tagged = (
        select(PulseHashtag.pulse_id)
        .join(Hashtag, Hashtag.id == PulseHashtag.hashtag_id)
        .where(Hashtag.tag == tag.lower().lstrip("#"))
    )
    stmt = restrict_to_visible(
        _base(hidden).where(Pulse.id.in_(tagged)), viewer.id if viewer else None
    )
    rows = list((await db.scalars(_paginate(stmt, limit, cursor))).unique().all())
    return split_page(rows, limit)
