#!/usr/bin/env bash
#
# Post-deploy checks. Run on the server, or with PULSE_BASE set to the public
# URL to check the whole path including the Cloudflare Tunnel.
#
#   ./deploy/verify.sh
#   PULSE_BASE=https://pulse.mammad.site ./deploy/verify.sh
#
set -uo pipefail

BASE="${PULSE_BASE:-http://127.0.0.1:${WEB_PORT:-8094}}"
fails=0

check() {
  local label="$1" expected="$2" url="$3"
  local got
  got=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$url" 2>/dev/null)
  if [ "$got" = "$expected" ]; then
    printf '  \033[32mok\033[0m   %-46s %s\n' "$label" "$got"
  else
    printf '  \033[31mFAIL\033[0m %-46s got %s, wanted %s\n' "$label" "$got" "$expected"
    fails=$((fails + 1))
  fi
}

echo "Checking $BASE"
check "liveness"                       200 "$BASE/health"
check "readiness (database reachable)" 200 "$BASE/ready"
check "web app"                        200 "$BASE/"
check "API"                            200 "$BASE/api/v1/feed/trends"
check "favicon"                        200 "$BASE/favicon.svg"
check "unauthenticated /me is refused" 401 "$BASE/api/v1/auth/me"
check "docs are off in production"     404 "$BASE/openapi.json"

# Dev login must be refused in production regardless of the .env flag.
dev=$(curl -s -o /dev/null -m 15 -w '%{http_code}' -X POST \
      -H 'Content-Type: application/json' -d '{"telegram_id":1}' \
      "$BASE/api/v1/auth/dev" 2>/dev/null)
if [ "$dev" = "403" ]; then
  printf '  \033[32mok\033[0m   %-46s %s\n' "dev login is disabled" "$dev"
else
  printf '  \033[31mFAIL\033[0m %-46s got %s, wanted 403\n' "dev login is disabled" "$dev"
  fails=$((fails + 1))
fi

echo
if [ "$fails" -eq 0 ]; then
  echo "All checks passed."
else
  echo "$fails check(s) failed."
  exit 1
fi
