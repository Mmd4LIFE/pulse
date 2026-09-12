"""Connecting a Telegram channel to an account."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.config import settings as app_settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.schemas.channel import ChannelConnect, ChannelOut
from app.schemas.common import Message
from app.services import channel_import
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


@router.post("/me/import", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def import_channel_history(
    user: CurrentUser,
    db: DbSession,
    background: BackgroundTasks,
    file: UploadFile = File(...),
) -> Message:
    """Import a channel's past posts from a Telegram Desktop export.

    The Bot API has no way to read a chat's history -- it only receives updates
    from the moment the bot is added -- so the back catalogue has to come from
    the export Telegram itself produces. Upload either the whole exported
    folder zipped, which brings the images with it, or the bare result.json for
    text and reactions alone.
    """
    channel = await service.get_for(db, user.id)
    if channel is None:
        raise NotFoundError("Connect your channel before importing its history.")
    if channel.import_status == "running":
        raise ConflictError("An import is already running for this channel.")

    # Stream to disk rather than into memory: a channel export runs to
    # hundreds of megabytes.
    staging = Path(app_settings.MEDIA_ROOT) / "imports"
    staging.mkdir(parents=True, exist_ok=True)
    target = staging / f"{user.id}-{secrets.token_hex(8)}"

    size = 0
    try:
        with target.open("wb") as sink:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > channel_import.MAX_ARCHIVE_BYTES:
                    raise ValidationError(
                        "That export is larger than "
                        f"{channel_import.MAX_ARCHIVE_BYTES // (1024 * 1024)} MB."
                    )
                sink.write(chunk)
    except ValidationError:
        target.unlink(missing_ok=True)
        raise
    except OSError as exc:
        target.unlink(missing_ok=True)
        raise ValidationError("The upload could not be stored.") from exc

    if size == 0:
        target.unlink(missing_ok=True)
        raise ValidationError("The uploaded file is empty.")

    channel.import_status = "running"
    channel.import_error = None
    channel.import_total = 0
    channel.import_done = 0
    await db.commit()

    background.add_task(channel_import.run_import, user.id, str(target))
    return Message(message="Import started. This can take a while on a large channel.")


@router.post("/me/import/reset", response_model=Message)
async def reset_import_state(user: CurrentUser, db: DbSession) -> Message:
    """Clear a stuck import so another can be started."""
    channel = await service.get_for(db, user.id)
    if channel is None:
        raise NotFoundError("No channel is connected.")
    channel.import_status = "idle"
    channel.import_error = None
    await db.commit()
    return Message(message="Import state cleared.")
