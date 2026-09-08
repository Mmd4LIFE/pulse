"""Autocomplete for @mentions in the composer."""

from __future__ import annotations


async def suggest(client, q, headers=None):
    response = await client.get(f"/api/v1/search/mentions?q={q}", headers=headers or {})
    assert response.status_code == 200, response.text
    return [u["username"] for u in response.json()]


async def test_a_handle_prefix_matches(client, make_user, as_user) -> None:
    await make_user("maryam", display_name="Maryam Rad")
    await make_user("marcus", display_name="Marcus")
    await make_user("sina", display_name="Sina")

    assert set(await suggest(client, "mar")) == {"maryam", "marcus"}
    assert await suggest(client, "sin") == ["sina"]


async def test_an_exact_handle_comes_first(client, make_user, as_user) -> None:
    await make_user("ali", display_name="Ali")
    await make_user("alireza", display_name="Alireza")
    await make_user("alison", display_name="Alison")

    assert (await suggest(client, "ali"))[0] == "ali"


async def test_people_you_follow_are_offered_first(client, make_user, as_user) -> None:
    """Typing a few letters should surface the person you actually talk to."""
    me = await make_user("me")
    await make_user("sam_stranger", display_name="Sam Stranger")
    friend = await make_user("sam_friend", display_name="Sam Friend")

    # The stranger is more followed, so reach alone would rank them first.
    for i in range(3):
        other = await make_user(f"fan{i}")
        await client.post("/api/v1/users/sam_stranger/follow", headers=as_user(other))

    await client.post(f"/api/v1/users/{friend.username}/follow", headers=as_user(me))

    ranked = await suggest(client, "sam", headers=as_user(me))
    assert ranked[0] == "sam_friend"


async def test_a_display_name_also_matches(client, make_user, as_user) -> None:
    await make_user("nz", display_name="Nazanin")
    assert await suggest(client, "nazan") == ["nz"]


async def test_the_leading_at_sign_is_optional(client, make_user, as_user) -> None:
    await make_user("maryam")
    assert await suggest(client, "%40mar") == ["maryam"]


async def test_blocked_accounts_are_not_offered(client, make_user, as_user) -> None:
    me = await make_user("me")
    await make_user("blocked_one", display_name="Blocked")
    await client.post("/api/v1/users/blocked_one/block", headers=as_user(me))

    assert await suggest(client, "blocked", headers=as_user(me)) == []


async def test_protected_accounts_can_still_be_mentioned(
    client, make_user, as_user
) -> None:
    """Protection hides pulses, not the existence of the handle."""
    owner, stranger = await make_user("quiet"), await make_user("stranger")
    await client.put(
        "/api/v1/users/me/privacy", json={"is_private": True}, headers=as_user(owner)
    )

    assert await suggest(client, "quie", headers=as_user(stranger)) == ["quiet"]


async def test_wildcards_are_treated_literally(client, make_user, as_user) -> None:
    await make_user("plain")
    assert await suggest(client, "%25") == []


async def test_the_list_is_capped(client, make_user, as_user) -> None:
    for i in range(12):
        await make_user(f"person{i}")

    response = await client.get("/api/v1/search/mentions?q=person&limit=5")
    assert len(response.json()) == 5


async def test_a_bare_at_sign_offers_the_people_you_follow(
    client, make_user, as_user
) -> None:
    me = await make_user("me")
    friend = await make_user("friend")
    await make_user("stranger")
    await client.post(f"/api/v1/users/{friend.username}/follow", headers=as_user(me))

    assert await suggest(client, "", headers=as_user(me)) == ["friend"]


async def test_a_bare_at_sign_offers_nothing_to_a_signed_out_reader(
    client, make_user, as_user
) -> None:
    await make_user("someone")
    assert await suggest(client, "") == []
