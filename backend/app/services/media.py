"""Image uploads.

Files are written under ``MEDIA_ROOT`` and served by nginx, so nothing that
reaches the disk may be attacker-controlled: the stored name is generated here
and the bytes are verified as a real image before being kept.
"""

from __future__ import annotations

import io
import secrets
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ValidationError
from app.models import Media, User

# Pillow's decoder name -> the MIME type and extension we store it as.
_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
    "GIF": ("image/gif", "gif"),
}

MAX_DIMENSION = 4096


def _media_root() -> Path:
    root = Path(settings.MEDIA_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _inspect(data: bytes) -> tuple[str, str, int, int]:
    """Return (mime, extension, width, height) or raise ``ValidationError``."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()  # cheap structural check
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            width, height = img.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("That file is not a readable image.") from exc

    if fmt not in _FORMATS:
        raise ValidationError("Only JPEG, PNG, WebP and GIF images are supported.")
    mime, ext = _FORMATS[fmt]
    if mime not in settings.ALLOWED_IMAGE_TYPES:
        raise ValidationError("That image type is not allowed.")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValidationError(f"Images may be at most {MAX_DIMENSION}px on a side.")
    if width < 1 or height < 1:
        raise ValidationError("That image has no content.")
    return mime, ext, width, height


async def store_upload(
    db: AsyncSession, uploader: User, data: bytes, alt_text: str | None = None
) -> Media:
    if not data:
        raise ValidationError("The uploaded file is empty.")
    if len(data) > settings.MAX_UPLOAD_BYTES:
        limit_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ValidationError(f"Images must be smaller than {limit_mb} MB.")

    mime, ext, width, height = _inspect(data)

    # Shard by month so no single directory grows without bound.
    today = datetime.now(UTC)
    folder = f"{today:%Y/%m}"
    name = f"{secrets.token_urlsafe(16)}.{ext}"
    key = f"{folder}/{name}"

    target = _media_root() / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    media = Media(
        uploader_id=uploader.id,
        storage_key=key,
        mime_type=mime,
        size_bytes=len(data),
        width=width,
        height=height,
        alt_text=(alt_text or None),
    )
    db.add(media)
    await db.commit()
    await db.refresh(media)
    return media
