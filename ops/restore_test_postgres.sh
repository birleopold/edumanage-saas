#!/usr/bin/env bash
set -u
APP=/srv/edumanage/app
VENV=/srv/edumanage/venv
BACKUP_DIR=/srv/edumanage/backups/postgresql

DB_JSON=$("$VENV/bin/python" "$APP/manage.py" shell --settings=config.settings.prod -c 'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps({"host":d["HOST"],"port":d["PORT"],"user":d["USER"],"password":d["PASSWORD"]}))' 2>/dev/null | tail -1)
eval "$("$VENV/bin/python" -c 'import json,shlex,sys; d=json.loads(sys.argv[1]); print("HOST="+shlex.quote(str(d["host"] or "127.0.0.1"))); print("PORT="+shlex.quote(str(d["port"] or "5432"))); print("APP_USER="+shlex.quote(str(d["user"]))); print("PGPASSWORD="+shlex.quote(str(d["password"])))' "$DB_JSON")"
export PGPASSWORD
LATEST=$(find "$BACKUP_DIR" -type f -name '*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)
[ -n "$LATEST" ] || { echo "No backup found"; exit 1; }
TEST_DB="edumanage_restore_test_$(date -u +%Y%m%d%H%M%S)"

# Database creation/drop are privileged operations. Keep CREATEDB away from the
# Django application role and perform only those two steps through local
# PostgreSQL peer authentication as the postgres OS account.
cleanup(){ sudo -u postgres dropdb --if-exists "$TEST_DB" >/dev/null 2>&1 || true; }
trap cleanup EXIT
sudo -u postgres createdb -O "$APP_USER" "$TEST_DB" || exit 1

if pg_restore -h "$HOST" -p "$PORT" -U "$APP_USER" -d "$TEST_DB" --no-owner --no-privileges "$LATEST"; then
  TABLES=$(psql -h "$HOST" -p "$PORT" -U "$APP_USER" -d "$TEST_DB" -Atc "select count(*) from information_schema.tables where table_schema not in ('pg_catalog','information_schema');")
  SHA=$(sha256sum "$LATEST" | awk '{print $1}')
  "$VENV/bin/python" "$APP/manage.py" record_platform_backup --status RESTORE_TESTED --location "$LATEST" --checksum "$SHA" --notes "Restore test succeeded; tables=$TABLES" --settings=config.settings.prod
else
  "$VENV/bin/python" "$APP/manage.py" record_platform_backup --status FAILED --location "$LATEST" --notes "Restore test failed" --settings=config.settings.prod || true
  exit 1
fi
