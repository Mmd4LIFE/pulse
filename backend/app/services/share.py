"""Sharing a pulse into a Telegram chat.

Telegram will not let a Mini App pick a chat and post into it. What it offers
instead is a *prepared inline message*: the app describes a message to the Bot
API, gets an id back, and hands that id to ``WebApp.shareMessage``, which opens
the native chat picker. The user chooses where it goes -- we never learn, and
never could send anything on our own.

The picture itself is rendered by the client, where the browser already has the
fonts, the bidirectional text layout and the exact styling of a pulse. It is
stored here because Telegram fetches the photo over the public web when the
message is finally sent, so it needs a URL that outlives the request.
"""

from __future__ import annotations

import io
import secrets
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from PIL import Image, UnidentifiedImageError

from app.core import botapi
from app.core.config import settings
from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.models import Pulse, User

log = get_logger(__name__)

CARD_FOLDER = "cards"
CARD_MAX_BYTES = 3 * 1024 * 1024
CARD_MAX_EDGE = 2600
CARD_MIN_EDGE = 120
# Telegram fetches an inline photo by URL and requires JPEG for it.
CARD_FORMAT = "JPEG"
# A prepared message is valid for far less than this; the cushion is for the
# message that is shared on the last possible day and read a while later.
CARD_KEEP_DAYS = 40


class PreparedShare(NamedTuple):
    id: str
    expires_at: datetime | None
    image_url: str


def pulse_link(pulse_id: int) -> str:
    """The address to hand a stranger: the bot, which opens the Mini App."""
    bot = settings.TELEGRAM_BOT_USERNAME
    if bot:
        return f"https://t.me/{bot}?start=pulse_{pulse_id}"
    return f"{settings.PUBLIC_WEB_URL.rstrip('/')}/pulse/{pulse_id}"


def _cards_root() -> Path:
    root = Path(settings.MEDIA_ROOT) / CARD_FOLDER
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sweep(root: Path, today: date) -> None:
    """Drop day folders no prepared message can still be pointing at.

    Cards are write-once and read by Telegram within days, so nothing here is
    worth a scheduled job; doing it on the way past keeps the directory from
    growing for the life of the deployment.
    """
    cutoff = today - timedelta(days=CARD_KEEP_DAYS)
    for folder in root.iterdir():
        try:
            when = date.fromisoformat(folder.name)
        except ValueError:
            continue
        if when < cutoff:
            shutil.rmtree(folder, ignore_errors=True)


def store_card(data: bytes) -> str:
    """Keep a rendered card and return the absolute URL Telegram will fetch."""
    if not data:
        raise ValidationError("The card image is empty.")
    if len(data) > CARD_MAX_BYTES:
        raise ValidationError("That card image is too large to share.")

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            width, height = img.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("That card image could not be read.") from exc

    if fmt != CARD_FORMAT:
        raise ValidationError("A shared card must be a JPEG image.")
    if not (CARD_MIN_EDGE <= width <= CARD_MAX_EDGE):
        raise ValidationError("That card image is the wrong size.")
    if not (CARD_MIN_EDGE <= height <= CARD_MAX_EDGE):
        raise ValidationError("That card image is the wrong size.")

    root = _cards_root()
    today = datetime.now(UTC).date()
    try:
        _sweep(root, today)
    except OSError:  # pragma: no cover - housekeeping never fails a share
        log.warning("card_sweep_failed")

    folder = root / today.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_urlsafe(16)}.jpg"
    (folder / name).write_bytes(data)

    key = f"{CARD_FOLDER}/{today.isoformat()}/{name}"
    prefix = settings.MEDIA_URL_PREFIX.strip("/")
    return f"{settings.PUBLIC_WEB_URL.rstrip('/')}/{prefix}/{key}"


async def prepare_card_message(
    sharer: User, pulse: Pulse, author: User, image_url: str
) -> PreparedShare:
    """Ask Telegram to hold a photo message for this user to place."""
    link = pulse_link(pulse.id)
    caption = f"{author.display_name} (@{author.username}) on Pulse"

    result = await botapi.call(
        "savePreparedInlineMessage",
        {
            "user_id": sharer.telegram_id,
            "allow_user_chats": True,
            "allow_bot_chats": False,
            "allow_group_chats": True,
            "allow_channel_chats": True,
            "result": {
                "type": "photo",
                "id": secrets.token_urlsafe(12),
                "photo_url": image_url,
                "thumbnail_url": image_url,
                "caption": caption,
                "reply_markup": {
                    "inline_keyboard": [[{"text": "Open in Pulse", "url": link}]]
                },
            },
        },
    )

    expires = result.get("expiration_date")
    return PreparedShare(
        id=str(result["id"]),
        expires_at=datetime.fromtimestamp(expires, UTC) if expires else None,
        image_url=image_url,
    )
