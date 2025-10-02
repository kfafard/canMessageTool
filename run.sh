#!/usr/bin/env bash
set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACK_DIR="$ROOT_DIR/backend"
FRONT_DIR="$ROOT_DIR/frontend"

BACK_RUN="$BACK_DIR/run.sh"
FRONT_LOG="$FRONT_DIR/frontend.log"
FRONT_PID="$FRONT_DIR/.pid"

# ── Helpers ────────────────────────────────────────────────────────────────────
ensure_exec() { [ -f "$BACK_RUN" ] && chmod +x "$BACK_RUN" 2>/dev/null || true; }
ensure_node() { command -v node >/dev/null && command -v npm >/dev/null || { echo "Node/npm not found"; exit 1; }; }
ensure_workspace() {
  # Minimal root package.json for npm workspaces (frontend) if missing
  if [ ! -f "$ROOT_DIR/package.json" ] || ! grep -q '"workspaces"' "$ROOT_DIR/package.json"; then
    cat > "$ROOT_DIR/package.json" <<'JSON'
{
  "name": "canmessagetool-root",
  "private": true,
  "workspaces": ["frontend"]
}
JSON
  fi
}
ensure_venv() {
  # Auto-activate Python venv for backend calls if present
  if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    . "$ROOT_DIR/.venv/bin/activate"
  fi
}

# ── Backend controls (delegates to backend/run.sh) ─────────────────────────────
start_backend()  { ensure_exec; ensure_venv; (cd "$BACK_DIR" && ./run.sh start); }
stop_backend()   { ensure_exec; (cd "$BACK_DIR" && ./run.sh stop || true); }
status_backend() { ensure_exec; (cd "$BACK_DIR" && ./run.sh status || true); }

# ── Frontend controls (npm workspace: frontend) ────────────────────────────────
FRONT_PORT=5173
FRONT_LOG="$FRONT_DIR/frontend.log"
FRONT_PID="$FRONT_DIR/.pid"      # will store the real listener PID (node/vite)
FRONT_PGID="$FRONT_DIR/.pgid"    # process group id we can kill in one go

start_frontend() {
  ensure_node; ensure_workspace
  # Install hoisted deps if needed (safe if already installed)
  (cd "$ROOT_DIR" && npm install --workspaces >/dev/null 2>&1 || true)

  echo "Starting frontend (Vite)…"
  # Start Vite in its own session (new process group), so we can kill the whole tree later
  (cd "$ROOT_DIR" && setsid npm run -w frontend dev -- --host --port "$FRONT_PORT" --strictPort > "$FRONT_LOG" 2>&1 & echo $! > "$FRONT_PID.raw")

  # Wait for the port to open, then capture the **actual listener PID**
  for i in {1..40}; do
    LISTENER_PID=$(lsof -t -i :"$FRONT_PORT" -sTCP:LISTEN 2>/dev/null | head -n1 || true)
    [ -n "$LISTENER_PID" ] && break
    sleep 0.2
  done

  if [ -z "${LISTENER_PID:-}" ]; then
    echo "Frontend failed to bind to port $FRONT_PORT. See $FRONT_LOG"
    # best-effort cleanup of the npm wrapper if it’s still around
    RAWPID=$(cat "$FRONT_PID.raw" 2>/dev/null || true)
    [ -n "$RAWPID" ] && kill "$RAWPID" 2>/dev/null || true
    rm -f "$FRONT_PID.raw"
    exit 1
  fi

  echo "$LISTENER_PID" > "$FRONT_PID"
  # Record its process group to kill the whole tree later
  PGID=$(ps -o pgid= -p "$LISTENER_PID" | tr -d ' ')
  echo "$PGID" > "$FRONT_PGID"

  rm -f "$FRONT_PID.raw"
  echo "Frontend started (PID=$LISTENER_PID, PGID=$PGID), logs: $FRONT_LOG"
}

stop_frontend() {
  # Prefer killing the whole process group (handles node + any children)
  if [ -f "$FRONT_PGID" ]; then
    PGID=$(cat "$FRONT_PGID" 2>/dev/null || true)
    if [ -n "$PGID" ]; then
      kill -TERM -- "-$PGID" 2>/dev/null || true
      sleep 0.5
      kill -KILL -- "-$PGID" 2>/dev/null || true
    fi
    rm -f "$FRONT_PGID"
  fi

  # Fallback: kill the listener PID directly if PGID missing
  if [ -f "$FRONT_PID" ]; then
    PID=$(cat "$FRONT_PID" 2>/dev/null || true)
    if [ -n "$PID" ]; then
      kill -TERM "$PID" 2>/dev/null || true
      sleep 0.5
      kill -KILL "$PID" 2>/dev/null || true
    fi
    rm -f "$FRONT_PID"
  fi

  # Last resort: if something still listens on the port, kill it
  LEFT=$(lsof -t -i :"$FRONT_PORT" -sTCP:LISTEN 2>/dev/null | xargs -r echo)
  if [ -n "$LEFT" ]; then
    kill -KILL $LEFT 2>/dev/null || true
  fi

  echo "Frontend stopped."
}


stop_frontend() {
  if [ -f "$FRONT_PID" ]; then
    PID="$(cat "$FRONT_PID" || true)"
    if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
      kill "$PID" || true
      # give Vite a moment to exit
      sleep 0.5
    fi
    rm -f "$FRONT_PID"
    echo "Frontend stopped."
  else
    # best-effort fallback
    pkill -f "vite.*frontend" 2>/dev/null || true
    echo "Frontend stop (best-effort)."
  fi
}

status_frontend() {
  if [ -f "$FRONT_PID" ]; then
    PID="$(cat "$FRONT_PID" || true)"
    if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
      echo "Frontend is running (PID=$PID)."
      return 0
    fi
  fi
  echo "Frontend is not running."
  return 1
}

# ── Orchestrator commands ──────────────────────────────────────────────────────
start() {
  echo "=== Starting CAN Tool (backend + frontend) ==="
  start_backend
  start_frontend
  echo "All services started."
  echo "Backend:  http://localhost:8000   (docs: /docs)"
  echo "Frontend: http://localhost:5173"
}

stop() {
  echo "=== Stopping CAN Tool (backend + frontend) ==="
  stop_frontend
  stop_backend
  echo "All services stopped."
}

restart() { stop; sleep 1; start; }

status() {
  echo "--- Backend ---"
  status_backend || true
  echo "--- Frontend ---"
  status_frontend || true
}

# Foreground dev: backend in background, frontend in foreground (Ctrl+C stops both)
up() {
  echo "=== Bringing CAN Tool up (foreground) ==="
  start_backend
  stop_frontend >/dev/null 2>&1 || true
  trap 'echo; echo "Ctrl+C → stopping both…"; stop_frontend; stop_backend; exit 0' INT
  ensure_node; ensure_workspace
  (cd "$ROOT_DIR" && npm run -w frontend dev -- --host --port "$FRONT_PORT" --strictPort)
}

# ── CLI ────────────────────────────────────────────────────────────────────────
case "${1:-}" in
  start)   start ;;
  stop)    stop ;;
  restart) restart ;;
  status)  status ;;
  up)      up ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|up}"
    exit 1
    ;;
esac
