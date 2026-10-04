#!/usr/bin/env bash
set -u
cat >/etc/systemd/system/edumanage-backup.service <<'EOF'
[Unit]
Description=EduManage PostgreSQL backup
After=postgresql.service
[Service]
Type=oneshot
User=admin
Group=admin
WorkingDirectory=/srv/edumanage/app
ExecStart=/bin/bash /srv/edumanage/app/ops/backup_postgres.sh
EOF
cat >/etc/systemd/system/edumanage-backup.timer <<'EOF'
[Unit]
Description=Nightly EduManage PostgreSQL backup
[Timer]
OnCalendar=*-*-* 02:15:00
Persistent=true
RandomizedDelaySec=900
[Install]
WantedBy=timers.target
EOF
cat >/etc/systemd/system/edumanage-restore-test.service <<'EOF'
[Unit]
Description=EduManage PostgreSQL restore verification
After=postgresql.service
[Service]
Type=oneshot
User=root
WorkingDirectory=/srv/edumanage/app
ExecStart=/bin/bash /srv/edumanage/app/ops/restore_test_postgres.sh
EOF
cat >/etc/systemd/system/edumanage-restore-test.timer <<'EOF'
[Unit]
Description=Weekly EduManage PostgreSQL restore verification
[Timer]
OnCalendar=Sun *-*-* 03:30:00
Persistent=true
RandomizedDelaySec=900
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now edumanage-backup.timer edumanage-restore-test.timer
systemctl list-timers --all | grep -E 'edumanage-(backup|restore-test)' || true
