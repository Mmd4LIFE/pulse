#!/usr/bin/env bash
#
# First-time setup on a fresh host: clone the repo, write .env, install the
# Cloudflare Tunnel service, and bring the stack up.
#
# Run this ON THE SERVER, once. Afterwards use deploy/deploy.sh from a laptop.
#
set -Eeuo pipefail

REPO="${PULSE_REPO:-https://github.com/Mmd4LIFE/pulse.git}"
APP_DIR="${PULSE_DIR:-/root/mk-projects/pulse}"
WEB_PORT="${WEB_PORT:-8094}"
DB_PORT="${DB_PORT:-5434}"
DOMAIN="${PULSE_DOMAIN:-pulse.mammad.site}"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

command -v docker >/dev/null || { echo "docker is required"; exit 1; }

say "Checking that ports $WEB_PORT and $DB_PORT are free"
for port in "$WEB_PORT" "$DB_PORT"; do
  if ss -tulpn 2>/dev/null | grep -q ":$port "; then
    echo "ERROR: port $port is already in use. Pick another in .env."; exit 1
  fi
done

say "Cloning into $APP_DIR"
mkdir -p "$(dirname "$APP_DIR")"
[ -d "$APP_DIR/.git" ] || git clone "$REPO" "$APP_DIR"
cd "$APP_DIR"

if [ ! -f .env ]; then
  say "Writing .env"
  SECRET=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))")
  PGPASS=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")
  cat > .env <<ENV
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
LOG_JSON=true

PUBLIC_WEB_URL=https://$DOMAIN
CORS_ORIGINS=https://$DOMAIN,https://web.telegram.org

SECRET_KEY=$SECRET
ACCESS_TOKEN_TTL_MINUTES=60
REFRESH_TOKEN_TTL_DAYS=30
TELEGRAM_INITDATA_MAX_AGE_SECONDS=86400

TELEGRAM_BOT_TOKEN=REPLACE_ME
TELEGRAM_BOT_USERNAME=REPLACE_ME
ALLOW_DEV_LOGIN=false

POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_USER=pulse
POSTGRES_PASSWORD=$PGPASS
POSTGRES_DB=pulse
DB_PORT=$DB_PORT

REDIS_URL=redis://redis:6379/0

WEB_PORT=$WEB_PORT
NEXT_PUBLIC_API_BASE_URL=/api/v1
ENV
  chmod 600 .env
  echo "    .env written -- set TELEGRAM_BOT_TOKEN before starting."
fi

say "Starting the stack"
docker compose up -d --build

say "Done. Point the Cloudflare Tunnel's public hostname $DOMAIN at http://localhost:$WEB_PORT"
