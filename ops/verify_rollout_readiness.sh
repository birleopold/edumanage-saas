#!/usr/bin/env bash
set -u
APP=/srv/edumanage/app
VENV=/srv/edumanage/venv
echo "=== release ==="; git -C "$APP" log -1 --oneline; git -C "$APP" status --short
echo "=== django ==="; "$VENV/bin/python" "$APP/manage.py" check --settings=config.settings.prod
echo "=== migrations ==="; "$VENV/bin/python" "$APP/manage.py" showmigrations tenants --settings=config.settings.prod | tail -15
echo "=== audit ==="; "$VENV/bin/python" "$APP/manage.py" verify_platform_audit_chain --settings=config.settings.prod
echo "=== billing dry run ==="; "$VENV/bin/python" "$APP/manage.py" reconcile_subscriptions --dry-run --settings=config.settings.prod
echo "=== service ==="; systemctl is-active edumanage.service || true
echo "=== health ==="; curl -fsS https://edumanage.leosoftug.com/health/ || true; echo
echo "=== platform ==="; curl -sS -o /dev/null -w '%{http_code}\n' https://edumanage.leosoftug.com/platform/login/
echo "=== caddy permission ==="; for d in demo.schools.leosoftug.com johnaschools.schools.leosoftug.com definitely-not-an-edumanage-school.example; do printf '%s ' "$d"; curl -sS -o /dev/null -w '%{http_code}\n' "https://edumanage.leosoftug.com/_internal/caddy/allow-domain?domain=$d"; done
echo "=== backup evidence ==="; "$VENV/bin/python" "$APP/manage.py" shell --settings=config.settings.prod -c 'from apps.public.tenants.models import PlatformBackupRecord as B; [print(x.status,x.occurred_at,x.checksum[:16],x.notes) for x in B.objects.all()[:5]]'
