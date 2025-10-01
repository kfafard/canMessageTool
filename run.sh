#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACK_SCRIPT="$ROOT_DIR/backend/run.sh"
FRONT_SCRIPT="$ROOT_DIR/frontend/run.sh"

ensure_exec() { chmod +x "$BACK_SCRIPT" "$FRONT_SCRIPT" 2>/dev/null || true; }

start() {
  ensure_exec
  echo "=== Starting CAN Tool (backend + frontend) ==="
  (cd "$ROOT_DIR/backend" && ./run.sh start)
  (cd "$ROOT_DIR/frontend" && ./run.sh start)
  echo "All services started."
  echo "Backend:  http://localhost:8000   (docs: /docs)"
  echo "Frontend: http://localhost:5173"
}

stop() {
  ensure_exec
  echo "=== Stopping CAN Tool (backend + frontend) ==="
  (cd "$ROOT_DIR/frontend" && ./run.sh stop || true)
  (cd "$ROOT_DIR/backend"  && ./run.sh stop || true)
  echo "All services stopped."
}

restart() { stop; sleep 1; start; }

status() {
  ensure_exec
  echo "--- Backend ---"
  (cd "$ROOT_DIR/backend" && ./run.sh status || true)
  echo "--- Frontend ---"
  (cd "$ROOT_DIR/frontend" && ./run.sh status || true)
}

# Foreground dev: keeps frontend in the foreground; Ctrl+C stops both
up() {
  ensure_exec
  echo "=== Bringing CAN Tool up (foreground) ==="
  (cd "$ROOT_DIR/backend" && ./run.sh start)
  trap 'echo; echo "Ctrl+C → stopping both…"; (cd "'"$ROOT_DIR/backend"'" && ./run.sh stop); (cd "'"$ROOT_DIR/frontend"'" && ./run.sh stop); exit 0' INT
  (cd "$ROOT_DIR/frontend" && pnpm dev --host --port 5173)
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) restart ;;
  status) status ;;
  up) up ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|up}"
    exit 1
    ;;
esac
