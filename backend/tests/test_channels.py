"""Connecting a channel, and mirroring pulses into it.

The Bot API is stubbed: these tests are about our rules — that a channel is
only accepted when the bot can actually post, that mirroring is opt-in per
pulse, and that a failed delivery never fails the post.
"""

from __future__ import annotations

import pytest

from app.services import channels as service


class FakeTelegram:
    """Stands in for the Bot API, recording what would have been sent."""

    def __init__(self, **responses):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, method: str, payload: dict):
        self.calls.append((method, payload))
        result = self.responses.get(method)
        if isinstance(result, Exception):
            raise result
        if result is None:
            raise service.TelegramApiError(f"no stub for {method}")
        return result

    def sent_texts(self) -> list[str]:
        return [p["text"] for m, p in self.calls if m == "sendMessage"]


def working_channel(**overrides):
    responses = {
        "getMe": {"id": 4242, "username": "pulsebot"},
        "getChat": {
            "id": -1001234567890,
            "type": "channel",
            "title": "My Channel",
            "username": "mychannel",
        },
        "getChatMember": {"status": "administrator", "can_post_messages": True},
        "sendMessage": {"message_id": 7},
    }
    responses.update(overrides)
    return FakeTelegram(**responses)


@pytest.fixture
def telegram(monkeypatch):
    def install(fake):
        monkeypatch.setattr(service, "_call", fake)
        return fake

    return install


async def post(client, user, as_user, **payload):
    return await client.post("/api/v1/pulses", json=payload, headers=as_user(user))


# --- connecting -----------------------------------------------------------


def test_a_channel_reference_is_accepted_in_the_forms_people_paste() -> None:
    for given in ("@mychannel", "mychannel", "https://t.me/mychannel", "t.me/mychannel/"):
        assert service.normalise_reference(given) == "@mychannel"
    assert service.normalise_reference("-1001234567890") == "-1001234567890"


def test_a_nonsense_reference_is_rejected() -> None:
    from app.core.errors import ValidationError

    for given in ("", "  ", "a b c", "@x", "https://example.com/foo"):
        with pytest.raises(ValidationError):
            service.normalise_reference(given)


async def test_connecting_a_channel_the_bot_can_post_to(
    client, make_user, as_user, telegram
) -> None:
    telegram(working_channel())
    user = await make_user("owner")

    response = await client.put(
        "/api/v1/channels/me", json={"reference": "@mychannel"}, headers=as_user(user)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["chat_id"] == -1001234567890
    assert body["username"] == "mychannel"
    assert body["can_post"] is True

    mine = (await client.get("/api/v1/channels/me", headers=as_user(user))).json()
    assert mine["title"] == "My Channel"


async def test_a_channel_without_the_bot_as_admin_is_refused(
    client, make_user, as_user, telegram
) -> None:
    telegram(working_channel(getChatMember={"status": "member"}))
    user = await make_user("owner")

    response = await client.put(
        "/api/v1/channels/me", json={"reference": "@mychannel"}, headers=as_user(user)
    )
    assert response.status_code == 422
    assert "administrator" in response.json()["error"]["message"]
    assert (await client.get("/api/v1/channels/me", headers=as_user(user))).json() is None


async def test_an_admin_without_post_rights_is_refused(
    client, make_user, as_user, telegram
) -> None:
    telegram(
        working_channel(
            getChatMember={"status": "administrator", "can_post_messages": False}
        )
    )
    user = await make_user("owner")

    response = await client.put(
        "/api/v1/channels/me", json={"reference": "@mychannel"}, headers=as_user(user)
    )
    assert response.status_code == 422
    assert "Post Messages" in response.json()["error"]["message"]


async def test_a_group_is_not_a_channel(client, make_user, as_user, telegram) -> None:
    telegram(
        working_channel(getChat={"id": -100111, "type": "supergroup", "title": "Chat"})
    )
    user = await make_user("owner")

    response = await client.put(
        "/api/v1/channels/me", json={"reference": "@somegroup"}, headers=as_user(user)
    )
    assert response.status_code == 422
    assert "only post to channels" in response.json()["error"]["message"]


async def test_two_accounts_cannot_claim_the_same_channel(
    client, make_user, as_user, telegram
) -> None:
    telegram(working_channel())
    first, second = await make_user("first"), await make_user("second")

    assert (
        await client.put(
            "/api/v1/channels/me", json={"reference": "@mychannel"}, headers=as_user(first)
        )
    ).status_code == 200
    clash = await client.put(
        "/api/v1/channels/me", json={"reference": "@mychannel"}, headers=as_user(second)
    )
    assert clash.status_code == 409


async def test_disconnecting_a_channel(client, make_user, as_user, telegram) -> None:
    telegram(working_channel())
    user = await make_user("owner")
    await client.put(
        "/api/v1/channels/me", json={"reference": "@mychannel"}, headers=as_user(user)
    )

    assert (
        await client.delete("/api/v1/channels/me", headers=as_user(user))
    ).status_code == 200
    assert (await client.get("/api/v1/channels/me", headers=as_user(user))).json() is None


# --- mirroring ------------------------------------------------------------


async def test_a_pulse_is_only_mirrored_when_asked(
    client, make_user, as_user, telegram
) -> None:
    fake = telegram(working_channel())
    user = await make_user("owner")
    await client.put(
        "/api/v1/channels/me", json={"reference": "@mychannel"}, headers=as_user(user)
    )
    fake.calls.clear()

    await post(client, user, as_user, content="kept to myself")
    assert fake.sent_texts() == []

    await post(client, user, as_user, content="shared widely", post_to_channel=True)
    texts = fake.sent_texts()
    assert len(texts) == 1
    assert "shared widely" in texts[0]
    assert "@owner" in texts[0]


async def test_asking_to_mirror_without_a_channel_is_harmless(
    client, make_user, as_user, telegram
) -> None:
    fake = telegram(working_channel())
    user = await make_user("owner")

    response = await post(
        client, user, as_user, content="no channel here", post_to_channel=True
    )
    assert response.status_code == 201
    assert fake.sent_texts() == []


async def test_a_failed_delivery_does_not_fail_the_pulse(
    client, make_user, as_user, telegram
) -> None:
    fake = telegram(working_channel())
    user = await make_user("owner")
    await client.put(
        "/api/v1/channels/me", json={"reference": "@mychannel"}, headers=as_user(user)
    )

    # Telegram starts refusing: the bot was demoted after connecting.
    fake.responses["sendMessage"] = service.TelegramApiError(
        "Bad Request: not enough rights to send text messages to the chat"
    )

    response = await post(
        client, user, as_user, content="still posted", post_to_channel=True
    )
    assert response.status_code == 201
    assert response.json()["content"] == "still posted"

    # The failure is recorded so the UI can explain it.
    channel = (await client.get("/api/v1/channels/me", headers=as_user(user))).json()
    assert channel["can_post"] is False
    assert "not enough rights" in channel["last_error"]


async def test_the_channel_message_links_back_into_the_app(
    client, make_user, as_user, telegram
) -> None:
    fake = telegram(working_channel())
    user = await make_user("owner")
    await client.put(
        "/api/v1/channels/me", json={"reference": "@mychannel"}, headers=as_user(user)
    )
    fake.calls.clear()

    created = await post(client, user, as_user, content="read this", post_to_channel=True)
    pulse_id = created.json()["id"]

    text = fake.sent_texts()[0]
    # The bot already resolves ?start=pulse_<id> into an in-app route.
    assert f"start=pulse_{pulse_id}" in text


async def test_html_in_a_pulse_is_escaped_before_it_reaches_telegram(
    client, make_user, as_user, telegram
) -> None:
    fake = telegram(working_channel())
    user = await make_user("owner")
    await client.put(
        "/api/v1/channels/me", json={"reference": "@mychannel"}, headers=as_user(user)
    )
    fake.calls.clear()

    await post(
        client, user, as_user, content="<b>bold</b> & <script>", post_to_channel=True
    )
    text = fake.sent_texts()[0]
    assert "&lt;b&gt;bold&lt;/b&gt;" in text
    assert "&amp;" in text
    assert "<script>" not in text
