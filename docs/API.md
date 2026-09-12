# API reference

Base path `/api/v1`. Interactive docs are served at `/docs` outside production.

All authenticated calls take `Authorization: Bearer <access_token>`.
List endpoints are cursor-paged: pass `?limit=` (1–50, default 20) and
`?cursor=` from the previous response's `next_cursor`.

## Errors

Every failure returns the same envelope:

```json
{ "error": { "code": "not_found", "message": "Pulse not found." } }
```

Validation failures add a `details` array of `{ field, message }`.

| Status | `code` | Meaning |
|---|---|---|
| 401 | `unauthenticated` | Missing, expired or invalid token |
| 403 | `forbidden` | Not yours, or blocked |
| 404 | `not_found` | No such resource |
| 409 | `conflict` | Username taken |
| 422 | `validation_error` | Bad payload |
| 429 | `rate_limited` | Posting too fast |

## Auth

| Method | Path | Notes |
|---|---|---|
| `POST` | `/auth/telegram` | Body `{ "init_data": "<raw initData>" }`. Returns tokens plus the user and `is_new_user`. |
| `POST` | `/auth/dev` | Unsigned login. Only when `ALLOW_DEV_LOGIN=true` and not production. |
| `POST` | `/auth/refresh` | Body `{ "refresh_token": "…" }`. |
| `GET` | `/auth/me` | The signed-in account. |

## Pulses

| Method | Path | Notes |
|---|---|---|
| `POST` | `/pulses` | `{ content, reply_to_id?, quote_of_id?, media_ids?, post_to_channel? }`. A pulse cannot be both a reply and a quote. `post_to_channel` mirrors it into the author's connected channel, after the response. |
| `GET` | `/pulses/{id}` | |
| `GET` | `/pulses/{id}/thread` | Ancestors, the pulse, and its direct replies. |
| `GET` | `/pulses/{id}/replies` | Paged, oldest first. |
| `DELETE` | `/pulses/{id}` | Author only. Soft delete. |
| `POST`/`DELETE` | `/pulses/{id}/like` | |
| `POST`/`DELETE` | `/pulses/{id}/repulse` | Reposting a repost boosts the original. |
| `POST`/`DELETE` | `/pulses/{id}/bookmark` | |

Interaction endpoints are idempotent: repeating them reports "Already …"
rather than failing or double-counting.

## Feeds

| Method | Path | Notes |
|---|---|---|
| `GET` | `/feed/home` | Followed accounts plus your own. Top-level only. Reposts collapse per page. |
| `GET` | `/feed/explore` | Public, top-level, newest first. |
| `GET` | `/feed/bookmarks` | Private to you. |
| `GET` | `/feed/trends` | Hashtags used in the last 48 hours. |
| `GET` | `/feed/hashtag/{tag}` | |

## People

| Method | Path | Notes |
|---|---|---|
| `GET` | `/users/{username}` | Includes `is_following` / `is_followed_by` relative to the caller. |
| `PATCH` | `/users/me` | `username`, `display_name`, `bio`, `location`, `website`. |
| `POST`/`DELETE` | `/users/{username}/follow` | |
| `POST`/`DELETE` | `/users/{username}/block` | A block drops the follow edges both ways. |
| `GET` | `/users/{username}/followers` · `/following` | |
| `GET` | `/users/{username}/pulses` · `/replies` · `/media` · `/likes` | |
| `GET` | `/users/suggestions` | |
| `PUT` | `/users/me/privacy` | `{ "is_private": true }`. Going public approves everyone waiting. |
| `GET` | `/users/me/follow-requests` · `/count` | Pending requests to follow you. |
| `POST` | `/users/me/follow-requests/{username}/approve` · `/decline` | |

Following a protected account returns `"Follow request sent."` rather than
following it. Its pulses, followers and following lists answer `403`
`protected_account` until the request is approved; `UserPublic.can_view_pulses`
says up front whether they are readable, so the app can show a lock instead of
provoking the error.

## Channels

| Method | Path | Notes |
|---|---|---|
| `GET` | `/channels/me` | The connected channel, or `null`. |
| `PUT` | `/channels/me` | `{ "reference": "@yourchannel" }`. Also accepts a t.me link or a `-100…` id. |
| `DELETE` | `/channels/me` | |
| `POST` | `/channels/me/test` | Posts a short message to prove the link works. |

Connecting verifies through the Bot API that the channel exists, is a channel
rather than a group, and that the bot is an administrator there with
`can_post_messages`. Anything else fails at connection time rather than
silently dropping posts later. A channel can belong to one account only.

## Search and notifications

| Method | Path | Notes |
|---|---|---|
| `GET` | `/search?q=` | Blended users + pulses + hashtags. |
| `GET` | `/search/users?q=` · `/search/pulses?q=` | Paged. |
| `GET` | `/search/mentions?q=` | Composer autocomplete. Ranked for mentions: exact handle, then accounts you follow, then reach. A bare `q=` returns the accounts you follow. |
| `GET` | `/notifications` | `?unread_only=true`, `?kind=like&kind=reply`. |
| `GET` | `/notifications/unread-count` | |
| `POST` | `/notifications/read-all` | |

## Media

`POST /media` — multipart with `file` and optional `alt_text`. Returns
`{ id, url, … }`; pass the id in `media_ids` when creating a pulse. Uploads are
verified as real images by decoding them, not by trusting the filename or the
declared content type, and each may be attached to one pulse only.

## Operations

`GET /health` — liveness, does not touch the database.
`GET /ready` — readiness, runs `SELECT 1`.
