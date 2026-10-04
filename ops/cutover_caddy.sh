#!/usr/bin/env bash
set -u
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/srv/edumanage/deploy-backups/caddy-$STAMP
mkdir -p "$BACKUP"
cp -a /etc/nginx "$BACKUP/nginx"
[ -d /etc/caddy ] && cp -a /etc/caddy "$BACKUP/caddy" || true
echo "$BACKUP" >/srv/edumanage/.last-caddy-backup

echo "Backup: $BACKUP"
echo "Installing internal Nginx edge..."
cp /srv/edumanage/app/ops/nginx-edumanage-internal.conf /etc/nginx/sites-available/edumanage-internal
rm -f /etc/nginx/sites-enabled/edumanage /etc/nginx/sites-enabled/hotspot /etc/nginx/sites-enabled/signalsolid /etc/nginx/sites-enabled/leosoftug.com
ln -sfn /etc/nginx/sites-available/edumanage-internal /etc/nginx/sites-enabled/edumanage-internal
nginx -t || { echo "Internal Nginx config invalid; restoring."; rm -rf /etc/nginx; cp -a "$BACKUP/nginx" /etc/nginx; exit 1; }

echo "Installing Caddy if required..."
if ! command -v caddy >/dev/null; then
 apt-get update
 apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
 curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
 curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' -o /etc/apt/sources.list.d/caddy-stable.list
 chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
 chmod o+r /etc/apt/sources.list.d/caddy-stable.list
 systemctl mask caddy.service 2>/dev/null || true
 apt-get update && apt-get install -y caddy
 systemctl unmask caddy.service 2>/dev/null || true
 systemctl stop caddy 2>/dev/null || true
fi
mkdir -p /etc/caddy
cp /srv/edumanage/app/ops/Caddyfile /etc/caddy/Caddyfile
if [ ! -f /etc/caddy/edumanage.env ]; then echo 'CADDY_ACME_EMAIL=leopoldbirungi@gmail.com' >/etc/caddy/edumanage.env; chmod 600 /etc/caddy/edumanage.env; fi
mkdir -p /etc/systemd/system/caddy.service.d
cat >/etc/systemd/system/caddy.service.d/edumanage-env.conf <<'EOF'
[Service]
EnvironmentFile=/etc/caddy/edumanage.env
EOF
systemctl stop caddy 2>/dev/null || true
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile || { echo "Caddy config invalid; no cutover performed."; exit 1; }

echo "Cutting over..."
systemctl stop caddy 2>/dev/null || true
systemctl restart nginx || { echo "Nginx internal restart failed."; exit 1; }
systemctl daemon-reload
systemctl enable caddy
systemctl restart caddy || { echo "Caddy failed. Run ops/rollback_caddy_cutover.sh"; exit 1; }
sleep 5
ss -ltnp | grep -E ':(80|443|18081)\b' || true
for u in https://edumanage.leosoftug.com/health/ https://demo.schools.leosoftug.com/ https://johnaschools.schools.leosoftug.com/ https://hotspotcloud.net/ https://signalsolid.com/ https://leosoftug.com/; do echo "=== $u"; curl -IL --max-time 20 "$u" | head -5 || true; done
