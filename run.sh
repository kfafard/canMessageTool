#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────── CAN CONFIG ─────────────────────────────
CAN_IFACE_DEFAULT="${CAN_IFACE_DEFAULT:-can0}"
CAN_BITRATE="${CAN_BITRATE:-250000}"
CANDUMP_LOG="${CANDUMP_LOG:-./candump.log}"
CANDUMP_PIDFILE="${CANDUMP_PIDFILE:-./candump.pid}"
AUTO_CAN="${AUTO_CAN:-0}"   # 1 = do can_up on start / can_down on stop

auto_can_enabled() { [[ "${AUTO_CAN}" == "1" ]]; }

ensure_can_utils() {
  command -v ip >/dev/null || { echo "iproute2 not found"; exit 1; }
  command -v cansend >/dev/null || { echo "can-utils not found (install: sudo apt install can-utils)"; exit 1; }
  command -v candump >/dev/null || { echo "can-utils not found (install: sudo apt install can-utils)"; exit 1; }
}

load_can_modules() {
  sudo modprobe can || true
  sudo modprobe can_raw || true
  # Only load kvaser_usb if Kvaser Leaf v3 is present; harmless if absent
  lsusb 2>/dev/null | grep -qi '0bfd:0117' && sudo modprobe kvaser_usb || true
}

detect_can_iface() {
  local got
  got="$(ip -brief link show type can | awk 'NR==1{print $1}')"
  if [[ -n "${got:-}" ]]; then
    echo "$got"
    return 0
  fi
  echo "$CAN_IFACE_DEFAULT"
}

can_is_up() {
  local ifc="$1"
  ip -details link show "$ifc" 2>/dev/null | grep -q "state UP"
}

candump_running() {
  [[ -f "$CANDUMP_PIDFILE" ]] && kill -0 "$(cat "$CANDUMP_PIDFILE")" 2>/dev/null
}

start_candump() {
  local ifc="$1"
  if candump_running; then
    echo "candump already running (PID $(cat "$CANDUMP_PIDFILE"))."
  else
    echo "Starting candump on $ifc → $CANDUMP_LOG"
    : > "$CANDUMP_LOG"
    nohup bash -c "exec candump $ifc >>'$CANDUMP_LOG' 2>&1" &
    echo $! > "$CANDUMP_PIDFILE"
    disown
  fi
}

stop_candump() {
  if candump_running; then
    local pid
    pid="$(cat "$CANDUMP_PIDFILE")"
    echo "Stopping candump (PID $pid)…"
    kill "$pid" 2>/dev/null || true
    sleep 0.2
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$CANDUMP_PIDFILE"
  fi
}

can_up() {
  ensure_can_utils
  load_can_modules
  local ifc; ifc="$(detect_can_iface)"
  if ! ip link show "$ifc" &>/dev/null; then
    echo "Bringing up $ifc (may be created by driver)…"
  fi
  sudo ip link set "$ifc" up type can bitrate "$CAN_BITRATE"
  echo "CAN up: $ifc @ ${CAN_BITRATE} bps"
  ip -details -brief link show dev "$ifc" || true
}

can_down() {
  local ifc; ifc="$(detect_can_iface)"
  stop_candump
  if ip link show "$ifc" &>/dev/null; then
    sudo ip link set "$ifc" down || true
    echo "CAN down: $ifc"
  else
    echo "No CAN interface to bring down."
  fi
}

can_test() {
  ensure_can_utils
  local ifc; ifc="$(detect_can_iface)"
  if ! can_is_up "$ifc"; then
    echo "(can-test) Interface $ifc not up — bringing up @ ${CAN_BITRATE}…"
    sudo ip link set "$ifc" up type can bitrate "$CAN_BITRATE"
  fi
  start_candump "$ifc"
  local frame="18FEE5FF#A0860100FFFFFFFF"
  echo "Sending test frame on $ifc: $frame"
  cansend "$ifc" "$frame"
  sleep 0.2
  echo "Recent candump lines:"
  tail -n 5 "$CANDUMP_LOG" || true
}

show_can_status() {
  echo "--- CAN Status ---"
  ip -details -brief link show type can || echo "No CAN interfaces detected."
  if candump_running; then
    echo "candump: running (PID $(cat "$CANDUMP_PIDFILE")) → $CANDUMP_LOG"
  else
    echo "candump: not running"
  fi
}

# ───────────────────────────── Paths ─────────────────────────────
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACK_DIR="$ROOT_DIR/backend"
FRONT_DIR="$ROOT_DIR/frontend"

BACK_RUN="$BACK_DIR/run.sh"
FRONT_PORT=5173
FRONT_LOG="$FRONT_DIR/frontend.log"
FRONT_PID="$FRONT_DIR/.pid"      # real listener PID
FRONT_PGID="$FRONT_DIR/.pgid"    # process group id to kill whole tree

# ─────────────────────────── Helpers ────────────────────────────
ensure_exec() { [ -f "$BACK_RUN" ] && chmod +x "$BACK_RUN" 2>/dev/null || true; }
ensure_node() { command -v node >/dev/null && command -v npm >/dev/null || { echo "Node/npm not found"; exit 1; }; }
ensure_workspace() {
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
  if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    . "$ROOT_DIR/.venv/bin/activate"
  fi
}

# ─────────────── Backend controls (delegate) ────────────────────
start_backend()  { ensure_exec; ensure_venv; (cd "$BACK_DIR" && ./run.sh start); }
stop_backend() {
  ensure_exec
  if (cd "$BACK_DIR" && ./run.sh stop); then
    echo "Backend stopped (script)."
  else
    echo "Backend stop script failed; best-effort kill…"
    # Adjust to match your backend process name(s)
    pkill -f 'uvicorn|gunicorn|python.*backend|can-message-backend' 2>/dev/null || true
  fi
}
status_backend() { ensure_exec; (cd "$BACK_DIR" && ./run.sh status || true); }

# ─────────────── Frontend controls (Vite) ───────────────────────
start_frontend() {
  ensure_node; ensure_workspace
  (cd "$ROOT_DIR" && npm install --workspaces >/dev/null 2>&1 || true)
  echo "Starting frontend (Vite)…"
  (cd "$ROOT_DIR" && setsid npm run -w frontend dev -- --host --port "$FRONT_PORT" --strictPort > "$FRONT_LOG" 2>&1 & echo $! > "$FRONT_PID.raw")
  for _ in {1..40}; do
    LISTENER_PID=$(lsof -t -i :"$FRONT_PORT" -sTCP:LISTEN 2>/dev/null | head -n1 || true)
    [ -n "${LISTENER_PID:-}" ] && break
    sleep 0.2
  done
  if [ -z "${LISTENER_PID:-}" ]; then
    echo "Frontend failed to bind to port $FRONT_PORT. See $FRONT_LOG"
    RAWPID=$(cat "$FRONT_PID.raw" 2>/dev/null || true)
    [ -n "$RAWPID" ] && kill "$RAWPID" 2>/dev/null || true
    rm -f "$FRONT_PID.raw"
    exit 1
  fi
  echo "$LISTENER_PID" > "$FRONT_PID"
  PGID=$(ps -o pgid= -p "$LISTENER_PID" | tr -d ' ')
  echo "$PGID" > "$FRONT_PGID"
  rm -f "$FRONT_PID.raw"
  echo "Frontend started (PID=$LISTENER_PID, PGID=$PGID), logs: $FRONT_LOG"
}

stop_frontend() {
  if [ -f "$FRONT_PGID" ]; then
    PGID=$(cat "$FRONT_PGID" 2>/dev/null || true)
    if [ -n "${PGID:-}" ]; then
      # Guard: never kill our own process group
      MYPGRP=$(ps -o pgid= -p $$ | tr -d ' ')
      if [ "$PGID" != "$MYPGRP" ]; then
        kill -TERM -- "-$PGID" 2>/dev/null || true
        sleep 0.5
        kill -KILL -- "-$PGID" 2>/dev/null || true
      else
        echo "Skip group kill (PGID $PGID == our shell PGID)."
      fi
    fi
    rm -f "$FRONT_PGID"
  fi
  LEFT=$(lsof -t -i :"$FRONT_PORT" -sTCP:LISTEN 2>/dev/null | xargs -r echo)
  [ -n "${LEFT:-}" ] && kill -KILL $LEFT 2>/dev/null || true
  echo "Frontend stopped."
}

status_frontend() {
  if [ -f "$FRONT_PID" ]; then
    PID=$(cat "$FRONT_PID" 2>/dev/null || true)
    if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
      echo "Frontend is running (PID=$PID)."
      return 0
    fi
  fi
  echo "Frontend is not running."
  return 1
}

# ─────────────── Orchestrator commands ──────────────────────────
do_start() {
  echo "=== Starting CAN Tool (backend + frontend) ==="
  start_backend
  start_frontend
  if auto_can_enabled; then
    can_up
  fi
  echo "All services started."
  echo "Backend:  http://localhost:8000   (docs: /docs)"
  echo "Frontend: http://localhost:${FRONT_PORT}"
}

do_stop() {
  echo "=== Stopping CAN Tool (backend + frontend) ==="
  stop_frontend || true      # never abort stop
  stop_backend  || true
  if auto_can_enabled; then
    can_down || true
  fi
  echo "All services stopped."
}


do_restart() { do_stop; sleep 1; do_start; }

do_status() {
  echo "--- Backend ---"
  status_backend || true
  echo "--- Frontend ---"
  status_frontend || true
  show_can_status
}

do_up() {
  echo "=== Bringing CAN Tool up (foreground) ==="
  if auto_can_enabled; then can_up; fi
  start_backend
  stop_frontend >/dev/null 2>&1 || true
  trap 'echo; echo "Ctrl+C → stopping both…"; stop_frontend; stop_backend; if auto_can_enabled; then can_down; fi; exit 0' INT
  ensure_node; ensure_workspace
  (cd "$ROOT_DIR" && npm run -w frontend dev -- --host --port "$FRONT_PORT" --strictPort)
}

# ───────────────────────────── CLI ──────────────────────────────
case "${1:-}" in
  start)     do_start ;;
  stop)      do_stop ;;
  restart)   do_restart ;;
  status)    do_status ;;
  up)        do_up ;;
  can-up)    can_up ;;
  can-down)  can_down ;;
  can-test)  can_test ;;
  *)
    cat <<EOF
Usage: $0 {start|stop|restart|status|up|can-up|can-down|can-test}

CAN helpers:
  can-up           Load modules and bring up CAN at ${CAN_BITRATE}
  can-down         Stop candump (if any) and bring the CAN iface down
  can-test         Bring up (if needed), start candump, send one test frame, show log

Environment overrides:
  CAN_IFACE_DEFAULT=<canX>   (default: ${CAN_IFACE_DEFAULT})
  CAN_BITRATE=<bps>          (default: ${CAN_BITRATE})
  CANDUMP_LOG=<path>         (default: ${CANDUMP_LOG})
  CANDUMP_PIDFILE=<path>     (default: ${CANDUMP_PIDFILE})
  AUTO_CAN=1                 (auto can_up on start / can_down on stop)
EOF
    exit 1
    ;;
esac
