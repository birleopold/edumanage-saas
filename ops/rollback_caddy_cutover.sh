#!/usr/bin/env bash
set -u
BACKUP=$(cat /srv/edumanage/.last-caddy-backup 2>/dev/null || true)
[ -n "$BACKUP" ] && [ -d "$BACKUP/nginx" ] || { echo "No Caddy rollback snapshot found."; exit 1; }
systemctl stop caddy 2>/dev/null || true
rm -rf /etc/nginx
cp -a "$BACKUP/nginx" /etc/nginx
nginx -t || { echo "Restored Nginx config is invalid; not restarting."; exit 1; }
systemctl restart nginx
echo "Rollback complete: $BACKUP"
ss -ltnp | grep -E ':(80|443|18081)\b' || true
