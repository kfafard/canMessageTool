#!/usr/bin/env bash
# Bring up a SocketCAN interface at a chosen bitrate.
# Defaults: iface=can0, bitrate=250000 (250 kbit/s)
#
# Usage examples:
#   ./scripts/linux/can_up.sh                # can0 @ 250k
#   ./scripts/linux/can_up.sh can0 500000    # can0 @ 500k

set -euo pipefail

IFACE="${1:-can0}"          # First argument or "can0"
BITRATE="${2:-250000}"      # Second argument or 250000

echo "[can_up] Loading base CAN modules (no error if already loaded)"
sudo modprobe can can_raw || true

echo "[can_up] Try common USB-CAN drivers (ignore if not present)"
for m in gs_usb peak_usb kvaser_usb; do
  sudo modprobe "$m" 2>/dev/null || true
done

echo "[can_up] Configure ${IFACE} at ${BITRATE}"
sudo ip link set "${IFACE}" down 2>/dev/null || true
sudo ip link set "${IFACE}" type can bitrate "${BITRATE}"
sudo ip link set "${IFACE}" up

echo "[can_up] Result:"
ip -details link show "${IFACE}"
