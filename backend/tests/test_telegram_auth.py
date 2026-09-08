"""The initData trust boundary."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.core.telegram import InitDataError, verify_init_data

BOT_TOKEN = "123456:TEST-TOKEN"


def sign(fields: dict[str, str], token: str = BOT_TOKEN) -> str:
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": digest})


def make_init_data(**overrides) -> str:
    user = {
        "id": 4242,
        "first_name": "Ada",
        "last_name": "Lovelace",
        "username": "ada",
        "language_code": "en",
    }
    fields = {
        "user": json.dumps(user, separators=(",", ":")),
        "auth_date": str(int(time.time())),
        "query_id": "AAF-test",
    }
    fields.update(overrides)
    return sign(fields)


def test_accepts_a_correctly_signed_payload() -> None:
    data = verify_init_data(make_init_data(), BOT_TOKEN)
    assert data.user.id == 4242
    assert data.user.username == "ada"
    assert data.user.display_name == "Ada Lovelace"


def test_rejects_a_tampered_field() -> None:
    signed = make_init_data()
    tampered = signed.replace("Ada", "Eve")
    with pytest.raises(InitDataError, match="signature"):
        verify_init_data(tampered, BOT_TOKEN)


def test_rejects_a_payload_signed_with_another_bot_token() -> None:
    other = sign(
        {
            "user": json.dumps({"id": 1, "first_name": "Mallory"}),
            "auth_date": str(int(time.time())),
        },
        token="999999:OTHER-TOKEN",
    )
    with pytest.raises(InitDataError, match="signature"):
        verify_init_data(other, BOT_TOKEN)


def test_rejects_a_payload_with_no_hash() -> None:
    with pytest.raises(InitDataError, match="hash"):
        verify_init_data("user=%7B%22id%22%3A1%7D&auth_date=1", BOT_TOKEN)


def test_rejects_stale_init_data() -> None:
    old = make_init_data(auth_date=str(int(time.time()) - 90_000))
    with pytest.raises(InitDataError, match="expired"):
        verify_init_data(old, BOT_TOKEN, max_age_seconds=86_400)


def test_rejects_an_auth_date_from_the_future() -> None:
    ahead = make_init_data(auth_date=str(int(time.time()) + 3_600))
    with pytest.raises(InitDataError, match="future"):
        verify_init_data(ahead, BOT_TOKEN)


def test_signature_field_is_excluded_from_the_check_string() -> None:
    """Telegram's Ed25519 ``signature`` must not take part in the HMAC."""
    fields = {
        "user": json.dumps({"id": 7, "first_name": "Grace"}),
        "auth_date": str(int(time.time())),
    }
    signed = sign(fields)
    with_sig = signed + "&signature=" + "a" * 64
    assert verify_init_data(with_sig, BOT_TOKEN).user.id == 7


def test_rejects_empty_input() -> None:
    with pytest.raises(InitDataError):
        verify_init_data("", BOT_TOKEN)


async def test_login_endpoint_creates_an_account(client) -> None:
    response = await client.post(
        "/api/v1/auth/telegram", json={"init_data": make_init_data()}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_new_user"] is True
    assert body["user"]["username"] == "ada"
    assert body["access_token"]

    # A second login reuses the same account.
    again = await client.post("/api/v1/auth/telegram", json={"init_data": make_init_data()})
    assert again.json()["is_new_user"] is False
    assert again.json()["user"]["id"] == body["user"]["id"]


async def test_login_endpoint_rejects_a_forged_payload(client) -> None:
    forged = make_init_data().replace("Ada", "Eve")
    response = await client.post("/api/v1/auth/telegram", json={"init_data": forged})
    assert response.status_code == 401
    # The specific reason is logged, not returned.
    assert "signature" not in response.text.lower()


async def test_protected_route_requires_a_token(client) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nonsense"})
    ).status_code == 401
