"""Who is allowed to read whose pulses.

A protected account's pulses are readable only by the owner and their approved
followers. That rule has to hold on every read path — explore, search, hashtag
feeds, threads, a single pulse — so it lives here as one SQL predicate and one
scalar check rather than being restated at each call site.
"""

from __future__ import annotations

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Follow, Pulse, User


def restrict_to_visible(stmt: Select, viewer_id: int | None) -> Select:
    """Filter a pulse query down to what ``viewer_id`` may read.

    Expressed as "not authored by a protected account the viewer has no access
    to". Protected accounts are the rare case, so the anti-join stays small.
    """
    protected = select(User.id).where(User.is_private.is_(True))

    if viewer_id is None:
        return stmt.where(Pulse.author_id.not_in(protected))

    approved = select(Follow.followee_id).where(Follow.follower_id == viewer_id)
    return stmt.where(
        or_(
            Pulse.author_id.not_in(protected),
            Pulse.author_id == viewer_id,
            Pulse.author_id.in_(approved),
        )
    )


async def may_view_account(db: AsyncSession, author: User, viewer_id: int | None) -> bool:
    """Whether ``viewer_id`` may read ``author``'s pulses."""
    if not author.is_private:
        return True
    if viewer_id is None:
        return False
    if viewer_id == author.id:
        return True

    edge = await db.scalar(
        select(Follow.follower_id).where(
            Follow.follower_id == viewer_id, Follow.followee_id == author.id
        )
    )
    return edge is not None


async def may_view_pulse(db: AsyncSession, pulse: Pulse, viewer_id: int | None) -> bool:
    return await may_view_account(db, pulse.author, viewer_id)
