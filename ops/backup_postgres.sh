#!/usr/bin/env bash
set -u
APP=/srv/edumanage/app
VENV=/srv/edumanage/venv
BACKUP_DIR=/srv/edumanage/backups/postgresql
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$BACKUP_DIR"
set -a; . "$APP/.env"; set +a
DB="${POSTGRES_DB:-edumanage_saas}"
HOST="${POSTGRES_HOST:-127.0.0.1}"
PORT="${POSTGRES_PORT:-5432}"
USER="${POSTGRES_USER:-postgres}"
FILE="$BACKUP_DIR/${DB}_${STAMP}.dump"
export PGPASSWORD="${POSTGRES_PASSWORD:-}"
if pg_dump -Fc -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -f "$FILE"; then
  SHA=$(sha256sum "$FILE" | awk '{print $1}')
  "$VENV/bin/python" "$APP/manage.py" record_platform_backup --status SUCCESS --location "$FILE" --checksum "$SHA" --notes "Automated pg_dump custom-format backup" --settings=config.settings.prod
  find "$BACKUP_DIR" -type f -name '*.dump' -mtime +14 -delete
else
  "$VENV/bin/python" "$APP/manage.py" record_platform_backup --status FAILED --location "$FILE" --notes "pg_dump failed" --settings=config.settings.prod || true
  exit 1
fi
