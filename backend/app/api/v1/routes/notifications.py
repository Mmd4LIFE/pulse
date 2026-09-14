"""The notification inbox."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession, Paging
from app.schemas.common import CountResponse, Message, Page
from app.schemas.notification import NotificationGroup, UnreadCounts
from app.services import notifications as service
from app.services.serializers import to_pulse_ref, to_user_summary

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationGroup])
async def list_notifications(
    user: CurrentUser,
    db: DbSession,
    paging: Paging,
    tab: str = Query(default="all", pattern="^(all|mentions|requests)$"),
) -> Page[NotificationGroup]:
    """The inbox, grouped.

    Forty people liking one pulse is one thing that happened, so it arrives as
    one row carrying a few faces and a count, not forty rows.
    """
    groups, cursor = await service.list_grouped(
        db, user, tab=tab, limit=paging.limit, cursor=paging.cursor
    )
    return Page(
        items=[
            NotificationGroup(
                key=g.key,
                type=g.type,
                actors=[to_user_summary(a) for a in g.actors],
                actor_count=g.actor_count,
                pulse=to_pulse_ref(g.pulse),
                is_read=g.is_read,
                created_at=g.created_at,
            )
            for g in groups
        ],
        next_cursor=cursor,
        has_more=cursor is not None,
    )


@router.get("/unread-count", response_model=CountResponse)
async def unread_count(user: CurrentUser, db: DbSession) -> CountResponse:
    """What the tab-bar badge shows."""
    return CountResponse(count=await service.unread_count(db, user))


@router.get("/unread", response_model=UnreadCounts)
async def unread_by_tab(user: CurrentUser, db: DbSession) -> UnreadCounts:
    """Unread per tab, so each tab can carry its own badge."""
    counts = await service.unread_counts(db, user)
    return UnreadCounts(**counts, total=sum(counts.get(t, 0) for t in ("all", "requests")))


@router.post("/read-all", response_model=CountResponse)
async def mark_all_read(
    user: CurrentUser,
    db: DbSession,
    tab: str | None = Query(default=None, pattern="^(all|mentions|requests)$"),
) -> CountResponse:
    """Mark one tab read, or the whole inbox when no tab is named."""
    return CountResponse(count=await service.mark_all_read(db, user, tab))


@router.post("/{notification_id}/read", response_model=Message)
async def mark_read(notification_id: int, user: CurrentUser, db: DbSession) -> Message:
    done = await service.mark_read(db, user, notification_id)
    return Message(message="Marked read." if done else "Already read.")
