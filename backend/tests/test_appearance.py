"""The per-account reading text size."""

from __future__ import annotations


async def test_the_default_is_the_small_size(client, make_user, as_user) -> None:
    user = await make_user("reader")
    me = (await client.get("/api/v1/auth/me", headers=as_user(user))).json()
    assert me["text_size"] == "small"


async def test_a_reader_can_change_it(client, make_user, as_user) -> None:
    user = await make_user("reader")

    response = await client.put(
        "/api/v1/users/me/appearance",
        json={"text_size": "large"},
        headers=as_user(user),
    )
    assert response.status_code == 200, response.text
    assert response.json()["text_size"] == "large"

    # It sticks, so the choice follows the reader to another device.
    me = (await client.get("/api/v1/auth/me", headers=as_user(user))).json()
    assert me["text_size"] == "large"


async def test_an_unknown_size_is_rejected(client, make_user, as_user) -> None:
    user = await make_user("reader")
    response = await client.put(
        "/api/v1/users/me/appearance",
        json={"text_size": "enormous"},
        headers=as_user(user),
    )
    assert response.status_code == 422


async def test_it_is_private_to_the_owner(client, make_user, as_user) -> None:
    """A reading preference is nobody else's business."""
    owner, other = await make_user("owner"), await make_user("other")
    await client.put(
        "/api/v1/users/me/appearance", json={"text_size": "xlarge"}, headers=as_user(owner)
    )

    profile = (await client.get("/api/v1/users/owner", headers=as_user(other))).json()
    assert "text_size" not in profile


async def test_signing_in_needs_no_extra_round_trip(client, make_user, as_user) -> None:
    """The size comes back with the session, so the app can apply it at once."""
    user = await make_user("reader", telegram_id=54321)
    await client.put(
        "/api/v1/users/me/appearance", json={"text_size": "medium"}, headers=as_user(user)
    )

    session = await client.post("/api/v1/auth/dev", json={"telegram_id": 54321})
    assert session.json()["user"]["text_size"] == "medium"
