#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# CAN diagnostics collector
# Writes results to a user cache folder so it won't pollute the Git repo.
# - OUT_ROOT: ~/.cache/can-tool/diagnostics (or $XDG_CACHE_HOME/can-tool/diagnostics)
# - OUT_STEM: timestamped folder name, e.g., can-diagnostics-20251003-110719
# ─────────────────────────────────────────────────────────────────────────────

# Resolve output root (Linux cache convention)
OUT_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/can-tool/diagnostics"
mkdir -p "$OUT_ROOT"

# Timestamped stem and paths
STAMP="$(date +'%Y%m%d-%H%M%S')"
OUT_STEM="can-diagnostics-${STAMP}"
OUT_DIR="${OUT_ROOT}/${OUT_STEM}"
OUT_TGZ="${OUT_ROOT}/${OUT_STEM}.tar.gz"

mkdir -p "${OUT_DIR}"

echo "[can-diag] Collecting system information..."

# 1) System & kernel info
{
  echo "==== uname -a ===="
  uname -a || true
  echo

  echo "==== lsmod | egrep '(^can|_usb|kvaser|peak|slcan)' ===="
  lsmod | egrep '(^can|_usb|kvaser|peak|slcan)' || true
  echo

  echo "==== ip -br link ===="
  ip -br link || true
  echo

  echo "==== ip -details link show type can (JSON) ===="
  ip -details -json link show type can 2>/dev/null || true
  echo

  echo "==== dmesg | egrep -i 'can|kvaser|gs_usb|peak|slcan' | tail -n 200 ===="
  dmesg | egrep -i 'can|kvaser|gs_usb|peak|slcan' | tail -n 200 || true
  echo
} > "${OUT_DIR}/system.txt"

# 2) Port 8000 listeners
{
  echo "==== sudo lsof -i TCP:8000 -sTCP:LISTEN -n -P ===="
  sudo -n true 2>/dev/null || true
  sudo lsof -i TCP:8000 -sTCP:LISTEN -n -P || true
} > "${OUT_DIR}/port8000.txt"

# 3) Network interfaces and CAN state
{
  echo "==== ip -details link show ===="
  ip -details link show || true
} > "${OUT_DIR}/links.txt"

# 4) Try to prepare vcan0 (harmless on systems without it)
{
  echo "==== vcan bring-up attempt ===="
  sudo modprobe can can_raw vcan 2>&1 || true
  sudo ip link add dev vcan0 type vcan 2>&1 || true
  sudo ip link set up dev vcan0 2>&1 || true
  ip -br link | egrep '^(v?can)[0-9]+' || true
} > "${OUT_DIR}/vcan_setup.txt"

echo "[can-diag] Packing results at ${OUT_TGZ}..."
tar -C "${OUT_ROOT}" -czf "${OUT_TGZ}" "${OUT_STEM}"
echo "[can-diag] Done. Created ${OUT_TGZ}"
echo
echo ">>> Attach ${OUT_TGZ} if you need support. <<<"

log "Packing results..."
tar -czf "${OUTDIR}.tar.gz" "$OUTDIR"
log "Done. Created ${OUTDIR}.tar.gz"
echo
echo ">>> Please attach ${OUTDIR}.tar.gz here. <<<"
