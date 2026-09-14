"""Sharing a pulse as a picture.

The Bot API is stubbed. What matters here is what we hand Telegram: a picture
we have checked, belonging to a pulse the sharer is allowed to see, addressed
to the sharer's own account.
"""

from __future__ import annotations

import io
from datetime import UTC, date, datetime, timedelta

import pytest
from PIL import Image

from app.core import botapi
from app.core.config import settings
from app.core.errors import ValidationError
from app.services import share


def card_bytes(width: int = 600, height: int = 400, fmt: str = "JPEG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (20, 80, 200)).save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
    monkeypatch.setattr(settings, "PUBLIC_WEB_URL", "https://pulse.example/")
    return tmp_path


@pytest.fixture
def telegram(monkeypatch):
    calls: list[tuple[str, dict]] = []

    async def fake(method: str, payload: dict):
        calls.append((method, payload))
        return {
            "id": "prepared-1",
            "expiration_date": int(datetime.now(UTC).timestamp()) + 3600,
        }

    monkeypatch.setattr(botapi, "call", fake)
    return calls


# --- what we are willing to store ----------------------------------------


def test_a_stored_card_gets_an_absolute_public_url(media_root) -> None:
    url = share.store_card(card_bytes())

    assert url.startswith("https://pulse.example/media/cards/")
    key = url.removeprefix("https://pulse.example/media/")
    assert (media_root / key).read_bytes() == card_bytes()


def test_only_jpeg_is_accepted() -> None:
    # Telegram fetches an inline photo by URL and insists on JPEG, so anything
    # else would be prepared successfully and then fail on send.
    with pytest.raises(ValidationError):
        share.store_card(card_bytes(fmt="PNG"))


def test_something_that_is_not_an_image_is_refused() -> None:
    with pytest.raises(ValidationError):
        share.store_card(b"<html>not a picture</html>")


def test_an_empty_card_is_refused() -> None:
    with pytest.raises(ValidationError):
        share.store_card(b"")


def test_an_absurdly_large_card_is_refused() -> None:
    with pytest.raises(ValidationError):
        share.store_card(card_bytes(width=4000, height=400))


def test_old_cards_are_swept_and_recent_ones_kept(media_root) -> None:
    root = media_root / "cards"
    today = date(2026, 5, 20)
    stale = root / (today - timedelta(days=90)).isoformat()
    fresh = root / (today - timedelta(days=2)).isoformat()
    for folder in (stale, fresh):
        folder.mkdir(parents=True)
        (folder / "card.jpg").write_bytes(b"x")
    (root / "not-a-date").mkdir()

    share._sweep(root, today)

    assert not stale.exists()
    assert fresh.exists()
    assert (root / "not-a-date").exists()


# --- what we ask Telegram to hold ----------------------------------------


async def test_sharing_a_pulse_prepares_a_message_for_the_sharer(
    client, make_user, as_user, telegram
) -> None:
    author = await make_user("writer")
    sharer = await make_user("reader")
    created = await client.post(
        "/api/v1/pulses", json={"content": "worth passing on"}, headers=as_user(author)
    )
    pulse_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/pulses/{pulse_id}/share-card",
        files={"file": ("card.jpg", card_bytes(), "image/jpeg")},
        headers=as_user(sharer),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["prepared_message_id"] == "prepared-1"
    assert body["link"].endswith(f"start=pulse_{pulse_id}")
    assert body["image_url"].startswith("https://pulse.example/media/cards/")

    method, payload = telegram[0]
    assert method == "savePreparedInlineMessage"
    # Addressed to the person sharing, not to the author of the pulse.
    assert payload["user_id"] == sharer.telegram_id
    assert payload["result"]["photo_url"] == body["image_url"]
    assert (
        payload["result"]["reply_markup"]["inline_keyboard"][0][0]["url"] == (body["link"])
    )


async def test_a_protected_pulse_cannot_be_shared_by_an_outsider(
    client, make_user, as_user, telegram
) -> None:
    author = await make_user("shy", is_private=True)
    outsider = await make_user("nosy")
    created = await client.post(
        "/api/v1/pulses", json={"content": "for my circle"}, headers=as_user(author)
    )
    pulse_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/pulses/{pulse_id}/share-card",
        files={"file": ("card.jpg", card_bytes(), "image/jpeg")},
        headers=as_user(outsider),
    )

    assert response.status_code == 403
    assert telegram == []


async def test_a_failure_at_telegram_is_reported_as_a_refusal_not_a_crash(
    client, make_user, as_user, monkeypatch
) -> None:
    async def fails(method: str, payload: dict):
        raise botapi.TelegramApiError("USER_ID_INVALID")

    monkeypatch.setattr(botapi, "call", fails)
    user = await make_user("solo")
    created = await client.post(
        "/api/v1/pulses", json={"content": "hello"}, headers=as_user(user)
    )

    response = await client.post(
        f"/api/v1/pulses/{created.json()['id']}/share-card",
        files={"file": ("card.jpg", card_bytes(), "image/jpeg")},
        headers=as_user(user),
    )

    assert response.status_code == 422
    assert "link" in response.json()["error"]["message"].lower()
