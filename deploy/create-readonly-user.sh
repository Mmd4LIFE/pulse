#!/usr/bin/env bash
#
# Create (or refresh) a read-only database role for analytics tools such as
# Metabase.
#
# The role is read-only three times over: it is granted only SELECT, it is
# denied CREATE on the schema, and its sessions default to read-only
# transactions, so even a query that tries to write fails rather than silently
# depending on privileges alone.
#
#   ./deploy/create-readonly-user.sh                 # generate a password
#   PULSE_RO_PASSWORD=... ./deploy/create-readonly-user.sh   # set a known one
#
# Run from the project directory on the host running the stack.
#
set -Eeuo pipefail

ROLE="${PULSE_RO_USER:-pulse_readonly}"
PASSWORD="${PULSE_RO_PASSWORD:-$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')}"

cd "$(dirname "${BASH_SOURCE[0]}")/.."
[ -f .env ] || { echo "ERROR: .env not found. Run this on the app host."; exit 1; }

DB_USER="$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2)"
DB_NAME="$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2)"
DB_USER="${DB_USER:-pulse}"
DB_NAME="${DB_NAME:-pulse}"

echo "==> granting read-only access to '$ROLE' on database '$DB_NAME'"

docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" <<SQL
DO \$\$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$ROLE') THEN
    ALTER ROLE $ROLE WITH LOGIN PASSWORD '$PASSWORD';
  ELSE
    CREATE ROLE $ROLE WITH LOGIN PASSWORD '$PASSWORD';
  END IF;
END
\$\$;

-- Even a query that tries to write fails, rather than relying on grants alone.
ALTER ROLE $ROLE SET default_transaction_read_only = on;
-- Analytics tools should not sit in a queue behind, or hold up, the app.
ALTER ROLE $ROLE SET statement_timeout = '120s';
ALTER ROLE $ROLE SET idle_in_transaction_session_timeout = '60s';

GRANT CONNECT ON DATABASE $DB_NAME TO $ROLE;
GRANT USAGE ON SCHEMA public TO $ROLE;
REVOKE CREATE ON SCHEMA public FROM $ROLE;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO $ROLE;
-- Tables a future migration creates are covered without re-running this.
ALTER DEFAULT PRIVILEGES FOR ROLE $DB_USER IN SCHEMA public
  GRANT SELECT ON TABLES TO $ROLE;
SQL

echo
echo "Role:     $ROLE"
echo "Password: $PASSWORD"
echo
echo "Store the password now -- it is not written anywhere."
