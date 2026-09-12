"""Protected accounts: who may read what, and how access is granted."""

from __future__ import annotations


async def post(client, user, as_user, **payload):
    return await client.post("/api/v1/pulses", json=payload, headers=as_user(user))


async def protect(client, user, as_user, on=True):
    return await client.put(
        "/api/v1/users/me/privacy", json={"is_private": on}, headers=as_user(user)
    )


async def test_protecting_an_account_hides_its_pulses_from_strangers(
    client, make_user, as_user
) -> None:
    owner, stranger = await make_user("owner"), await make_user("stranger")
    pulse_id = (await post(client, owner, as_user, content="private thoughts")).json()["id"]

    # Public first: everybody can see it.
    explore = (await client.get("/api/v1/feed/explore", headers=as_user(stranger))).json()
    assert [p["id"] for p in explore["items"]] == [pulse_id]

    assert (await protect(client, owner, as_user)).status_code == 200

    explore = (await client.get("/api/v1/feed/explore", headers=as_user(stranger))).json()
    assert explore["items"] == []

    assert (
        await client.get(f"/api/v1/pulses/{pulse_id}", headers=as_user(stranger))
    ).status_code == 403
    assert (
        await client.get("/api/v1/users/owner/pulses", headers=as_user(stranger))
    ).status_code == 403

    # The owner still sees their own.
    own = (await client.get("/api/v1/users/owner/pulses", headers=as_user(owner))).json()
    assert [p["id"] for p in own["items"]] == [pulse_id]


async def test_a_protected_account_is_invisible_to_anonymous_readers(
    client, make_user, as_user
) -> None:
    owner = await make_user("owner")
    await post(client, owner, as_user, content="secret")
    await protect(client, owner, as_user)

    assert (await client.get("/api/v1/feed/explore")).json()["items"] == []
    assert (await client.get("/api/v1/search/pulses?q=secret")).json()["items"] == []
    assert (await client.get("/api/v1/users/owner/pulses")).status_code == 403

    # The profile itself stays discoverable, flagged as protected.
    profile = (await client.get("/api/v1/users/owner")).json()
    assert profile["is_private"] is True
    assert profile["can_view_pulses"] is False


async def test_following_a_protected_account_creates_a_request(
    client, make_user, as_user
) -> None:
    owner, fan = await make_user("owner"), await make_user("fan")
    await post(client, owner, as_user, content="members only")
    await protect(client, owner, as_user)

    response = await client.post("/api/v1/users/owner/follow", headers=as_user(fan))
    assert response.json()["message"] == "Follow request sent."

    # A request is not a follow: still no access, and no follower counted.
    profile = (await client.get("/api/v1/users/owner", headers=as_user(fan))).json()
    assert profile["is_following"] is False
    assert profile["follow_requested"] is True
    assert profile["followers_count"] == 0
    assert (
        await client.get("/api/v1/users/owner/pulses", headers=as_user(fan))
    ).status_code == 403

    pending = (
        await client.get("/api/v1/users/me/follow-requests", headers=as_user(owner))
    ).json()
    assert [u["username"] for u in pending["items"]] == ["fan"]

    inbox = (await client.get("/api/v1/notifications", headers=as_user(owner))).json()
    assert [n["type"] for n in inbox["items"]] == ["follow_request"]


async def test_approving_a_request_grants_access(client, make_user, as_user) -> None:
    owner, fan = await make_user("owner"), await make_user("fan")
    pulse_id = (await post(client, owner, as_user, content="members only")).json()["id"]
    await protect(client, owner, as_user)
    await client.post("/api/v1/users/owner/follow", headers=as_user(fan))

    approved = await client.post(
        "/api/v1/users/me/follow-requests/fan/approve", headers=as_user(owner)
    )
    assert approved.json()["message"] == "Approved."

    profile = (await client.get("/api/v1/users/owner", headers=as_user(fan))).json()
    assert profile["is_following"] is True
    assert profile["followers_count"] == 1
    assert profile["can_view_pulses"] is True

    timeline = (await client.get("/api/v1/users/owner/pulses", headers=as_user(fan))).json()
    assert [p["id"] for p in timeline["items"]] == [pulse_id]

    feed = (await client.get("/api/v1/feed/home", headers=as_user(fan))).json()
    assert [p["id"] for p in feed["items"]] == [pulse_id]

    # The request is consumed, not left pending.
    pending = (
        await client.get("/api/v1/users/me/follow-requests", headers=as_user(owner))
    ).json()
    assert pending["items"] == []


async def test_declining_a_request_leaves_no_access(client, make_user, as_user) -> None:
    owner, fan = await make_user("owner"), await make_user("fan")
    await post(client, owner, as_user, content="members only")
    await protect(client, owner, as_user)
    await client.post("/api/v1/users/owner/follow", headers=as_user(fan))

    await client.post(
        "/api/v1/users/me/follow-requests/fan/decline", headers=as_user(owner)
    )

    profile = (await client.get("/api/v1/users/owner", headers=as_user(fan))).json()
    assert profile["is_following"] is False
    assert profile["follow_requested"] is False
    assert (
        await client.get("/api/v1/users/owner/pulses", headers=as_user(fan))
    ).status_code == 403


async def test_a_requester_can_withdraw(client, make_user, as_user) -> None:
    owner, fan = await make_user("owner"), await make_user("fan")
    await protect(client, owner, as_user)
    await client.post("/api/v1/users/owner/follow", headers=as_user(fan))

    await client.delete("/api/v1/users/owner/follow", headers=as_user(fan))
    pending = (
        await client.get("/api/v1/users/me/follow-requests", headers=as_user(owner))
    ).json()
    assert pending["items"] == []


async def test_existing_followers_keep_access_when_an_account_is_protected(
    client, make_user, as_user
) -> None:
    owner, fan = await make_user("owner"), await make_user("fan")
    pulse_id = (await post(client, owner, as_user, content="still visible")).json()["id"]
    await client.post("/api/v1/users/owner/follow", headers=as_user(fan))

    await protect(client, owner, as_user)

    timeline = (await client.get("/api/v1/users/owner/pulses", headers=as_user(fan))).json()
    assert [p["id"] for p in timeline["items"]] == [pulse_id]


async def test_going_public_admits_everyone_waiting(client, make_user, as_user) -> None:
    owner, a, b = await make_user("owner"), await make_user("ann"), await make_user("bob")
    await protect(client, owner, as_user)
    await client.post("/api/v1/users/owner/follow", headers=as_user(a))
    await client.post("/api/v1/users/owner/follow", headers=as_user(b))

    await protect(client, owner, as_user, on=False)

    profile = (await client.get("/api/v1/users/owner", headers=as_user(a))).json()
    assert profile["is_following"] is True
    assert profile["followers_count"] == 2

    pending = (
        await client.get("/api/v1/users/me/follow-requests", headers=as_user(owner))
    ).json()
    assert pending["items"] == []


async def test_protected_pulses_stay_out_of_search_hashtags_and_trends(
    client, make_user, as_user
) -> None:
    owner, stranger = await make_user("owner"), await make_user("stranger")
    await post(client, owner, as_user, content="findme #quiet")
    await protect(client, owner, as_user)

    assert (
        await client.get("/api/v1/search/pulses?q=findme", headers=as_user(stranger))
    ).json()["items"] == []
    assert (
        await client.get("/api/v1/feed/hashtag/quiet", headers=as_user(stranger))
    ).json()["items"] == []
    assert (await client.get("/api/v1/feed/trends")).json() == []


async def test_a_protected_reply_does_not_leak_through_a_public_thread(
    client, make_user, as_user
) -> None:
    author, quiet, reader = (
        await make_user("author"),
        await make_user("quiet"),
        await make_user("reader"),
    )
    root = (await post(client, author, as_user, content="public root")).json()
    await post(client, quiet, as_user, content="protected reply", reply_to_id=root["id"])
    await protect(client, quiet, as_user)

    thread = (
        await client.get(f"/api/v1/pulses/{root['id']}/thread", headers=as_user(reader))
    ).json()
    assert thread["replies"] == []


async def test_a_protected_pulse_does_not_leak_through_someone_elses_likes(
    client, make_user, as_user
) -> None:
    owner, liker, reader = (
        await make_user("owner"),
        await make_user("liker"),
        await make_user("reader"),
    )
    pulse_id = (await post(client, owner, as_user, content="liked one")).json()["id"]
    await client.post(f"/api/v1/pulses/{pulse_id}/like", headers=as_user(liker))
    await protect(client, owner, as_user)

    likes = (await client.get("/api/v1/users/liker/likes", headers=as_user(reader))).json()
    assert likes["items"] == []


async def test_a_protected_accounts_follower_list_is_private(
    client, make_user, as_user
) -> None:
    owner, fan, stranger = (
        await make_user("owner"),
        await make_user("fan"),
        await make_user("stranger"),
    )
    await client.post("/api/v1/users/owner/follow", headers=as_user(fan))
    await protect(client, owner, as_user)

    assert (
        await client.get("/api/v1/users/owner/followers", headers=as_user(stranger))
    ).status_code == 403
    assert (
        await client.get("/api/v1/users/owner/followers", headers=as_user(fan))
    ).status_code == 200


async def test_the_owner_sees_a_count_of_waiting_requests(
    client, make_user, as_user
) -> None:
    """The badge the settings screen shows has to come back from /auth/me."""
    owner, a, b = await make_user("owner"), await make_user("ann"), await make_user("bob")
    await protect(client, owner, as_user)
    await client.post("/api/v1/users/owner/follow", headers=as_user(a))
    await client.post("/api/v1/users/owner/follow", headers=as_user(b))

    me = (await client.get("/api/v1/auth/me", headers=as_user(owner))).json()
    assert me["pending_follow_requests"] == 2

    await client.post(
        "/api/v1/users/me/follow-requests/ann/approve", headers=as_user(owner)
    )
    me = (await client.get("/api/v1/auth/me", headers=as_user(owner))).json()
    assert me["pending_follow_requests"] == 1


async def test_approving_turns_the_request_notification_into_a_follow(
    client, make_user, as_user
) -> None:
    """The inbox must reflect what happened, not what was once asked."""
    owner, fan = await make_user("owner"), await make_user("fan")
    await protect(client, owner, as_user)
    await client.post("/api/v1/users/owner/follow", headers=as_user(fan))

    inbox = (await client.get("/api/v1/notifications", headers=as_user(owner))).json()
    assert [n["type"] for n in inbox["items"]] == ["follow_request"]

    await client.post(
        "/api/v1/users/me/follow-requests/fan/approve", headers=as_user(owner)
    )

    inbox = (await client.get("/api/v1/notifications", headers=as_user(owner))).json()
    # One row still, but it now says what is true: they follow.
    assert [n["type"] for n in inbox["items"]] == ["follow"]


async def test_declining_removes_the_request_from_the_inbox(
    client, make_user, as_user
) -> None:
    owner, fan = await make_user("owner"), await make_user("fan")
    await protect(client, owner, as_user)
    await client.post("/api/v1/users/owner/follow", headers=as_user(fan))

    await client.post(
        "/api/v1/users/me/follow-requests/fan/decline", headers=as_user(owner)
    )

    inbox = (await client.get("/api/v1/notifications", headers=as_user(owner))).json()
    assert inbox["items"] == []


async def test_the_requester_is_told_their_request_was_accepted(
    client, make_user, as_user
) -> None:
    """Not that the owner followed them, which is not what happened."""
    owner, fan = await make_user("owner"), await make_user("fan")
    await protect(client, owner, as_user)
    await client.post("/api/v1/users/owner/follow", headers=as_user(fan))
    await client.post(
        "/api/v1/users/me/follow-requests/fan/approve", headers=as_user(owner)
    )

    inbox = (await client.get("/api/v1/notifications", headers=as_user(fan))).json()
    assert [n["type"] for n in inbox["items"]] == ["follow_accepted"]
    assert inbox["items"][0]["actor"]["username"] == "owner"


async def test_a_declined_requester_is_told_nothing(client, make_user, as_user) -> None:
    """Silence, the way every other feed handles a decline."""
    owner, fan = await make_user("owner"), await make_user("fan")
    await protect(client, owner, as_user)
    await client.post("/api/v1/users/owner/follow", headers=as_user(fan))
    await client.post(
        "/api/v1/users/me/follow-requests/fan/decline", headers=as_user(owner)
    )

    inbox = (await client.get("/api/v1/notifications", headers=as_user(fan))).json()
    assert inbox["items"] == []
