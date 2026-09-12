"""Importing a Telegram channel's history into Pulse.

The Bot API cannot read a chat's past: it only delivers updates from the moment
a bot is added, and there is no history method to call. The only way to get a
channel's back catalogue without asking someone for their account credentials
is the export Telegram Desktop itself produces -- "Export chat history", which
writes a ``result.json`` alongside the media it references.

So that is what this reads. The owner exports their channel, uploads the file,
and each message becomes a pulse credited to them.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PermissionDeniedError, ValidationError
from app.core.logging import get_logger
from app.models import Channel, Pulse, User
from app.services.media import store_upload
from app.services.text import normalise_content

log = get_logger(__name__)

# A channel export can be enormous. These bound one run so a single upload
# cannot fill the disk or hold a worker indefinitely.
MAX_MESSAGES = 20_000
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MEDIA_PER_MESSAGE = 4

# Pulses are capped at 280 characters; channel posts frequently are not.
TRUNCATION_MARK = "…"

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


class ChannelExportError(Exception):
    """The uploaded export could not be read."""


# ---------------------------------------------------------------------------
# Reading the export
# ---------------------------------------------------------------------------


def chat_id_from_export(raw_id: Any) -> int | None:
    """Turn the export's channel id into the -100… form the Bot API uses.

    Exports record a channel as a bare positive id; everywhere else in Telegram
    the same channel is -100 followed by those digits.
    """
    try:
        value = int(raw_id)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return value
    return int(f"-100{value}")


def flatten_text(raw: Any) -> str:
    """Export text is either a plain string or a list of runs.

    A run is either a bare string or an object carrying the visible text along
    with the entity type, which is not needed here -- Pulse re-detects links,
    mentions and hashtags from the text itself when it renders.
    """
    if isinstance(raw, str):
        return raw
    if not isinstance(raw, list):
        return ""

    parts: list[str] = []
    for run in raw:
        if isinstance(run, str):
            parts.append(run)
        elif isinstance(run, dict):
            parts.append(str(run.get("text") or ""))
    return "".join(parts)


def parse_reactions(raw: Any) -> list[dict[str, Any]]:
    """Carry the channel's reaction tallies across.

    Custom emoji cannot be rendered outside Telegram, so they are kept with a
    neutral marker rather than dropped -- the count is still real.
    """
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        count = item.get("count")
        if not isinstance(count, int) or count <= 0:
            continue
        emoji = item.get("emoji")
        if not emoji and item.get("type") == "custom_emoji":
            emoji = "⭐"
        if not emoji:
            continue
        out.append({"emoji": str(emoji)[:16], "count": count})

    out.sort(key=lambda r: r["count"], reverse=True)
    return out[:8]


def parse_date(message: dict[str, Any]) -> datetime | None:
    unix = message.get("date_unixtime")
    if unix is not None:
        try:
            return datetime.fromtimestamp(int(unix), tz=UTC)
        except (TypeError, ValueError, OSError):
            pass

    raw = message.get("date")
    if isinstance(raw, str):
        try:
            # Exports write local time with no zone; treat it as UTC rather
            # than guessing, so ordering stays right even if the clock is off.
            return datetime.fromisoformat(raw).replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def media_paths(message: dict[str, Any]) -> list[str]:
    """Relative paths of images the message references."""
    found: list[str] = []
    for key in ("photo", "file", "thumbnail"):
        value = message.get(key)
        # A missing file is written as "(File not included...)" in the export.
        if (
            isinstance(value, str)
            and value
            and not value.startswith("(")
            and Path(value).suffix.lower() in IMAGE_SUFFIXES
        ):
            found.append(value)
    # A file and its thumbnail are the same picture; keep the first only.
    return found[:MAX_MEDIA_PER_MESSAGE] if len(found) < 2 else found[:1]


def iter_messages(export: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield the posts worth importing, skipping joins, pins and the like."""
    messages = export.get("messages")
    if not isinstance(messages, list):
        raise ChannelExportError("The export has no messages array.")

    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("type") != "message":
            continue  # service events
        if not isinstance(message.get("id"), int):
            continue
        yield message


def load_export(path: Path) -> tuple[dict[str, Any], zipfile.ZipFile | None, str]:
    """Open an upload, whether it is the bare JSON or a zip of the folder.

    Returns the parsed export, the open archive when there is one, and the
    prefix inside it that media paths are relative to.
    """
    if zipfile.is_zipfile(path):
        archive = zipfile.ZipFile(path)
        names = archive.namelist()
        candidates = [n for n in names if n.endswith("result.json")]
        if not candidates:
            archive.close()
            raise ChannelExportError(
                "That archive has no result.json. Zip the whole folder Telegram "
                "exported, not just part of it."
            )
        # The shallowest one, in case the folder was zipped with a wrapper.
        member = min(candidates, key=lambda n: n.count("/"))
        prefix = member[: -len("result.json")]
        try:
            export = json.loads(archive.read(member).decode("utf-8", "replace"))
        except (json.JSONDecodeError, KeyError) as exc:
            archive.close()
            raise ChannelExportError(
                "The result.json inside the archive is not readable."
            ) from exc
        return export, archive, prefix

    try:
        export = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise ChannelExportError(
            "That file is neither a Telegram export archive nor a readable result.json."
        ) from exc
    return export, None, ""


# ---------------------------------------------------------------------------
# Writing it into Pulse
# ---------------------------------------------------------------------------


def _content_for(message: dict[str, Any]) -> str:
    text = normalise_content(flatten_text(message.get("text")))
    if len(text) <= 280:
        return text
    # Cut on a word boundary where there is one nearby, so the tail is not a
    # severed word.
    cut = text[:279]
    space = cut.rfind(" ")
    if space > 200:
        cut = cut[:space]
    return cut.rstrip() + TRUNCATION_MARK


async def _attach_media(
    db: AsyncSession,
    owner: User,
    pulse: Pulse,
    message: dict[str, Any],
    archive: zipfile.ZipFile | None,
    prefix: str,
) -> None:
    """Store the message's pictures, when the export included them."""
    if archive is None:
        return

    for position, relative in enumerate(media_paths(message)):
        member = f"{prefix}{relative}"
        try:
            data = archive.read(member)
        except KeyError:
            continue  # referenced but not in the archive
        if not data:
            continue
        try:
            item = await store_upload(db, owner, data)
        except Exception as exc:
            log.info("import_media_skipped", reason=str(exc), member=member)
            continue
        item.pulse_id = pulse.id
        item.position = position


async def import_export(
    db: AsyncSession, owner: User, channel: Channel, upload_path: Path
) -> tuple[int, int]:
    """Import an export into ``channel``'s owner's account.

    Returns (created, updated). Safe to run twice: a message already imported
    has its text and reactions refreshed rather than being posted again.
    """
    export, archive, prefix = load_export(upload_path)

    try:
        exported_id = chat_id_from_export(export.get("id"))
        if exported_id is None:
            raise ChannelExportError("The export does not say which chat it came from.")

        # Without this check anyone could upload somebody else's export and
        # publish its contents under their own name.
        if exported_id != channel.chat_id:
            raise PermissionDeniedError(
                "That export is from a different channel than the one connected "
                "to your account.",
                code="wrong_channel",
            )

        messages = list(iter_messages(export))
        if len(messages) > MAX_MESSAGES:
            messages = messages[-MAX_MESSAGES:]  # keep the most recent

        channel.import_total = len(messages)
        channel.import_done = 0
        await db.commit()

        created = updated = 0
        for index, message in enumerate(messages, start=1):
            content = _content_for(message)
            reactions = parse_reactions(message.get("reactions"))
            posted = parse_date(message)
            has_media = bool(archive and media_paths(message))

            if not content and not has_media:
                continue  # nothing that would render

            existing = await db.scalar(
                select(Pulse).where(
                    Pulse.source_channel_id == channel.chat_id,
                    Pulse.source_message_id == message["id"],
                )
            )
            if existing is not None:
                existing.content = content
                existing.reactions = reactions or None
                existing.is_deleted = False
                updated += 1
            else:
                pulse = Pulse(
                    author_id=owner.id,
                    content=content,
                    source_channel_id=channel.chat_id,
                    source_message_id=message["id"],
                    source_date=posted,
                    reactions=reactions or None,
                )
                if posted is not None:
                    # Show when it was posted to the channel, not when the
                    # import happened to run.
                    pulse.created_at = posted
                db.add(pulse)
                await db.flush()
                pulse.conversation_id = pulse.id
                await _attach_media(db, owner, pulse, message, archive, prefix)
                created += 1

            if index % 50 == 0:
                channel.import_done = index
                await db.commit()

        channel.import_done = len(messages)
        await db.commit()
        return created, updated
    finally:
        if archive is not None:
            archive.close()


async def run_import(owner_id: int, upload_path: str) -> None:
    """Background entry point. Never raises: failures are recorded instead."""
    from app.db.session import SessionLocal

    path = Path(upload_path)
    try:
        async with SessionLocal() as db:
            owner = await db.get(User, owner_id)
            channel = await db.scalar(select(Channel).where(Channel.owner_id == owner_id))
            if owner is None or channel is None:
                return

            try:
                created, updated = await import_export(db, owner, channel, path)
            except (ChannelExportError, PermissionDeniedError, ValidationError) as exc:
                await db.rollback()
                await db.execute(
                    update(Channel)
                    .where(Channel.owner_id == owner_id)
                    .values(
                        import_status="failed",
                        import_error=str(getattr(exc, "message", exc))[:255],
                    )
                )
                await db.commit()
                log.warning("channel_import_failed", owner_id=owner_id, reason=str(exc))
                return

            await db.execute(
                update(Channel)
                .where(Channel.owner_id == owner_id)
                .values(
                    import_status="done",
                    import_error=None,
                    imported_at=datetime.now(UTC),
                )
            )
            await db.commit()
            log.info(
                "channel_import_done",
                owner_id=owner_id,
                created=created,
                updated=updated,
            )
    except Exception as exc:
        log.exception("channel_import_crashed", owner_id=owner_id, error=str(exc))
        try:
            async with SessionLocal() as db:
                await db.execute(
                    update(Channel)
                    .where(Channel.owner_id == owner_id)
                    .values(import_status="failed", import_error=str(exc)[:255])
                )
                await db.commit()
        except Exception:
            pass
    finally:
        path.unlink(missing_ok=True)
