# backend/bus.py
from __future__ import annotations

import asyncio
import time
import threading
import queue
import subprocess
import json
import sys
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

# ──────────────────────────────────────────────────────────────────────────────
# Optional backends (import failures are handled gracefully)
# ──────────────────────────────────────────────────────────────────────────────

# python-can (SocketCAN path)
try:
    import can  # type: ignore
    HAS_PYCAN = True
except Exception:
    HAS_PYCAN = False

# Intrepid libicsneo path
try:
    import icsneopy as ics  # type: ignore
    HAS_INTREPID = True
except Exception:
    HAS_INTREPID = False


# ──────────────────────────────────────────────────────────────────────────────
# Common structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Frame:
    ts: float
    id_hex: str
    data: bytes


def _hex_id(i: int) -> str:
    """J1939 uses 29-bit (extended) IDs; print as 8 hex chars."""
    return f"{i:08X}"


# ──────────────────────────────────────────────────────────────────────────────
# SocketCAN implementation via python-can
# ──────────────────────────────────────────────────────────────────────────────

class _SocketCANBus:
    """
    python-can based reader/writer (SocketCAN).

    Notes:
    - bitrate is NOT set by python-can for socketcan; bring the link up externally
      (e.g., `ip link set can0 up type can bitrate 250000`).
    - RX runs on a lightweight thread to keep the event loop free.
    """
    def __init__(self, channel: str, bitrate: Optional[int] = None):
        self.channel = channel
        self.bitrate = bitrate
        self.bus: Optional["can.BusABC"] = None
        self._rxq: "queue.Queue[Frame]" = queue.Queue(maxsize=10000)
        self._stop = threading.Event()
        self._rx_thread: Optional[threading.Thread] = None
        self.frames_total = 0
        self.frames_by_pgn: Dict[int, int] = {}

    def open(self):
        if not HAS_PYCAN:
            raise RuntimeError("python-can not available")
        # Raises if channel doesn’t exist:
        self.bus = can.interface.Bus(
            channel=self.channel,
            bustype="socketcan",
            receive_own_messages=True  # <— this is the key
        )
        self._start_rx()

    def close(self):
        self._stop.set()
        if self._rx_thread:
            self._rx_thread.join(timeout=1)
        if self.bus:
            try:
                self.bus.shutdown()
            except Exception:
                pass
            self.bus = None

    def send(self, id_hex: str, data_hex: str):
        if not self.bus:
            raise RuntimeError("Bus not open")
        arb = int(id_hex, 16)
        data = bytes.fromhex(data_hex)
        msg = can.Message(arbitration_id=arb, is_extended_id=True, data=data)
        self.bus.send(msg)

    def _start_rx(self):
        def loop():
            while not self._stop.is_set():
                try:
                    msg = self.bus.recv(0.02)  # type: ignore[attr-defined]
                    if msg is None:
                        continue
                    ts = getattr(msg, "timestamp", time.time())
                    data = bytes(getattr(msg, "data", b"") or b"")
                    arb = int(getattr(msg, "arbitration_id", 0))
                    frm = Frame(ts=ts, id_hex=_hex_id(arb), data=data)
                    try:
                        self._rxq.put_nowait(frm)
                    except queue.Full:
                        # Drop oldest to stay responsive under burst
                        try:
                            _ = self._rxq.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            self._rxq.put_nowait(frm)
                        except queue.Full:
                            pass
                    self.frames_total += 1
                except Exception:
                    time.sleep(0.001)
        self._rx_thread = threading.Thread(target=loop, daemon=True)
        self._rx_thread.start()

    def read_batch(self, max_items: int) -> List[Frame]:
        out: List[Frame] = []
        while len(out) < max_items:
            try:
                out.append(self._rxq.get_nowait())
            except queue.Empty:
                break
        return out

    def health(self) -> Dict[str, Any]:
        return {
            "driver": "socketcan",
            "channel": self.channel,
            "frames_total": self.frames_total,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Intrepid implementation via icsneopy (libicsneo)
# ──────────────────────────────────────────────────────────────────────────────

class _IntrepidBus:
    """libicsneo wrapper with a compatible API."""
    def __init__(self, device_index: int, bitrate: Optional[int] = None):
        self.device_index = device_index
        self.bitrate = bitrate
        self.dev: Optional["ics.Device"] = None
        self._net = ics.Network.NetID.CAN1
        self._rxq: "queue.Queue[Frame]" = queue.Queue(maxsize=10000)
        self._stop = threading.Event()
        self._rx_thread: Optional[threading.Thread] = None
        self.frames_total = 0

    @staticmethod
    def list_names() -> List[str]:
        """Return names like ['intrepid0', ...] if library is present."""
        if not HAS_INTREPID:
            return []
        try:
            return [f"intrepid{i}" for i, _ in enumerate(ics.find_all_devices())]
        except Exception:
            return []

    def open(self):
        if not HAS_INTREPID:
            raise RuntimeError("Intrepid bindings not available")
        devs = ics.find_all_devices()
        if self.device_index >= len(devs):
            raise RuntimeError("No Intrepid device at that index")
        self.dev = devs[self.device_index]
        if not self.dev.is_open():
            if not self.dev.open():
                raise RuntimeError("Failed to open Intrepid device")
        # Optional bitrate apply
        if self.bitrate:
            try:
                settings = self.dev.get_settings()
                settings.set_can_bitrate(self._net, self.bitrate)
                self.dev.apply_settings(settings)
            except Exception:
                pass
        self.dev.enable_bus(self._net, True)
        self._start_rx()

    def close(self):
        self._stop.set()
        if self._rx_thread:
            self._rx_thread.join(timeout=1)
        if self.dev:
            try:
                self.dev.enable_bus(self._net, False)
                self.dev.close()
            except Exception:
                pass
            self.dev = None

    def send(self, id_hex: str, data_hex: str):
        if not self.dev:
            raise RuntimeError("Device not open")
        msg = ics.CanMessage()
        msg.arb_id = int(id_hex, 16)
        msg.is_extended = True
        msg.data = bytearray.fromhex(data_hex)
        ok = self.dev.transmit(msg)
        if not ok:
            raise RuntimeError("TX failed")

    def _start_rx(self):
        def loop():
            while not self._stop.is_set():
                try:
                    msgs = self.dev.receive()  # returns list
                    ts = time.time()
                    for m in msgs:
                        data = bytes(m.data or b"")
                        self._rxq.put_nowait(Frame(ts=ts, id_hex=_hex_id(int(m.arb_id)), data=data))
                        self.frames_total += 1
                except Exception:
                    time.sleep(0.001)
        self._rx_thread = threading.Thread(target=loop, daemon=True)
        self._rx_thread.start()

    def read_batch(self, max_items: int) -> List[Frame]:
        out: List[Frame] = []
        while len(out) < max_items:
            try:
                out.append(self._rxq.get_nowait())
            except queue.Empty:
                break
        return out

    def health(self) -> Dict[str, Any]:
        name = ""
        try:
            name = self.dev.get_product_name() if self.dev else ""
        except Exception:
            pass
        return {
            "driver": "intrepid",
            "device_index": self.device_index,
            "device": name,
            "frames_total": self.frames_total,
        }

# --- Kvaser backend (Windows) -----------------------------------------------
# This implements a minimal Kvaser backend via python-can. It expects that
# Kvaser CANlib drivers are installed on the machine (so that python-can can
# load canlib32.dll). Channel naming follows "kvaser<N>" where N is an integer.
class _KvaserBus:
    def __init__(self):
        self._bus = None
        self._last_info = {}

    async def discover_interfaces(self):
        """
        Return a small set of candidate channel names the UI can offer.
        We can't reliably enumerate Kvaser channels portably without extra deps,
        so provide a few common indices. The user will usually pick kvaser0.
        """
        return [f"kvaser{i}" for i in range(4)]

    async def connect(self, channel: str, bitrate: int):
        """
        Open a Kvaser channel: interface='kvaser', channel=<index>, bitrate=<bps>.
        'channel' is expected as 'kvaser0', 'kvaser1', etc.
        """
        import can  # python-can
        try:
            if not channel.lower().startswith("kvaser"):
                return False, f"invalid channel name '{channel}'. use 'kvaser0', 'kvaser1', etc."
            idx = int(channel.replace("kvaser", ""))

            # Close previous if any
            if self._bus is not None:
                try:
                    self._bus.shutdown()
                except Exception:
                    pass
                self._bus = None

            self._bus = can.interface.Bus(
                interface="kvaser",
                channel=idx,
                bitrate=bitrate,
            )
            self._last_info = {
                "backend": "kvaser",
                "channel": idx,
                "bitrate": bitrate,
            }
            return True, f"connected to {channel} @ {bitrate} bps"
        except Exception as e:
            return False, f"Failed to open {channel}: {e}"

    async def disconnect(self):
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception:
                pass
            self._bus = None

    def health_snapshot(self):
        return dict(self._last_info)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers for SocketCAN discovery (fast & non-blocking for the API thread)
# ──────────────────────────────────────────────────────────────────────────────

def _list_socketcan_names() -> List[str]:
    """
    Return available SocketCAN interface names quickly.

    Strategy:
      1) Preferred: `ip -details -json link show type can` (timeout 1s)
      2) Fallback: scan /sys/class/net for interfaces starting with can* or vcan*
    """
    names: List[str] = []

    # Preferred: `ip` JSON output
    try:
        proc = subprocess.run(
            ["ip", "-details", "-json", "link", "show", "type", "can"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=True,
        )
        data = json.loads(proc.stdout or "[]")
        for item in data:
            ifname = item.get("ifname")
            if isinstance(ifname, str):
                names.append(ifname)
    except Exception:
        pass

    # Fallback: /sys scan
    try:
        for p in Path("/sys/class/net").glob("*"):
            n = p.name
            if n.startswith(("can", "vcan")):
                names.append(n)
    except Exception:
        pass

    # Deduplicate, keep order
    seen = set()
    uniq: List[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


# ──────────────────────────────────────────────────────────────────────────────
# Front-end facing manager (fixed deadlock + offloaded blocking calls)
# ──────────────────────────────────────────────────────────────────────────────

class BusManager:
    def __init__(self):
        self._impl = None
        self._impl_name = None

        # Prefer SocketCAN on Linux
        if sys.platform.startswith("linux"):
            try:
                self._impl = _SocketCANBus()
                self._impl_name = "socketcan"
            except Exception:
                pass

        # If Intrepid (ics) is installed, allow that to override on any platform.
        # We probe for the module without importing it to keep Pylance happy.
        try:
            if importlib.util.find_spec("ics") is not None:
                self._impl = _IntrepidBus()
                self._impl_name = "intrepid"
        except Exception:
            pass

        # On Windows, prefer Kvaser if python-can is present.
        if sys.platform.startswith("win"):
            try:
                if importlib.util.find_spec("can") is not None:
                    self._impl = _KvaserBus()
                    self._impl_name = "kvaser"
            except Exception:
                # Leave whatever impl we already selected (e.g., Intrepid)
                pass


# ---- Discovery -----------------------------------------------------------

    async def discover_interfaces(self) -> List[str]:
        tasks = [
            asyncio.to_thread(_list_socketcan_names),
            asyncio.to_thread(_IntrepidBus.list_names) if HAS_INTREPID else None,
        ]
        results: List[List[str]] = []
        for t in [t for t in tasks if t is not None]:
            try:
                results.append(await t)  # type: ignore[arg-type]
            except Exception:
                results.append([])
        out: List[str] = []
        seen: set[str] = set()
        for group in results:
            for name in group:
                if name not in seen:
                    seen.add(name)
                    out.append(name)
        return out

    # ---- Connect / Disconnect ----------------------------------------------

    # INTERNAL: do not call without holding self._lock
    async def _disconnect_no_lock(self) -> None:
        if self._bus is not None:
            try:
                # offload potential blocking close
                await asyncio.to_thread(self._bus.close)  # type: ignore[attr-defined]
            except Exception:
                pass
            self._bus = None
            self._info = {}

    async def connect(self, channel: str, bitrate: Optional[int] = None) -> Tuple[bool, str]:
        """
        Connect to either SocketCAN (default) or Intrepid if channel starts with 'intrepid'.
        Offloads hardware open to a thread to avoid blocking the event loop.
        """
        async with self._lock:
            # FIX: avoid deadlock by calling the no-lock variant
            await self._disconnect_no_lock()
            try:
                if channel.startswith("intrepid"):
                    idx = int(channel.replace("intrepid", "") or "0")
                    b = _IntrepidBus(device_index=idx, bitrate=bitrate)
                    # offload blocking open
                    await asyncio.to_thread(b.open)
                    self._bus = b
                    name = ""
                    try:
                        name = b.dev.get_product_name()
                    except Exception:
                        pass
                    self._info = {
                        "driver": "intrepid",
                        "device": name,
                        "channel": f"intrepid{idx}",
                        "connected_at": time.time(),
                    }
                    return True, "connected (intrepid)"
                else:
                    if not HAS_PYCAN:
                        return False, "python-can not available"
                    b = _SocketCANBus(channel=channel, bitrate=bitrate)
                    # offload blocking open
                    await asyncio.to_thread(b.open)
                    self._bus = b
                    self._info = {
                        "driver": "socketcan",
                        "channel": channel,
                        "connected_at": time.time(),
                    }
                    return True, "connected (socketcan)"
            except Exception as e:
                self._bus = None
                self._info = {}
                return False, str(e)

    async def disconnect(self):
        async with self._lock:
            await self._disconnect_no_lock()

    # ---- I/O ----------------------------------------------------------------

    async def send(self, id_hex: str, data_hex: str):
        if self._bus is None:
            raise RuntimeError("Not connected")
        self._bus.send(id_hex, data_hex)  # type: ignore[attr-defined]

    async def get_rx_batch(self, timeout: float, max_items: int) -> List[Frame]:
        """
        Collect up to max_items frames, waiting up to 'timeout' seconds.
        Polls in small sleeps to hit ~50–100 Hz cadence without blocking the loop.
        """
        end = time.time() + timeout
        items: List[Frame] = []
        while time.time() < end:
            if self._bus is None:
                break
            batch = self._bus.read_batch(max_items)  # type: ignore[attr-defined]
            if batch:
                items.extend(batch)
                break
            await asyncio.sleep(0.01)
        return items

    # ---- Health / Self-test -------------------------------------------------

    def health_snapshot(self) -> Dict[str, Any]:
        if self._bus is None:
            return {"status": "disconnected"}
        base = {"status": "connected"}
        try:
            base.update(self._info)
        except Exception:
            pass
        try:
            base.update(self._bus.health())  # type: ignore[attr-defined]
        except Exception:
            pass
        return base

    async def selftest(self, timeout_ms: int = 300) -> Dict[str, Any]:
        """
        Sends a magic frame and waits briefly to see it come back through our RX path.
        Works out-of-the-box on vcan (loopback). On physical hardware, echo_rx may be false.
        """
        if self._bus is None:
            return {"connected": False, "reason": "not connected"}

        test_id_hex = "18F11CEF"
        test_data_hex = "A55A55A55A55A55A"

        # Drain any old frames quickly so we don't count stale traffic
        try:
            _ = self._bus.read_batch(10000)  # type: ignore[attr-defined]
        except Exception:
            pass

        tx_ok = False
        try:
            self._bus.send(test_id_hex, test_data_hex)  # type: ignore[attr-defined]
            tx_ok = True
        except Exception as e:
            return {"connected": True, "tx_ok": False, "error": str(e)}

        # Wait briefly for echo
        deadline = time.time() + (timeout_ms / 1000.0)
        echo_rx = False
        rx_seen = 0
        while time.time() < deadline:
            try:
                b = self._bus.read_batch(1000)  # type: ignore[attr-defined]
            except Exception:
                b = []
            rx_seen += len(b)
            for fr in b:
                if fr.id_hex.upper() == test_id_hex and fr.data.hex().upper() == test_data_hex:
                    echo_rx = True
                    break
            if echo_rx:
                break
            await asyncio.sleep(0.01)

        return {
            "connected": True,
            "tx_ok": tx_ok,
            "echo_rx": echo_rx,
            "rx_seen": rx_seen,
            "note": "Echo depends on loopback/other node. vcan will echo; hardware may not.",
        }
