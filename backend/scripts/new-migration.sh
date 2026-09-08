#!/usr/bin/env bash
#
# Create the next migration with a sequential revision id, so that
# alembic/versions lists in apply order rather than by random hash.
#
#   ./backend/scripts/new-migration.sh "add polls"
#
# Runs alembic on the host against the published database port, so the file
# lands in the working tree rather than inside a container.
#
set -Eeuo pipefail

MESSAGE="${1:-}"
[ -n "$MESSAGE" ] || { echo "usage: $0 \"a short description\""; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSIONS="$ROOT/backend/alembic/versions"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"

[ -x "$PYTHON" ] || { echo "ERROR: no venv at $PYTHON. Create one first."; exit 1; }

# Highest existing number, defaulting to 0 for an empty folder. 10# forces
# base 10 so that 008 and 009 are not read as invalid octal.
last=$(find "$VERSIONS" -maxdepth 1 -name '[0-9]*_*.py' -printf '%f\n' 2>/dev/null \
       | sed -E 's/^([0-9]+)_.*/\1/' | sort -n | tail -1)
next=$(printf '%03d' $(( 10#${last:-000} + 1 )))

echo "==> creating revision $next: $MESSAGE"

# Autogenerate needs to diff against a live database. Reach the compose one on
# its published loopback port.
DB_PORT="$(grep -E '^DB_PORT=' "$ROOT/.env" 2>/dev/null | cut -d= -f2)"
export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-${DB_PORT:-5434}}"

cd "$ROOT/backend"
"$PYTHON" -m alembic revision --autogenerate --rev-id "$next" -m "$MESSAGE"

echo "==> review it before committing:"
ls -1 "$VERSIONS" | tail -3
