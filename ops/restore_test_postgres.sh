#!/usr/bin/env bash
set -u
APP=/srv/edumanage/app
VENV=/srv/edumanage/venv
BACKUP_DIR=/srv/edumanage/backups/postgresql
set -a; . "$APP/.env"; set +a
HOST="${POSTGRES_HOST:-127.0.0.1}"; PORT="${POSTGRES_PORT:-5432}"; USER="${POSTGRES_USER:-postgres}"
LATEST=$(find "$BACKUP_DIR" -type f -name '*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
[ -n "$LATEST" ] || { echo "No backup found"; exit 1; }
TEST_DB="edumanage_restore_test_$(date -u +%Y%m%d%H%M%S)"
export PGPASSWORD="${POSTGRES_PASSWORD:-}"
cleanup(){ dropdb -h "$HOST" -p "$PORT" -U "$USER" --if-exists "$TEST_DB" >/dev/null 2>&1 || true; }
trap cleanup EXIT
createdb -h "$HOST" -p "$PORT" -U "$USER" "$TEST_DB" || exit 1
if pg_restore -h "$HOST" -p "$PORT" -U "$USER" -d "$TEST_DB" --no-owner --no-privileges "$LATEST"; then
  TABLES=$(psql -h "$HOST" -p "$PORT" -U "$USER" -d "$TEST_DB" -Atc "select count(*) from information_schema.tables where table_schema not in ('pg_catalog','information_schema');")
  SHA=$(sha256sum "$LATEST" | awk '{print $1}')
  "$VENV/bin/python" "$APP/manage.py" record_platform_backup --status RESTORE_TESTED --location "$LATEST" --checksum "$SHA" --notes "Restore test succeeded; tables=$TABLES" --settings=config.settings.prod
else
  "$VENV/bin/python" "$APP/manage.py" record_platform_backup --status FAILED --location "$LATEST" --notes "Restore test failed" --settings=config.settings.prod || true
  exit 1
fi
