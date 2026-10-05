#!/usr/bin/env bash
# Backend deploy, run ON the production server by
# .github/workflows/test-and-deploy.yml (piped over ssh, so the version of this
# script being deployed is the one that runs).
#
# The server has no GitHub credentials and the deploy user has no passwordless
# sudo, so:
#   - code arrives as a git bundle shipped by the CI runner
#   - wros-backend is restarted by stopping its process; the systemd unit has
#     Restart=always and brings it back on the new code
#   - the queue worker is kept alive by a cron watchdog (flock = one instance)
#
# Usage: deploy_backend.sh <bundle-path|-> <commit-sha>
set -euo pipefail

BUNDLE="$1"
SHA="$2"
REPO=/home/HRMS/WROS-Master
VENV="$REPO/venv"
BACKEND_PATTERN="[/]home/HRMS/WROS-Master/venv/bin/uvicorn app.main:app"
WORKER_PATTERN="[/]home/HRMS/WROS-Master/backend/start_worker.py"
WORKER_CRON="* * * * * cd $REPO/backend && /usr/bin/flock -n /tmp/wros-queue-worker.lock $VENV/bin/python $REPO/backend/start_worker.py >> /home/HRMS/wros-queue-worker.log 2>&1"
ME="$(id -un)"

cd "$REPO"
PREV="$(git rev-parse HEAD)"

restart_backend() {
  pkill -u "$ME" -f "$BACKEND_PATTERN" || true
}

backend_healthy() {
  for _ in $(seq 1 45); do
    sleep 2
    if [ "$(curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/health)" = "200" ]; then
      return 0
    fi
  done
  return 1
}

if [ "$BUNDLE" != "-" ]; then
  git fetch -q "$BUNDLE" "+HEAD:refs/remotes/deploy/head"
fi
git cat-file -e "$SHA^{commit}"
git reset -q --hard "$SHA"
echo "[deploy] $PREV -> $SHA"

"$VENV/bin/python" -m pip install -q -r backend/requirements.txt

# Refuse to restart into code that cannot even be imported (a broken import
# is what kept production in a restart loop until 2026-10-05).
if ! (cd backend && timeout 120 "$VENV/bin/python" -c "import app.main" >/tmp/wros-import-check.log 2>&1); then
  echo "[deploy] import check FAILED, staying on $PREV:"
  grep -v "DATABASE_URL" /tmp/wros-import-check.log | tail -30
  git reset -q --hard "$PREV"
  exit 1
fi

restart_backend
if ! backend_healthy; then
  echo "[deploy] backend unhealthy on $SHA; startup output:"
  systemctl status wros-backend --no-pager | head -5 || true
  (cd backend && timeout 60 "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8099 2>&1 \
    | grep -v "DATABASE_URL" | tail -40) || true
  echo "[deploy] rolling back to $PREV"
  git reset -q --hard "$PREV"
  restart_backend
  backend_healthy && echo "[deploy] rollback healthy" || echo "[deploy] rollback ALSO unhealthy"
  exit 1
fi
echo "[deploy] backend healthy"

# Queue worker: ensure the watchdog exists, then stop the old worker (SIGTERM
# lets it finish its cycle); cron starts the new code within a minute.
( crontab -l 2>/dev/null | grep -v "wros-queue-worker.lock" || true; echo "$WORKER_CRON" ) | crontab -
pkill -u "$ME" -f "$WORKER_PATTERN" || true
echo "[deploy] queue worker restarting via cron"
