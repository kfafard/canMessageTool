#!/usr/bin/env bash
set -euo pipefail

APP="uvicorn app:app --reload --host 0.0.0.0 --port 8000"
PIDFILE="backend.pid"
LOGFILE="backend.log"

start() {
  if [ -f "$PIDFILE" ] && ps -p "$(cat "$PIDFILE")" >/dev/null 2>&1; then
    echo "Backend already running (PID=$(cat $PIDFILE))"
    exit 0
  fi
  echo "Starting backend…"
  $APP > "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  echo "Backend started (PID=$(cat "$PIDFILE")), logs: $LOGFILE"
}

stop() {
  if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    echo "Stopping backend (PID=$PID)…"
    kill "$PID" 2>/dev/null || true
    rm -f "$PIDFILE"
  else
    echo "No PID file, trying pkill…"
    pkill -f "uvicorn app:app" || true
  fi
}

restart() { stop; sleep 1; start; }

status() {
  if [ -f "$PIDFILE" ] && ps -p "$(cat "$PIDFILE")" >/dev/null 2>&1; then
    echo "Backend is running (PID=$(cat "$PIDFILE"))"
  else
    echo "Backend is not running"
  fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) restart ;;
  status) status ;;
  *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
