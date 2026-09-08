#!/usr/bin/env bash
#
# Deploy Pulse to the application host.
#
# Pulls the latest commit on the server, rebuilds the images and restarts the
# stack. The server keeps its own .env; this script never copies secrets.
#
#   ./deploy/deploy.sh              # deploy the current branch
#   PULSE_BRANCH=main ./deploy/deploy.sh
#
set -Eeuo pipefail

HOST="${PULSE_HOST:-91.107.156.153}"
USER="${PULSE_USER:-root}"
APP_DIR="${PULSE_DIR:-/root/mk-projects/pulse}"
BRANCH="${PULSE_BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

command -v ssh >/dev/null || die "ssh is not installed"

say "Deploying branch '$BRANCH' to $USER@$HOST:$APP_DIR"

ssh -o StrictHostKeyChecking=accept-new "$USER@$HOST" bash -Eeuo pipefail -s <<REMOTE
set -Eeuo pipefail
cd "$APP_DIR" || { echo "ERROR: $APP_DIR does not exist. Run the first-time setup first."; exit 1; }

echo "--> fetching"
git fetch --all --prune
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

[ -f .env ] || { echo "ERROR: .env is missing on the server."; exit 1; }

echo "--> building"
docker compose build

echo "--> migrating and restarting"
docker compose up -d --remove-orphans

# The nginx config is a bind mount, so compose sees no reason to recreate the
# container when only that file changed. Validate and reload it explicitly,
# which also avoids dropping connections.
echo "--> reloading nginx"
if docker compose exec -T nginx nginx -t >/dev/null 2>&1; then
  docker compose exec -T nginx nginx -s reload
else
  echo "ERROR: the nginx config is invalid; not reloading"
  docker compose exec -T nginx nginx -t
  exit 1
fi

echo "--> pruning dangling images"
docker image prune -f >/dev/null

echo "--> waiting for health"
PORT=\$(grep -E '^WEB_PORT=' .env | cut -d= -f2)
for i in \$(seq 1 30); do
  if curl -fsS -m 5 "http://127.0.0.1:\$PORT/health" >/dev/null 2>&1; then
    echo "    healthy after \${i}s"
    break
  fi
  [ "\$i" = "30" ] && { echo "ERROR: never became healthy"; docker compose ps; docker compose logs --tail=60; exit 1; }
  sleep 1
done

echo "--> verifying"
WEB_PORT="\$PORT" ./deploy/verify.sh

docker compose ps
REMOTE

say "Deployed."
