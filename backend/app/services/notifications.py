"""The notification inbox.

Notifications arrive one per action, which is the right way to record them and
the wrong way to read them: forty people liking the same pulse is one thing
that happened, not forty. So the inbox is assembled by grouping rather than
listed raw.

The grouping key is ``(type, pulse, day)``, and it does the right thing for
every kind without special-casing, because of what each kind points at:

* a like or a repulse points at the pulse it was made on, so all of them on
  one pulse collapse into a single row;
* a reply, quote or mention points at the *new* pulse, which is unique, so each
  stays its own row -- they carry words worth reading individually;
* a follow has no pulse, so a day's follows collapse together.

The day in the key is what keeps "5 people liked this" from silently becoming
"200 people liked this, at some point, ever".
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, NamedTuple

from sqlalchemy import func, literal_column, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models import Notification, NotificationType, Pulse, User

# Which kinds belong to which tab.
#
# Follow requests are deliberately not in "all": they are a queue of decisions,
# not a record of things that happened, and mixing the two means the queue is
# either lost among the rest or the rest is interrupted by it.
MENTION_KINDS = (
    NotificationType.REPLY,
    NotificationType.QUOTE,
    NotificationType.MENTION,
)
REQUEST_KINDS = (NotificationType.FOLLOW_REQUEST,)
ALL_KINDS = tuple(k for k in NotificationType if k not in REQUEST_KINDS)

Tab = Literal["all", "mentions", "requests"]

TABS: dict[str, tuple[NotificationType, ...]] = {
    "all": ALL_KINDS,
    "mentions": MENTION_KINDS,
    "requests": REQUEST_KINDS,
}

# Kinds that must never be collapsed together.
#
# A follow request is a decision, not an event. Three of them grouped into one
# row means one row carrying six buttons, and no way to see which name each
# pair belongs to -- so each keeps its own row.
NEVER_GROUP = REQUEST_KINDS

# How many faces a grouped row shows before it resorts to counting.
FACES_PER_GROUP = 3


class Group(NamedTuple):
    """One row of the inbox: a thing that happened, and who did it."""

    key: str
    type: NotificationType
    actors: list[User]
    actor_count: int
    pulse: Pulse | None
    is_read: bool
    created_at: datetime
    cursor: int


def _day():
    """The calendar day a notification landed on, as a groupable expression.

    ``literal_column`` rather than a plain string: passed as a value, the unit
    becomes a bind parameter, and Postgres then sees the copy in GROUP BY as a
    different expression from the one in SELECT and refuses the query.
    """
    return func.date_trunc(literal_column("'day'"), Notification.created_at)


def kinds_for(tab: str) -> tuple[NotificationType, ...]:
    return TABS.get(tab, ALL_KINDS)


async def list_grouped(
    db: AsyncSession,
    user: User,
    *,
    tab: str = "all",
    limit: int = 20,
    cursor: int | None = None,
) -> tuple[list[Group], str | None]:
    """A page of the inbox, already grouped."""
    kinds = kinds_for(tab)
    # Adding the id to the key makes every row a group of one.
    ungrouped = all(kind in NEVER_GROUP for kind in kinds)
    extra_key = [Notification.id] if ungrouped else []

    # One row per group, with the numbers the row needs to render.
    latest = func.max(Notification.id).label("latest")
    summary = (
        select(
            Notification.type.label("type"),
            Notification.pulse_id.label("pulse_id"),
            _day().label("day"),
            latest,
            func.count().label("actor_count"),
            func.bool_and(Notification.is_read).label("all_read"),
            func.max(Notification.created_at).label("latest_at"),
        )
        .where(Notification.recipient_id == user.id, Notification.type.in_(kinds))
        .group_by(Notification.type, Notification.pulse_id, _day(), *extra_key)
        .order_by(latest.desc())
        .limit(limit + 1)
    )
    if cursor:
        summary = summary.having(latest < cursor)

    rows = (await db.execute(summary)).all()
    page = rows[:limit]
    next_cursor = str(page[-1].latest) if len(rows) > limit and page else None
    if not page:
        return [], None

    # The faces for those groups, ranked within each one, so a group of four
    # hundred likes still costs three rows rather than four hundred.
    ranked = (
        select(
            Notification.id,
            Notification.actor_id,
            Notification.type.label("type"),
            Notification.pulse_id.label("pulse_id"),
            _day().label("day"),
            func.row_number()
            .over(
                partition_by=(
                    Notification.type,
                    Notification.pulse_id,
                    _day(),
                    *extra_key,
                ),
                order_by=Notification.id.desc(),
            )
            .label("rank"),
        )
        .where(
            Notification.recipient_id == user.id,
            Notification.type.in_(kinds),
            Notification.id <= page[0].latest,
        )
        .subquery()
    )

    faces = (
        await db.execute(
            select(ranked.c.id, ranked.c.type, ranked.c.pulse_id, ranked.c.day, User)
            .join(User, User.id == ranked.c.actor_id)
            .where(ranked.c.rank <= FACES_PER_GROUP)
        )
    ).all()

    by_group: dict[tuple, list[User]] = {}
    for notification_id, kind, pulse_id, day, actor in faces:
        key = (kind, pulse_id, day, notification_id) if ungrouped else (kind, pulse_id, day)
        by_group.setdefault(key, []).append(actor)

    # The pulses the page refers to, in one go.
    pulse_ids = [r.pulse_id for r in page if r.pulse_id is not None]
    pulses: dict[int, Pulse] = {}
    if pulse_ids:
        found = await db.scalars(
            select(Pulse)
            .options(joinedload(Pulse.author), selectinload(Pulse.media))
            .where(Pulse.id.in_(pulse_ids))
        )
        pulses = {p.id: p for p in found.unique().all()}

    groups: list[Group] = []
    for row in page:
        group_key = (
            (row.type, row.pulse_id, row.day, row.latest)
            if ungrouped
            else (row.type, row.pulse_id, row.day)
        )
        actors = by_group.get(group_key, [])
        groups.append(
            Group(
                key=f"{row.type.value}:{row.pulse_id or 0}:{row.latest}",
                type=row.type,
                actors=actors,
                actor_count=row.actor_count,
                pulse=pulses.get(row.pulse_id) if row.pulse_id else None,
                is_read=bool(row.all_read),
                created_at=row.latest_at,
                cursor=row.latest,
            )
        )
    return groups, next_cursor


async def unread_counts(db: AsyncSession, user: User) -> dict[str, int]:
    """Unread per tab, in one query rather than one query per tab."""
    rows = (
        await db.execute(
            select(Notification.type, func.count())
            .where(Notification.recipient_id == user.id, Notification.is_read.is_(False))
            .group_by(Notification.type)
        )
    ).all()
    by_kind = dict(rows)

    return {tab: sum(by_kind.get(kind, 0) for kind in kinds) for tab, kinds in TABS.items()}


async def unread_count(db: AsyncSession, user: User) -> int:
    """What the tab-bar badge shows: everything awaiting attention."""
    return (
        await db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.recipient_id == user.id, Notification.is_read.is_(False))
        )
    ) or 0


async def mark_all_read(db: AsyncSession, user: User, tab: str | None = None) -> int:
    """Mark a tab read, or the whole inbox when no tab is named.

    Reading one tab must not silently clear another: opening Mentions should
    not make a pending follow request look attended to.
    """
    stmt = update(Notification).where(
        Notification.recipient_id == user.id, Notification.is_read.is_(False)
    )
    if tab:
        stmt = stmt.where(Notification.type.in_(kinds_for(tab)))

    result = await db.execute(stmt.values(is_read=True))
    await db.commit()
    return result.rowcount or 0


async def mark_read(db: AsyncSession, user: User, notification_id: int) -> bool:
    result = await db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.recipient_id == user.id,
        )
        .values(is_read=True)
    )
    await db.commit()
    return (result.rowcount or 0) > 0
