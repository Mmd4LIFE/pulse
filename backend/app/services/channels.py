"""Connecting a Telegram channel and mirroring pulses into it.

Pulse can echo a user's posts into a channel they run. Telegram only allows
that while our bot is an administrator there with permission to post, so a
channel is resolved and that permission checked before the connection is
stored — connecting fails loudly rather than silently dropping messages later.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models import Channel, Pulse, User

log = get_logger(__name__)

API_ROOT = "https://api.telegram.org"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)

USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
# -100… for channels and supergroups.
CHAT_ID_RE = re.compile(r"^-100\d{5,}$")


class TelegramApiError(Exception):
    """A call to the Bot API failed."""

    def __init__(self, description: str, *, status: int | None = None) -> None:
        self.description = description
        self.status = status
        super().__init__(description)


async def _call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{API_ROOT}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise TelegramApiError(f"Could not reach Telegram: {exc}") from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise TelegramApiError("Telegram returned an unreadable response") from exc

    if not body.get("ok"):
        raise TelegramApiError(
            str(body.get("description") or "Telegram rejected the request"),
            status=response.status_code,
        )
    return body.get("result") or {}


def normalise_reference(reference: str) -> str:
    """Accept @name, a t.me link, a bare name, or a numeric -100… id."""
    value = reference.strip()
    if not value:
        raise ValidationError("Enter a channel username.")

    # People paste the link in every form: with a scheme, without one, with a
    # trailing slash, or just the @name.
    value = re.sub(
        r"^(https?://)?(www\.)?(t\.me|telegram\.me)/", "", value, flags=re.IGNORECASE
    )
    value = value.lstrip("@").strip("/")

    if CHAT_ID_RE.match(value):
        return value
    if not USERNAME_RE.match(value):
        raise ValidationError(
            "That is not a channel username. Use the public @name of your channel."
        )
    return f"@{value}"


async def _bot_id() -> int:
    me = await _call("getMe", {})
    return int(me["id"])


async def connect(db: AsyncSession, owner: User, reference: str) -> Channel:
    """Verify the bot can post to a channel, then attach it to the account."""
    chat_ref = normalise_reference(reference)

    try:
        chat = await _call("getChat", {"chat_id": chat_ref})
    except TelegramApiError as exc:
        log.info("channel_lookup_failed", reason=exc.description)
        raise NotFoundError(
            "No such channel. Check the username, and make sure the channel is public "
            "or that the bot has already been added to it."
        ) from exc

    if chat.get("type") != "channel":
        raise ValidationError("That is not a channel. Pulse can only post to channels.")

    chat_id = int(chat["id"])

    try:
        member = await _call(
            "getChatMember", {"chat_id": chat_id, "user_id": await _bot_id()}
        )
    except TelegramApiError as exc:
        raise ValidationError(
            f"Add @{settings.TELEGRAM_BOT_USERNAME or 'the Pulse bot'} to the channel "
            "as an administrator first."
        ) from exc

    if member.get("status") != "administrator":
        raise ValidationError(
            f"@{settings.TELEGRAM_BOT_USERNAME or 'The Pulse bot'} is in the channel but "
            "is not an administrator. Promote it so it can post."
        )
    if not member.get("can_post_messages", False):
        raise ValidationError(
            "The bot is an administrator but cannot post messages. Enable "
            '"Post Messages" for it in the channel settings.'
        )

    # Another account cannot claim a channel that is already connected.
    taken = await db.scalar(
        select(Channel).where(Channel.chat_id == chat_id, Channel.owner_id != owner.id)
    )
    if taken is not None:
        raise ConflictError("That channel is already connected to another account.")

    existing = await db.scalar(select(Channel).where(Channel.owner_id == owner.id))
    if existing is None:
        existing = Channel(owner_id=owner.id, chat_id=chat_id, title="")
        db.add(existing)

    existing.chat_id = chat_id
    existing.username = chat.get("username")
    existing.title = str(chat.get("title") or chat.get("username") or "Channel")[:255]
    existing.can_post = True
    existing.last_error = None

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("That channel is already connected.") from None

    await db.refresh(existing)
    log.info("channel_connected", owner_id=owner.id, chat_id=chat_id)
    return existing


async def get_for(db: AsyncSession, owner_id: int) -> Channel | None:
    return await db.scalar(select(Channel).where(Channel.owner_id == owner_id))


async def disconnect(db: AsyncSession, owner: User) -> bool:
    result = await db.execute(delete(Channel).where(Channel.owner_id == owner.id))
    await db.commit()
    return (result.rowcount or 0) > 0


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_message(pulse: Pulse, author: User) -> str:
    """The channel post: the pulse, attributed, with a way back into the app."""
    name = _escape(author.display_name)
    body = _escape(pulse.content) if pulse.content else "<i>(image)</i>"
    bot = settings.TELEGRAM_BOT_USERNAME
    link = f"https://t.me/{bot}?start=pulse_{pulse.id}" if bot else None

    lines = [f"<b>{name}</b> <i>@{_escape(author.username)}</i>", "", body]
    if link:
        lines += ["", f'<a href="{link}">Open in Pulse</a>']
    return "\n".join(lines)


async def publish_pulse(db: AsyncSession, pulse_id: int, owner_id: int) -> None:
    """Mirror a pulse into its author's channel.

    Runs after the response has been sent, so a slow or failing Telegram call
    never delays or fails the post itself. Problems are recorded on the channel
    so the UI can explain them.
    """
    channel = await get_for(db, owner_id)
    if channel is None:
        return

    pulse = await db.scalar(select(Pulse).where(Pulse.id == pulse_id))
    author = await db.get(User, owner_id)
    if pulse is None or author is None or pulse.is_deleted:
        return

    try:
        await _call(
            "sendMessage",
            {
                "chat_id": channel.chat_id,
                "text": render_message(pulse, author),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
    except TelegramApiError as exc:
        channel.can_post = False
        channel.last_error = exc.description[:255]
        await db.commit()
        log.warning(
            "channel_delivery_failed",
            owner_id=owner_id,
            pulse_id=pulse_id,
            reason=exc.description,
        )
        return

    channel.can_post = True
    channel.last_error = None
    channel.last_posted_at = datetime.now(UTC)
    pulse.sent_to_channel = True
    await db.commit()
    log.info("channel_delivered", owner_id=owner_id, pulse_id=pulse_id)


async def deliver_in_background(pulse_id: int, owner_id: int) -> None:
    """Entry point for FastAPI's background tasks.

    The request's session is already closed by the time this runs, so it opens
    its own. Nothing here may raise: a failed delivery must never surface as a
    failed post.
    """
    from app.db.session import SessionLocal

    try:
        async with SessionLocal() as session:
            await publish_pulse(session, pulse_id, owner_id)
    except Exception as exc:
        log.warning(
            "channel_delivery_crashed",
            pulse_id=pulse_id,
            owner_id=owner_id,
            error=str(exc),
        )
