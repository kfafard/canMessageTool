# backend/canio/bus_intrepid.py
from __future__ import annotations
import threading, queue, time
from typing import Optional, Dict, Any, List
import icsneopy as ics

class IntrepidBus:
    """
    Minimal wrapper that makes libicsneo behave like our socketcan bus.
    - Uses CAN1 by default
    - RX collected in a queue; use read_batch() from the WS streamer
    - send() accepts (can_id, data: bytes, extended=True)
    """
    def __init__(self, device_index: int = 0, bitrate: Optional[int] = None):
        self.device_index = device_index
        self.bitrate = bitrate
        self.dev: Optional[ics.Device] = None
        self._rxq: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=10000)
        self._stop = threading.Event()
        self._rx_thread: Optional[threading.Thread] = None
        self._net = ics.Network.NetID.CAN1  # default to CAN1

    # ---- Discovery ----
    @staticmethod
    def list_interfaces() -> List[str]:
        devs = ics.find_all_devices()
        return [f"intrepid{i}" for i, _ in enumerate(devs)]

    # ---- Lifecycle ----
    def open(self) -> None:
        devs = ics.find_all_devices()
        if self.device_index >= len(devs):
            raise RuntimeError("No Intrepid device at that index")
        self.dev = devs[self.device_index]
        if not self.dev.is_open():
            if not self.dev.open():
                raise RuntimeError("Failed to open Intrepid device")

        # Optional: set bitrate if provided
        if self.bitrate:
            try:
                settings = self.dev.get_settings()
                # Not all firmwares expose per-net bitrates; this call may be a no-op
                settings.set_can_bitrate(self._net, self.bitrate)
                self.dev.apply_settings(settings)
            except Exception:
                pass  # safe to ignore; many devices already have a stored bitrate

        # Enable CAN bus
        self.dev.enable_bus(self._net, True)
        self._start_rx()

    def close(self) -> None:
        self._stop.set()
        if self._rx_thread:
            self._rx_thread.join(timeout=1.0)
        if self.dev:
            try:
                self.dev.enable_bus(self._net, False)
                self.dev.close()
            except Exception:
                pass
            self.dev = None

    # ---- TX/RX ----
    def send(self, can_id: int, data: bytes, extended: bool = True) -> None:
        if not self.dev:
            raise RuntimeError("Device not open")
        msg = ics.CanMessage()
        msg.arb_id = can_id
        msg.is_extended = extended
        msg.data = bytearray(data)
        ok = self.dev.transmit(msg)
        if not ok:
            raise RuntimeError("TX failed")

    def _start_rx(self) -> None:
        def loop():
            while not self._stop.is_set():
                try:
                    msgs = self.dev.receive()  # returns a list
                    ts = time.time()
                    for m in msgs:
                        payload = bytes(m.data or b"")
                        self._rxq.put_nowait({
                            "ts": ts,
                            "id": int(m.arb_id),
                            "is_extended": bool(m.is_extended),
                            "dlc": len(payload),
                            "data_hex": payload.hex().upper(),
                        })
                except Exception:
                    time.sleep(0.001)
        self._rx_thread = threading.Thread(target=loop, daemon=True)
        self._rx_thread.start()

    def read_batch(self, max_items: int = 1000) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        while len(out) < max_items:
            try:
                out.append(self._rxq.get_nowait())
            except queue.Empty:
                break
        return out
