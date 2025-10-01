# backend/bus.py
from __future__ import annotations
import asyncio, time, threading, queue, struct
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any

# Try python-can for SocketCAN path
try:
    import can  # type: ignore
    HAS_PYCAN = True
except Exception:
    HAS_PYCAN = False

# Try Intrepid libicsneo path
try:
    import icsneopy as ics  # type: ignore
    HAS_INTREPID = True
except Exception:
    HAS_INTREPID = False


@dataclass
class Frame:
    ts: float
    id_hex: str
    data: bytes

def _hex_id(i: int) -> str:
    # Extended IDs for J1939
    return f"{i:08X}"

class _SocketCANBus:
    """python-can based reader/writer (SocketCAN)."""
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
        # bitrate is only used when bringing the link up externally;
        # python-can won't set it itself for SocketCAN.
        self.bus = can.interface.Bus(channel=self.channel, bustype="socketcan")
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
                    self._rxq.put_nowait(Frame(ts=ts, id_hex=_hex_id(arb), data=data))
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
        if not HAS_INTREPID:
            return []
        return [f"intrepid{i}" for i, _ in enumerate(ics.find_all_devices())]

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
        # Optional bitrate
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


class BusManager:
    """Front-end facing manager that hides which backend we're using."""
    def __init__(self):
        self._bus: Optional[object] = None
        self._lock = asyncio.Lock()
        self._info: Dict[str, Any] = {}

    async def discover_interfaces(self) -> List[str]:
        names: List[str] = []
        # SocketCAN names (quick scan). python-can doesn't enumerate by default.
        if HAS_PYCAN:
            pass
        # Intrepid names
        if HAS_INTREPID:
            try:
                names += _IntrepidBus.list_names()
            except Exception:
                pass
        return names

    async def connect(self, channel: str, bitrate: Optional[int] = None) -> Tuple[bool, str]:
        async with self._lock:
            await self.disconnect()
            try:
                if channel.startswith("intrepid"):
                    idx = int(channel.replace("intrepid", "") or "0")
                    b = _IntrepidBus(device_index=idx, bitrate=bitrate)
                    b.open()
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
                    b.open()
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
            if self._bus is not None:
                try:
                    self._bus.close()  # type: ignore[attr-defined]
                except Exception:
                    pass
                self._bus = None
                self._info = {}

    async def send(self, id_hex: str, data_hex: str):
        if self._bus is None:
            raise RuntimeError("Not connected")
        self._bus.send(id_hex, data_hex)  # type: ignore[attr-defined]

    async def get_rx_batch(self, timeout: float, max_items: int) -> List[Frame]:
        # simple poll/sleep loop to roughly match 50–100 Hz batching
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

        # Unique test ID & payload (Extended ID typical for J1939)
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
