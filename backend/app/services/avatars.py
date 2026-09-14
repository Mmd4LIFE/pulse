"""Serving a profile photo from our own origin.

Telegram hosts profile photos and sends no CORS headers with them, so a browser
will display one but will not let a canvas read it back. That is fine until the
app wants to *draw* a picture of a pulse, at which point the avatar is the one
thing on the card it cannot include.

So the photo is fetched here, once, kept next to the uploads, and handed back
from our own domain. The address is never taken from the caller: it comes from
the account row, which was filled in from Telegram's signed initData, and every
hop of the redirect Telegram uses has to land on a host we know.
"""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.logging import get_logger
from app.models import User

log = get_logger(__name__)

CACHE_FOLDER = "avatars"
# Telegram answers t.me with a redirect onto its CDN, so both belong here.
ALLOWED_HOSTS = (
    "t.me",
    "telegram.org",
    "telesco.pe",
    "cdn-telegram.org",
)
MAX_BYTES = 4 * 1024 * 1024
# Long enough that a timeline of shares costs one fetch, short enough that a
# changed photo catches up on its own.
FRESH_FOR = timedelta(days=3)
TIMEOUT = httpx.Timeout(8.0, connect=4.0)
MAX_HOPS = 4
# Enough for the card, small enough to keep on disk without thinking about it.
EDGE = 320


def _host_allowed(url: httpx.URL) -> bool:
    if url.scheme != "https":
        return False
    host = url.host.lower()
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in ALLOWED_HOSTS)


def _cache_path(source: str) -> Path:
    digest = hashlib.sha256(source.encode()).hexdigest()[:32]
    root = Path(settings.MEDIA_ROOT) / CACHE_FOLDER
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{digest}.jpg"


def _is_fresh(path: Path) -> bool:
    try:
        age = datetime.now(UTC).timestamp() - path.stat().st_mtime
    except OSError:
        return False
    return age < FRESH_FOR.total_seconds()


async def _download(source: str) -> bytes | None:
    """Follow Telegram's redirect by hand, checking where each hop points."""
    url = httpx.URL(source)
    if not _host_allowed(url):
        return None

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
        for _ in range(MAX_HOPS):
            response = await client.get(url)
            if response.is_redirect:
                url = response.next_request.url if response.next_request else None
                if url is None or not _host_allowed(url):
                    return None
                continue
            if response.status_code != 200:
                return None
            data = response.content
            return data if 0 < len(data) <= MAX_BYTES else None
    return None


def _to_jpeg(data: bytes) -> bytes | None:
    try:
        with Image.open(io.BytesIO(data)) as img:
            img = img.convert("RGB")
            img.thumbnail((EDGE, EDGE))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=88)
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    return buffer.getvalue()


async def local_copy(user: User) -> Path | None:
    """A JPEG of this account's photo on our own disk, or None if there isn't one."""
    source = user.avatar_url
    if not source:
        return None

    path = _cache_path(source)
    if path.exists() and _is_fresh(path):
        return path

    try:
        data = await _download(source)
    except httpx.HTTPError as exc:
        log.info("avatar_fetch_failed", error=str(exc))
        data = None

    if data is None:
        # A stale copy beats no picture at all while Telegram is unreachable.
        return path if path.exists() else None

    jpeg = _to_jpeg(data)
    if jpeg is None:
        return path if path.exists() else None

    # Write beside the target and move, so a reader never sees half a file.
    staging = path.with_suffix(".part")
    staging.write_bytes(jpeg)
    staging.replace(path)
    return path
