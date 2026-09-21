#!/usr/bin/env bash
set -Eeuo pipefail

# Required/typical overrides:
#   PROJECT_DIR=/home/admin/edumanage-saas
#   SERVICE_NAME=edumanage-gunicorn.service
#   HEALTH_URL=https://edumanage.example.com/health/
PROJECT_DIR="${PROJECT_DIR:-/home/admin/edumanage-saas}"
BRANCH="${BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-edumanage-gunicorn.service}"
HEALTH_URL="${HEALTH_URL:-}"
SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.tenants}"
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/.venv}"
LOCK_FILE="${LOCK_FILE:-/tmp/edumanage-deploy.lock}"

exec 9>"$LOCK_FILE"
flock -n 9 || { echo "Another EduManage deployment is running." >&2; exit 1; }

cd "$PROJECT_DIR"
test -d .git || { echo "Not a Git checkout: $PROJECT_DIR" >&2; exit 1; }
test -f manage.py || { echo "manage.py not found in $PROJECT_DIR" >&2; exit 1; }
test -x "$VENV_DIR/bin/python" || { echo "Python venv not found: $VENV_DIR" >&2; exit 1; }

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Deployment stopped: the VPS checkout has uncommitted changes." >&2
  exit 1
fi

git fetch --prune origin "$BRANCH"
git checkout "$BRANCH"
git merge --ff-only "origin/$BRANCH"
DEPLOY_SHA="$(git rev-parse --verify HEAD)"

"$VENV_DIR/bin/pip" install --requirement requirements.txt
"$VENV_DIR/bin/python" manage.py check --settings="$SETTINGS_MODULE"
"$VENV_DIR/bin/python" manage.py migrate_schemas --shared --noinput --settings="$SETTINGS_MODULE"
"$VENV_DIR/bin/python" manage.py migrate_schemas --tenant --noinput --settings="$SETTINGS_MODULE"
"$VENV_DIR/bin/python" manage.py collectstatic --noinput --settings="$SETTINGS_MODULE"

sudo systemctl restart "$SERVICE_NAME"
sudo systemctl is-active --quiet "$SERVICE_NAME"

if [[ -n "$HEALTH_URL" ]]; then
  curl --fail --silent --show-error --retry 6 --retry-delay 5 "$HEALTH_URL" >/dev/null
fi

echo "EduManage deployed successfully: $DEPLOY_SHA"
