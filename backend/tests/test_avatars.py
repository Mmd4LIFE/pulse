"""Serving a profile photo from our own origin.

The point of the mirror is that a canvas can read the result, so what matters
is that we only ever fetch where the account row points, that every hop of
Telegram's redirect is checked, and that a photo already on disk is reused.
"""

from __future__ import annotations

import io

import httpx
import pytest
from PIL import Image

from app.core.config import settings
from app.services import avatars

TELEGRAM_URL = "https://t.me/i/userpic/320/abc.svg"
CDN_URL = "https://cdn1.telesco.pe/file/abc.jpg"


def photo_bytes(size: int = 640) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (size, size), (200, 30, 90)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
    return tmp_path


class Transport(httpx.AsyncBaseTransport):
    """Answers the two hops Telegram actually uses, and records them."""

    def __init__(self, redirect_to: str | None = CDN_URL, body: bytes | None = None):
        self.redirect_to = redirect_to
        self.body = photo_bytes() if body is None else body
        self.seen: list[str] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(str(request.url))
        if request.url.host == "t.me" and self.redirect_to:
            return httpx.Response(302, headers={"location": self.redirect_to})
        return httpx.Response(200, content=self.body)


@pytest.fixture
def telegram(monkeypatch):
    def install(transport: Transport) -> Transport:
        original = httpx.AsyncClient

        def client(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        monkeypatch.setattr(avatars.httpx, "AsyncClient", client)
        return transport

    return install


async def test_a_photo_is_fetched_through_the_redirect_and_kept(
    make_user, telegram
) -> None:
    seen = telegram(Transport())
    user = await make_user("pictured", avatar_url=TELEGRAM_URL)

    path = await avatars.local_copy(user)

    assert path is not None and path.exists()
    assert seen.seen == [TELEGRAM_URL, CDN_URL]
    with Image.open(path) as img:
        assert img.format == "JPEG"
        # Scaled down to what a card needs rather than kept at full size.
        assert max(img.size) == avatars.EDGE


async def test_a_kept_photo_is_not_fetched_again(make_user, telegram) -> None:
    seen = telegram(Transport())
    user = await make_user("pictured", avatar_url=TELEGRAM_URL)

    first = await avatars.local_copy(user)
    second = await avatars.local_copy(user)

    assert first == second
    assert len(seen.seen) == 2  # the first call's two hops, and no more


async def test_a_redirect_off_telegram_is_refused(make_user, telegram) -> None:
    # The address comes from our own rows, but a hop we follow does not: an
    # open redirect would otherwise make this endpoint fetch anything at all.
    seen = telegram(Transport(redirect_to="https://127.0.0.1:8000/internal"))
    user = await make_user("pictured", avatar_url=TELEGRAM_URL)

    assert await avatars.local_copy(user) is None
    assert seen.seen == [TELEGRAM_URL]


async def test_an_account_photo_hosted_somewhere_else_is_never_fetched(
    make_user, telegram
) -> None:
    seen = telegram(Transport())
    user = await make_user("odd", avatar_url="https://example.com/evil.jpg")

    assert await avatars.local_copy(user) is None
    assert seen.seen == []


async def test_an_account_with_no_photo_has_nothing_to_serve(make_user) -> None:
    user = await make_user("plain")
    assert await avatars.local_copy(user) is None


async def test_the_endpoint_serves_the_photo_to_anyone(client, make_user, telegram) -> None:
    telegram(Transport())
    await make_user("pictured", avatar_url=TELEGRAM_URL)

    # No Authorization header: a browser loading an <img> sends none.
    response = await client.get("/api/v1/users/pictured/avatar")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content[:2] == b"\xff\xd8"  # JPEG magic


async def test_the_endpoint_is_a_plain_404_when_there_is_no_photo(
    client, make_user
) -> None:
    await make_user("plain")
    response = await client.get("/api/v1/users/plain/avatar")
    assert response.status_code == 404
