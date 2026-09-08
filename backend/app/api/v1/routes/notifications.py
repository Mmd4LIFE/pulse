"""The notification inbox."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession, Paging
from app.models import NotificationType
from app.schemas.common import CountResponse, Message, Page
from app.schemas.notification import NotificationOut
from app.services import notifications as service
from app.services.serializers import to_pulse_ref, to_user_summary

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationOut])
async def list_notifications(
    user: CurrentUser,
    db: DbSession,
    paging: Paging,
    unread_only: bool = False,
    kind: list[NotificationType] | None = Query(default=None),
) -> Page[NotificationOut]:
    rows, cursor = await service.list_notifications(
        db, user, paging.limit, paging.cursor, only_unread=unread_only, kinds=kind
    )
    return Page(
        items=[
            NotificationOut(
                id=n.id,
                type=n.type,
                actor=to_user_summary(n.actor),
                pulse=to_pulse_ref(n.pulse),
                is_read=n.is_read,
                created_at=n.created_at,
            )
            for n in rows
        ],
        next_cursor=cursor,
        has_more=cursor is not None,
    )


@router.get("/unread-count", response_model=CountResponse)
async def unread_count(user: CurrentUser, db: DbSession) -> CountResponse:
    return CountResponse(count=await service.unread_count(db, user))


@router.post("/read-all", response_model=CountResponse)
async def mark_all_read(user: CurrentUser, db: DbSession) -> CountResponse:
    return CountResponse(count=await service.mark_all_read(db, user))


@router.post("/{notification_id}/read", response_model=Message)
async def mark_read(notification_id: int, user: CurrentUser, db: DbSession) -> Message:
    done = await service.mark_read(db, user, notification_id)
    return Message(message="Marked read." if done else "Already read.")
