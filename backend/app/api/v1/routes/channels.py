"""Connecting a Telegram channel to an account."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.errors import NotFoundError
from app.schemas.channel import ChannelConnect, ChannelOut
from app.schemas.common import Message
from app.services import channels as service

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("/me", response_model=ChannelOut | None)
async def read_my_channel(user: CurrentUser, db: DbSession) -> ChannelOut | None:
    channel = await service.get_for(db, user.id)
    return ChannelOut.model_validate(channel) if channel else None


@router.put("/me", response_model=ChannelOut, status_code=status.HTTP_200_OK)
async def connect_channel(
    payload: ChannelConnect, user: CurrentUser, db: DbSession
) -> ChannelOut:
    """Attach a channel, after checking the bot can actually post to it."""
    channel = await service.connect(db, user, payload.reference)
    return ChannelOut.model_validate(channel)


@router.delete("/me", response_model=Message)
async def disconnect_channel(user: CurrentUser, db: DbSession) -> Message:
    removed = await service.disconnect(db, user)
    return Message(message="Channel disconnected." if removed else "No channel connected.")


@router.post("/me/test", response_model=Message)
async def send_test_message(user: CurrentUser, db: DbSession) -> Message:
    """Post a short message to prove the connection works end to end."""
    channel = await service.get_for(db, user.id)
    if channel is None:
        raise NotFoundError("No channel is connected.")

    bot = settings.TELEGRAM_BOT_USERNAME or "Pulse"
    try:
        await service._call(
            "sendMessage",
            {
                "chat_id": channel.chat_id,
                "text": (
                    "✅ <b>Pulse is connected.</b>\n\n"
                    "Pulses you choose to share will appear here."
                ),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
    except service.TelegramApiError as exc:
        channel.can_post = False
        channel.last_error = exc.description[:255]
        await db.commit()
        return Message(message=f"Telegram refused: {exc.description}")

    channel.can_post = True
    channel.last_error = None
    await db.commit()
    return Message(message=f"Sent. Check {channel.display} — posted by @{bot}.")
