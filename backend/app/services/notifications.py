"""Reading and clearing the notification inbox."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Notification, NotificationType, Pulse, User


def _load_options() -> tuple:
    # Both child loads must hang off the same strategy for Notification.pulse;
    # mixing joinedload and selectinload on one path is a loader conflict.
    return (
        joinedload(Notification.actor),
        joinedload(Notification.pulse).joinedload(Pulse.author),
        joinedload(Notification.pulse).selectinload(Pulse.media),
    )


async def list_notifications(
    db: AsyncSession,
    user: User,
    limit: int,
    cursor: int | None,
    *,
    only_unread: bool = False,
    kinds: list[NotificationType] | None = None,
) -> tuple[list[Notification], str | None]:
    stmt = (
        select(Notification)
        .options(*_load_options())
        .where(Notification.recipient_id == user.id)
        .order_by(Notification.id.desc())
        .limit(limit + 1)
    )
    if only_unread:
        stmt = stmt.where(Notification.is_read.is_(False))
    if kinds:
        stmt = stmt.where(Notification.type.in_(kinds))
    if cursor:
        stmt = stmt.where(Notification.id < cursor)

    rows = list((await db.scalars(stmt)).unique().all())
    items = rows[:limit]
    next_cursor = str(items[-1].id) if len(rows) > limit and items else None
    return items, next_cursor


async def unread_count(db: AsyncSession, user: User) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.recipient_id == user.id, Notification.is_read.is_(False))
        )
    ) or 0


async def mark_all_read(db: AsyncSession, user: User) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.recipient_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
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
