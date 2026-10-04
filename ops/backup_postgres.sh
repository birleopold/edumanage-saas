#!/usr/bin/env bash
set -u
APP=/srv/edumanage/app
VENV=/srv/edumanage/venv
BACKUP_DIR=/srv/edumanage/backups/postgresql
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

DB_JSON=$("$VENV/bin/python" "$APP/manage.py" shell --settings=config.settings.prod -c 'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps({"name":d["NAME"],"host":d["HOST"],"port":d["PORT"],"user":d["USER"],"password":d["PASSWORD"]}))' 2>/dev/null | tail -1)
eval "$("$VENV/bin/python" -c 'import json,shlex,sys; d=json.loads(sys.argv[1]); print("DB="+shlex.quote(str(d["name"]))); print("HOST="+shlex.quote(str(d["host"] or "127.0.0.1"))); print("PORT="+shlex.quote(str(d["port"] or "5432"))); print("USER="+shlex.quote(str(d["user"]))); print("PGPASSWORD="+shlex.quote(str(d["password"])))' "$DB_JSON")"
export PGPASSWORD
FILE="$BACKUP_DIR/${DB}_${STAMP}.dump"

if [ ! -d "$BACKUP_DIR" ] || [ ! -w "$BACKUP_DIR" ]; then
  echo "Backup directory is missing or not writable: $BACKUP_DIR"
  "$VENV/bin/python" "$APP/manage.py" record_platform_backup --status FAILED --location "$FILE" --notes "Backup directory missing/not writable" --settings=config.settings.prod || true
  exit 1
fi

if pg_dump -Fc -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -f "$FILE"; then
  SHA=$(sha256sum "$FILE" | awk '{print $1}')
  "$VENV/bin/python" "$APP/manage.py" record_platform_backup --status SUCCESS --location "$FILE" --checksum "$SHA" --notes "Automated pg_dump custom-format backup" --settings=config.settings.prod
  find "$BACKUP_DIR" -type f -name '*.dump' -mtime +14 -delete
else
  rm -f "$FILE"
  "$VENV/bin/python" "$APP/manage.py" record_platform_backup --status FAILED --location "$FILE" --notes "pg_dump failed" --settings=config.settings.prod || true
  exit 1
fi
