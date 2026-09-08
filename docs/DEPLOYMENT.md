# Deployment runbook

How Pulse is deployed on the shared application host, and what to do when
something needs changing.

## The host

The box already runs several projects. Pulse follows the conventions the others
established, so nothing collides:

* every project lives in `/root/mk-projects/<name>`
* each publishes **one** HTTP port, bound to `127.0.0.1` only
* a Cloudflare Tunnel per project terminates TLS and reaches that port
* Postgres is published on loopback only, for `psql` and backups

Pulse's allocation:

| Service | Host port | Bound to |
|---|---|---|
| nginx (the app) | `8094` | `127.0.0.1` |
| PostgreSQL | `5434` | `127.0.0.1` |
| Redis | — | container network only |

Both were verified free before being chosen. To re-check before changing them:

```bash
ss -tulpn | grep LISTEN | sort -t: -k2 -n
```

## First-time setup

```bash
ssh root@<host>
export PULSE_DOMAIN=pulse.mammad.site
curl -fsSL https://raw.githubusercontent.com/Mmd4LIFE/pulse/main/deploy/bootstrap.sh | bash
```

Or manually:

```bash
git clone https://github.com/Mmd4LIFE/pulse.git /root/mk-projects/pulse
cd /root/mk-projects/pulse
./deploy/bootstrap.sh
```

The script refuses to continue if either port is taken, generates `SECRET_KEY`
and the database password, and writes `.env` with `chmod 600`. Fill in
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME`, then:

```bash
docker compose up -d --build
```

## The Cloudflare Tunnel

The tunnel is *remotely managed*: it authenticates with a token and takes its
ingress rules from the Cloudflare dashboard, not from a file on the host.

Install it as its own systemd unit, matching the other projects on this box:

```bash
install -d -m 700 /etc/cloudflared
printf '%s' '<TUNNEL_TOKEN>' > /etc/cloudflared/pulse-token
chmod 600 /etc/cloudflared/pulse-token

cp deploy/cloudflared-pulse.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cloudflared-pulse
systemctl status cloudflared-pulse --no-pager
```

### Pointing the hostname at the app — the one manual step

A token-managed tunnel takes its ingress rules from Cloudflare, not from disk.
Until a public hostname is attached, `cloudflared` says so plainly at startup:

```
WRN No ingress rules were defined in provided config (if any) nor from the cli,
    cloudflared will return 503 for all incoming HTTP requests
```

Fix it in the dashboard — **Zero Trust → Networks → Tunnels →** the Pulse
tunnel (`df7e295c-df95-40f4-9861-90c66b4d63f7`) **→ Public Hostname → Add**:

| Field | Value |
|---|---|
| Subdomain | `pulse` |
| Domain | `mammad.site` |
| Path | *(leave empty)* |
| Type | `HTTP` |
| URL | `localhost:8094` |

Saving this also creates the `pulse.mammad.site` DNS record, so nothing else is
needed. `cloudflared` picks the change up within seconds — no restart:

```bash
journalctl -u cloudflared-pulse -n 20 --no-pager | grep "Updated to new configuration"
```

Then verify the whole path from outside:

```bash
curl -fsS https://pulse.mammad.site/health
PULSE_BASE=https://pulse.mammad.site ./deploy/verify.sh
```

## Telling Telegram about the app

With BotFather:

1. `/setmenubutton` → pick the bot → the URL `https://pulse.mammad.site`
   (the bot also sets this itself on every start).
2. `/newapp` → pick the bot → title, description, a 640×360 image, and the
   same URL. This gives the app a `t.me/<bot>/<short-name>` direct link.
3. `/setdomain` → pick the bot → `pulse.mammad.site`.

Telegram will only open an **https** URL, so the tunnel has to be live first.

## Shipping a change

From a laptop, on the branch you want live:

```bash
./deploy/deploy.sh
```

It fetches on the server, hard-resets to the branch, rebuilds, runs migrations
(the `migrate` service must exit 0 before the API starts), restarts, prunes
dangling images, and then polls `/health` until the stack answers.

The server's `.env` is never touched — secrets stay on the host.

Afterwards:

```bash
./deploy/verify.sh
```

which checks liveness, readiness, the web app, the API, and that the production
hardening is intact (docs disabled, dev login refused, `/me` unauthenticated).

## Operating it

```bash
cd /root/mk-projects/pulse

docker compose ps                 # what is running
docker compose logs -f --tail=100 api
docker compose restart api
docker compose exec db psql -U pulse -d pulse
```

### Backups

```bash
docker compose exec -T db pg_dump -U pulse -d pulse --clean --if-exists \
  | gzip > "/root/backups/pulse-$(date +%F).sql.gz"
```

A nightly cron entry:

```cron
15 3 * * * cd /root/mk-projects/pulse && docker compose exec -T db pg_dump -U pulse -d pulse --clean --if-exists | gzip > /root/backups/pulse-$(date +\%F).sql.gz && find /root/backups -name 'pulse-*.sql.gz' -mtime +14 -delete
```

Restore:

```bash
gunzip -c /root/backups/pulse-2026-09-08.sql.gz \
  | docker compose exec -T db psql -U pulse -d pulse
```

Uploaded images live in the `pulse_media` Docker volume:

```bash
docker run --rm -v pulse_media:/data -v /root/backups:/out alpine \
  tar czf /out/pulse-media-$(date +%F).tar.gz -C /data .
```

## Troubleshooting

**The tunnel is up but the domain 502s.** The public hostname is not pointed at
`localhost:8094`, or nginx is down. Check `docker compose ps` and
`journalctl -u cloudflared-pulse -n 50`.

**Telegram shows a blank screen.** `PUBLIC_WEB_URL` must be the https origin and
must match the domain set with `/setdomain`. Check the browser console through
Telegram Desktop's devtools.

**"Telegram sign-in could not be verified."** The `TELEGRAM_BOT_TOKEN` in `.env`
is not the bot serving the Mini App — `initData` is signed with the bot's own
token, so they must be the same bot. The reason is logged by the API:

```bash
docker compose logs api | grep initdata_rejected
```

**The API will not start.** It waits on `migrate` finishing successfully. Look
at `docker compose logs migrate` for a failed migration.

**Port already in use on a redeploy.** Another project claimed it. Change
`WEB_PORT` / `DB_PORT` in `.env` and update the tunnel's public hostname to
match.
