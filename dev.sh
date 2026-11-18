#!/usr/bin/env bash
# Starts everything for local development:
#   1. Docker services (PostgreSQL + Redis)
#   2. Database migrations
#   3. A terminal window for FastAPI
#   4. A terminal window for the Celery worker
#
# Run from Git Bash (Windows), Linux or macOS:   bash dev.sh

set -euo pipefail
cd "$(dirname "$0")"

API_CMD="uv run uvicorn app.main:app --reload"
OS="$(uname -s)"

# Celery's default pool does not work on Windows, so use --pool=solo there.
case "$OS" in
  MINGW*|MSYS*|CYGWIN*) WORKER_CMD="uv run celery -A app.tasks.celery_app:celery_app worker --loglevel=info --pool=solo" ;;
  *)                    WORKER_CMD="uv run celery -A app.tasks.celery_app:celery_app worker --loglevel=info" ;;
esac

echo "==> Starting Docker services (PostgreSQL, Redis)..."
docker compose up -d

wait_healthy() {
  local container="$1"
  echo -n "    waiting for $container "
  for _ in $(seq 1 30); do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "starting")"
    if [ "$status" = "healthy" ]; then
      echo "-> healthy"
      return 0
    fi
    echo -n "."
    sleep 2
  done
  echo
  echo "ERROR: $container did not become healthy. Check: docker compose logs" >&2
  exit 1
}

wait_healthy job_platform_db
wait_healthy job_platform_redis

echo "==> Applying database migrations..."
uv run alembic upgrade head

echo "==> Opening terminals for FastAPI and the Celery worker..."
PROJECT_DIR="$(pwd)"

case "$OS" in
  MINGW*|MSYS*|CYGWIN*)
    # Windows (Git Bash): open two PowerShell windows that stay open.
    WIN_DIR="$(cygpath -w "$PROJECT_DIR")"
    powershell.exe -NoProfile -Command "Start-Process powershell.exe -WorkingDirectory '$WIN_DIR' -ArgumentList '-NoExit','-Command','$API_CMD'"
    powershell.exe -NoProfile -Command "Start-Process powershell.exe -WorkingDirectory '$WIN_DIR' -ArgumentList '-NoExit','-Command','$WORKER_CMD'"
    ;;
  Darwin)
    # macOS Terminal.app
    osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_DIR' && $API_CMD\""
    osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_DIR' && $WORKER_CMD\""
    ;;
  *)
    # Linux
    if command -v gnome-terminal >/dev/null 2>&1; then
      gnome-terminal --title="FastAPI" -- bash -c "$API_CMD; exec bash"
      gnome-terminal --title="Celery Worker" -- bash -c "$WORKER_CMD; exec bash"
    elif command -v konsole >/dev/null 2>&1; then
      konsole --new-tab -e bash -c "$API_CMD; exec bash" &
      konsole --new-tab -e bash -c "$WORKER_CMD; exec bash" &
    elif command -v xterm >/dev/null 2>&1; then
      xterm -T "FastAPI" -e bash -c "$API_CMD; exec bash" &
      xterm -T "Celery Worker" -e bash -c "$WORKER_CMD; exec bash" &
    else
      echo "No supported terminal found. Run these in two terminals:" >&2
      echo "  $API_CMD" >&2
      echo "  $WORKER_CMD" >&2
      exit 1
    fi
    ;;
esac

echo
echo "Done."
echo "  API docs : http://127.0.0.1:8000/docs"
echo "  Stop     : close the two terminal windows (Ctrl+C in each), then 'docker compose stop'"