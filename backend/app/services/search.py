"""Search across accounts, pulses, and hashtags."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Follow, Hashtag, Pulse, User
from app.services import users as user_service
from app.services.pulses import _load_options
from app.services.visibility import restrict_to_visible


def _escape_like(term: str) -> str:
    """Neutralise LIKE wildcards so a query for "100%" is a literal search."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_users(
    db: AsyncSession, query: str, viewer: User | None, limit: int, cursor: int | None
) -> list[User]:
    term = _escape_like(query.strip().lstrip("@"))
    if not term:
        return []
    pattern = f"%{term.lower()}%"

    stmt = (
        select(User)
        .where(
            User.is_active.is_(True),
            or_(
                func.lower(User.username).like(pattern, escape="\\"),
                func.lower(User.display_name).like(pattern, escape="\\"),
            ),
        )
        # Exact handle first, then by reach.
        .order_by(
            (func.lower(User.username) == term.lower()).desc(),
            User.followers_count.desc(),
            User.id.desc(),
        )
        .limit(limit)
    )
    if viewer is not None:
        hidden = await user_service.blocked_ids(db, viewer.id)
        if hidden:
            stmt = stmt.where(User.id.not_in(hidden))
    if cursor:
        stmt = stmt.where(User.id < cursor)
    return list((await db.scalars(stmt)).all())


async def search_pulses(
    db: AsyncSession, query: str, viewer: User | None, limit: int, cursor: int | None
) -> tuple[list[Pulse], str | None]:
    term = _escape_like(query.strip())
    if not term:
        return [], None

    stmt = (
        select(Pulse)
        .options(*_load_options())
        .where(
            Pulse.is_deleted.is_(False),
            Pulse.repulse_of_id.is_(None),
            Pulse.content.ilike(f"%{term}%", escape="\\"),
        )
        .order_by(Pulse.id.desc())
        .limit(limit + 1)
    )
    if viewer is not None:
        hidden = await user_service.blocked_ids(db, viewer.id)
        if hidden:
            stmt = stmt.where(Pulse.author_id.not_in(hidden))
    stmt = restrict_to_visible(stmt, viewer.id if viewer else None)
    if cursor:
        stmt = stmt.where(Pulse.id < cursor)

    rows = list((await db.scalars(stmt)).unique().all())
    items = rows[:limit]
    next_cursor = str(items[-1].id) if len(rows) > limit and items else None
    return items, next_cursor


async def search_hashtags(db: AsyncSession, query: str, limit: int) -> list[Hashtag]:
    term = _escape_like(query.strip().lstrip("#").lower())
    if not term:
        return []
    stmt = (
        select(Hashtag)
        .where(Hashtag.tag.like(f"{term}%", escape="\\"))
        .order_by(Hashtag.usage_count.desc(), Hashtag.tag.asc())
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())


async def suggest_mentions(
    db: AsyncSession, query: str, viewer: User | None, limit: int
) -> list[User]:
    """Accounts to offer while someone is typing an @mention.

    Ranked for the composer rather than for browsing: an exact handle first,
    then people the writer follows, then by reach. Matching is prefix-based on
    the handle -- typing "@ma" should offer @maryam, not every account with
    "ma" buried in its display name.
    """
    term = _escape_like(query.strip().lstrip("@")).lower()

    if not term:
        # A bare "@" means "who do I usually talk to": offer the accounts the
        # writer follows rather than nothing at all.
        if viewer is None:
            return []
        followed = select(Follow.followee_id).where(Follow.follower_id == viewer.id)
        stmt = (
            select(User)
            .where(User.is_active.is_(True), User.id.in_(followed))
            .order_by(User.followers_count.desc(), User.id.desc())
            .limit(limit)
        )
        hidden = await user_service.blocked_ids(db, viewer.id)
        if hidden:
            stmt = stmt.where(User.id.not_in(hidden))
        return list((await db.scalars(stmt)).all())

    handle_prefix = func.lower(User.username).like(f"{term}%", escape="\\")
    name_match = func.lower(User.display_name).like(f"%{term}%", escape="\\")

    stmt = select(User).where(User.is_active.is_(True), or_(handle_prefix, name_match))

    order = [
        (func.lower(User.username) == term).desc(),
        handle_prefix.desc(),
    ]

    if viewer is not None:
        followed = select(Follow.followee_id).where(Follow.follower_id == viewer.id)
        # People you follow are far likelier to be who you meant.
        order.insert(1, User.id.in_(followed).desc())

        hidden = await user_service.blocked_ids(db, viewer.id)
        if hidden:
            stmt = stmt.where(User.id.not_in(hidden))

    order += [User.followers_count.desc(), User.id.asc()]
    return list((await db.scalars(stmt.order_by(*order).limit(limit))).all())
