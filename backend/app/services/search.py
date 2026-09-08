"""Search across accounts, pulses, and hashtags."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Hashtag, Pulse, User
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
