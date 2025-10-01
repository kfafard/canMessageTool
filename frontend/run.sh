#!/usr/bin/env bash
set -euo pipefail

# Ensure pnpm is on PATH (non-interactive shells)
export PNPM_HOME="$HOME/.local/share/pnpm"
case ":$PATH:" in
  *":$PNPM_HOME:"*) ;;
  *) export PATH="$PNPM_HOME:$PATH" ;;
esac

APP="pnpm dev --host --port 5173"
PIDFILE="frontend.pid"
LOGFILE="frontend.log"

start() {
  if [ -f "$PIDFILE" ] && ps -p "$(cat "$PIDFILE")" >/dev/null 2>&1; then
    echo "Frontend already running (PID=$(cat $PIDFILE))"
    exit 0
  fi
  echo "Starting frontend…"
  $APP > "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  echo "Frontend started (PID=$(cat "$PIDFILE")), logs: $LOGFILE"
}

stop() {
  if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    echo "Stopping frontend (PID=$PID)…"
    kill "$PID" 2>/dev/null || true
    rm -f "$PIDFILE"
  else
    echo "No PID file, trying pkill…"
    pkill -f "pnpm dev" || true
  fi
}

restart() { stop; sleep 1; start; }

status() {
  if [ -f "$PIDFILE" ] && ps -p "$(cat "$PIDFILE")" >/dev/null 2>&1; then
    echo "Frontend is running (PID=$(cat "$PIDFILE"))"
  else
    echo "Frontend is not running"
  fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) restart ;;
  status) status ;;
  *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
