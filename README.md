# Pulse

A short-form social feed — think X/Twitter — that runs as a **Telegram Mini App**.
No install, no signup: it opens inside Telegram and you are already signed in.

<p align="center">
  <em>FastAPI · PostgreSQL · Alembic · Next.js · Tailwind · shadcn/ui · Docker</em>
</p>

---

## What it does

| | |
|---|---|
| **Pulses** | Post up to 280 characters with up to 4 images |
| **Threads** | Reply to anything; the whole conversation is one indexed lookup |
| **Repulse** | Repost, or quote with your own take |
| **Follow** | A home timeline built only from accounts you follow |
| **Discover** | Explore feed, trending hashtags, suggested accounts |
| **Search** | People, pulses and hashtags |
| **Notifications** | Likes, replies, repulses, quotes, follows, mentions — with an unread badge |
| **Bookmarks** | Private saves |
| **Blocking** | Hides both accounts from each other everywhere |
| **Profiles** | Editable handle, bio, location, website; Pulses / Replies / Media / Likes tabs |

The interface follows the host client: it reads Telegram's colour scheme and
theme parameters, uses the native back button, haptics and confirm dialogs, and
respects the safe-area insets.

## How authentication works

Telegram hands the Mini App a signed `initData` query string. The backend
verifies it with `HMAC-SHA256(key=HMAC-SHA256("WebAppData", bot_token), …)` and
compares in constant time before anything is parsed out of it. Only then is a
JWT pair issued.

This is the single trust boundary in the system, so it is deliberately strict:
stale payloads are rejected, `auth_date` from the future is rejected, and the
Ed25519 `signature` field is excluded from the check string, as Telegram
specifies. See [`backend/app/core/telegram.py`](backend/app/core/telegram.py)
and the tests in [`backend/tests/test_telegram_auth.py`](backend/tests/test_telegram_auth.py).

## Architecture

```
Telegram client
      │  https://<your-domain>
      ▼
Cloudflare Tunnel ──▶ nginx :8094 (loopback only)
                        ├── /api/…      ──▶ FastAPI (gunicorn + uvicorn workers)
                        ├── /media/…    ──▶ uploaded images, straight off disk
                        └── /…          ──▶ Next.js (standalone server)
                                              │
                                    PostgreSQL 16 · Redis
```

* **`backend/`** — FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2.
  Routes stay thin; everything that touches the database lives in `services/`.
* **`frontend/`** — Next.js App Router, TypeScript, Tailwind, shadcn/ui
  primitives, TanStack Query with optimistic interactions.
* **`bot/`** — aiogram 3. Publishes the menu button and turns deep links into
  in-app routes.

### Design notes worth knowing

* **One table for four things.** A post, reply, repost and quote are all rows in
  `pulses`, distinguished by which parent column is set. A timeline is then a
  single index scan rather than a union.
* **Cursor pagination everywhere.** Pages key off the monotonic pulse id, so the
  feed does not shift under the reader when new pulses arrive at the head.
* **Counters are denormalised** and maintained in the service layer, so
  rendering a timeline never runs an aggregate per row.
* **No N+1 in the feed.** Viewer-relative flags (`is_liked`, `is_bookmarked`,
  `is_repulsed`) are resolved for an entire page in three set-membership
  queries — see `services/serializers.py`.
* **Reposts collapse per page.** Three people boosting the same pulse renders
  one card, not three.
* **Soft deletes.** A deleted pulse still anchors its replies, so threads never
  lose their shape.

## Running it locally

Requirements: Docker with Compose v2.

```bash
git clone https://github.com/Mmd4LIFE/pulse.git && cd pulse
cp .env.example .env          # then set TELEGRAM_BOT_TOKEN and SECRET_KEY
docker compose up -d --build
```

The app is then on <http://localhost:8094>.

Outside Telegram there is no `initData`, so the frontend falls back to a
development login. The backend only honours it when `ALLOW_DEV_LOGIN=true`, and
refuses it outright in production.

```bash
make help          # every task
make logs S=api    # follow one service
make test          # backend test suite
make lint          # ruff + eslint + tsc
```

### Working on the code directly

```bash
python -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8010

cd frontend && npm install && npm run dev
```

## Database migrations

Alembic owns the schema; the `migrate` service runs `alembic upgrade head` to
completion before the API is allowed to start, so the two can never be out of
step.

```bash
make revision M="add polls"   # autogenerate
make migrate                  # apply
```

## Deploying

`deploy/bootstrap.sh` sets a host up once; `deploy/deploy.sh` ships subsequent
changes. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the full runbook,
including the Cloudflare Tunnel and BotFather steps.

```bash
./deploy/deploy.sh
```

## Configuration

Every setting is an environment variable; [`.env.example`](.env.example) is the
annotated reference. The ones that matter most:

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Signs and verifies `initData`. The whole auth model rests on it. |
| `SECRET_KEY` | Signs the JWTs. At least 32 characters, random. |
| `PUBLIC_WEB_URL` | The HTTPS origin Telegram opens. Must be https. |
| `ALLOW_DEV_LOGIN` | Unsigned login for local work. Never enable in production. |
| `WEB_PORT` / `DB_PORT` | Host ports, bound to loopback only. |

## Tests

```bash
make test
```

39 tests covering signature verification and forgery, timelines and cursor
paging, threads, the follow graph, blocking in both directions, notification
fan-out, permissions, and search escaping. They run against a real PostgreSQL
database, because the schema depends on partial indexes and boolean-to-int
casts that another engine would not exercise.

## Licence

MIT — see [LICENSE](LICENSE).
