#!/usr/bin/env bash
# scripts/linux/can_diag.sh
#
# PURPOSE:
#   Collects CAN + environment diagnostics on Linux Mint so we can pinpoint why the app
#   can't access 'can0' or fails to bring an interface up.
#
# WHAT IT DOES:
#   - Gathers OS + kernel info
#   - Checks presence/state of CAN interfaces
#   - Checks required kernel modules
#   - Verifies CAN tools and 'ip' availability
#   - Looks for anything already listening on TCP 8000
#   - (Optionally) creates/starts a virtual CAN 'vcan0' to confirm the stack works
#   - Captures app binary capabilities (setcap) so the app can manage interfaces
#   - Bundles results into can-diagnostics.tar.gz for you to attach back
#
# SAFE TO RUN:
#   Uses read-only commands except where noted with 'sudo'. It only *creates/ups* vcan0 if you agree.

set -euo pipefail

OUTDIR="can-diagnostics-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUTDIR"

log() { echo "[can-diag] $*" | tee -a "$OUTDIR/diag.log"; }

log "Collecting system information..."
{
  echo "=== OS ==="
  uname -a || true
  echo
  echo "=== /etc/os-release ==="
  cat /etc/os-release || true
  echo
  echo "=== Kernel modules (CAN related) ==="
  lsmod | egrep -i '^(can|can_raw|vcan|slcan|gs_usb|peak_usb|kvaser_usb)\b' || true
  echo
  echo "=== iproute2 ==="
  which ip || true
  ip -V || true
  echo
  echo "=== CAN tools ==="
  which candump || true
  candump -h 2>&1 | head -n 5 || true
} > "$OUTDIR/system.txt"

log "Checking TCP:8000 listeners..."
{
  sudo lsof -i TCP:8000 -sTCP:LISTEN -n -P || true
  echo
  ss -lntp 2>/dev/null | grep ':8000' || true
} > "$OUTDIR/port8000.txt"

# Try to locate the app binary in the common place you used
APP_BIN="./can-tool-linux-v0.0.4"
if [[ ! -x "$APP_BIN" ]]; then
  # Also try Downloads fallback
  if [[ -x "$HOME/Downloads/can-tool-linux-v0.0.4" ]]; then
    APP_BIN="$HOME/Downloads/can-tool-linux-v0.0.4"
  fi
fi

log "Inspecting app binary: $APP_BIN"
{
  echo "BIN: $APP_BIN"
  if [[ -e "$APP_BIN" ]]; then
    ls -l "$APP_BIN" || true
    sha256sum "$APP_BIN" || true
    file "$APP_BIN" || true
    which getcap >/dev/null 2>&1 && getcap "$APP_BIN" || echo "getcap not available (install: sudo apt install -y libcap2-bin)"
  else
    echo "Binary not found at $APP_BIN (skipping capability check)."
  fi
} > "$OUTDIR/app-binary.txt"

log "Enumerating network interfaces and CAN state..."
{
  echo "=== ip -br link ==="
  ip -br link || true
  echo
  echo "=== ip -details link show type can ==="
  ip -details link show type can || true
} > "$OUTDIR/net-ifaces.txt"

log "Kernel ring messages for CAN (may show driver attach/usb events)..."
dmesg --color=never | egrep -i '(\bcan\b|socketcan|gs_usb|peak|kvaser|slcan)' > "$OUTDIR/dmesg-can.txt" || true

# Ask user if we should create vcan0 to validate the stack quickly
CREATE_VCAN=${CREATE_VCAN:-yes}  # set CREATE_VCAN=no to skip
if [[ "${CREATE_VCAN}" == "yes" ]]; then
  log "Attempting to load CAN modules and create vcan0 (requires sudo)..."
  {
    set -x
    sudo modprobe can || true
    sudo modprobe can_raw || true
    sudo modprobe vcan || true

    if ! ip -br link | grep -q '^vcan0'; then
      sudo ip link add dev vcan0 type vcan || true
    fi
    sudo ip link set up vcan0 || true
    set +x

    echo
    echo "=== vcan0 state after bring-up ==="
    ip -br link show vcan0 || true
  } > "$OUTDIR/vcan-setup.txt" 2>&1
else
  log "Skipping vcan0 creation (CREATE_VCAN=no)."
fi

log "Packing results..."
tar -czf "${OUTDIR}.tar.gz" "$OUTDIR"
log "Done. Created ${OUTDIR}.tar.gz"
echo
echo ">>> Please attach ${OUTDIR}.tar.gz here. <<<"
