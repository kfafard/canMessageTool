# backend/app.py
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Local modules
from bus import BusManager, Frame
from decoder import decode_frame, safe_hex
from j1939_maps import PGN_NAME_MAP
from models import ConnectRequest, SendRequest, LogStartRequest

# -----------------------------------------------------------------------------
# FastAPI app + CORS
# -----------------------------------------------------------------------------
app = FastAPI(title="CAN Tool Backend", version="0.1.0")

# During local dev we allow all origins; tighten in prod if needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # e.g., ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Paths for data files (robust even if uvicorn is started from another folder)
# -----------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent
PRESETS_PATH = DATA_DIR / "presets.json"
GROUPS_PATH = DATA_DIR / "groups.json"

# -----------------------------------------------------------------------------
# BusManager lazy initialization
# -----------------------------------------------------------------------------
# Previously `bus_manager = BusManager()` at import time could block startup.
# We now create it lazily, off the event loop, the first time it's needed.
_bus: Optional[BusManager] = None
_bus_init_lock = asyncio.Lock()  # prevents double-init under concurrency


async def get_bus() -> BusManager:
    """
    Return a ready BusManager instance, creating it on first use.

    Creation is offloaded to a worker thread via asyncio.to_thread so the
    FastAPI event loop is never blocked by heavy / blocking code inside
    BusManager.__init__(). This keeps /docs and /api routes responsive.
    """
    global _bus
    if _bus is not None:
        return _bus

    async with _bus_init_lock:
        if _bus is None:
            # Build the instance in a thread to avoid blocking the event loop
            _bus = await asyncio.to_thread(BusManager)
    return _bus


def bus_health_snapshot_safe() -> Dict[str, Any]:
    """
    Return a health snapshot even if the bus isn't initialized yet.
    """
    if _bus is None:
        return {"ready": False, "channel": None, "status": "initializing"}
    try:
        return _bus.health_snapshot()
    except Exception as e:
        return {"ready": False, "error": str(e)}


# -----------------------------------------------------------------------------
# In-memory logging buffer (CSV)
# -----------------------------------------------------------------------------
logging_enabled = False
log_buffer: List[str] = ["timestamp,id_hex,pgn,sa,data_hex,decoded_json\n"]

# -----------------------------------------------------------------------------
# API routes
# -----------------------------------------------------------------------------

@app.get("/api/interfaces")
async def list_interfaces():
    """
    Return a list of CAN interface names.
    Always includes a baseline of ['vcan0', 'can0'] for convenience.
    """
    bus = await get_bus()
    detected = await bus.discover_interfaces()
    base = ["vcan0", "can0"]
    uniq = list(dict.fromkeys(base + detected))
    return {"interfaces": uniq}


@app.post("/api/connect")
async def connect(req: ConnectRequest):
    """
    Connect to a CAN channel (e.g., 'can0', 'vcan0') with an optional bitrate.
    """
    bus = await get_bus()
    ok, msg = await bus.connect(req.channel, bitrate=req.bitrate)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "connected", "channel": req.channel, "info": bus.health_snapshot()}


@app.post("/api/selftest")
async def selftest():
    """
    Run a short self-test (implementation in BusManager).
    """
    bus = await get_bus()
    return await bus.selftest(timeout_ms=300)


@app.post("/api/disconnect")
async def disconnect():
    """
    Disconnect and release the CAN channel.
    """
    bus = await get_bus()
    await bus.disconnect()
    return {"status": "disconnected"}


@app.get("/api/health")
async def health():
    """
    Health snapshot; safe even before the bus is fully ready.
    """
    return bus_health_snapshot_safe()


@app.post("/api/send")
async def send(req: SendRequest):
    """
    Send one or more frames; returns per-frame status.
    """
    bus = await get_bus()
    out = []
    for it in req.frames:
        try:
            await bus.send(it["id_hex"], it["data_hex"])
            out.append({"id_hex": it["id_hex"], "ok": True})
        except Exception as e:
            out.append({"id_hex": it["id_hex"], "ok": False, "error": str(e)})
    return {"results": out}


# ----------------------------- Presets / Groups ------------------------------

@app.get('/api/presets')
async def get_presets():
    # Always return *both* shapes so any frontend version works.
    try:
        with PRESETS_PATH.open('r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"presets": [], "frames": []}

    presets = []
    frames = []

    if isinstance(data, dict):
        if "presets" in data and isinstance(data["presets"], list):
            presets = data["presets"]
            # derive frames
            frames = [
                {"id_hex": p.get("id_hex"), "data_hex": p.get("data_hex"), "name": p.get("name")}
                for p in presets
                if "id_hex" in p and "data_hex" in p
            ]
        elif "frames" in data and isinstance(data["frames"], list):
            frames = data["frames"]
            # derive presets (lossy; only name/id/data)
            presets = [
                {"name": f.get("name"), "id_hex": f.get("id_hex"), "data_hex": f.get("data_hex")}
                for f in frames
                if "id_hex" in f and "data_hex" in f
            ]
    return {"presets": presets, "frames": frames}


@app.post("/api/presets")
async def save_presets(payload: Dict[str, Any]):
    """
    Write presets.json atomically (best effort).
    """
    tmp = PRESETS_PATH.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(PRESETS_PATH)
    return {"status": "ok"}


@app.get("/api/groups")
async def get_groups():
    """
    Read groups.json; return an empty default if file is missing.
    """
    try:
        with GROUPS_PATH.open("r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"groups": []}


@app.post("/api/groups")
async def save_groups(payload: Dict[str, Any]):
    """
    Write groups.json atomically (best effort).
    """
    tmp = GROUPS_PATH.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(GROUPS_PATH)
    return {"status": "ok"}


# ----------------------------- Logging control -------------------------------

@app.post("/api/log/start")
async def log_start(req: LogStartRequest):
    """
    Enable in-memory CSV logging. The UI can later download via /api/log/stop.
    """
    global logging_enabled, log_buffer
    logging_enabled = True
    log_buffer = ["timestamp,id_hex,pgn,sa,data_hex,decoded_json\n"]
    return {"status": "logging"}


@app.post("/api/log/stop")
async def log_stop():
    """
    Disable logging and return the CSV as a string in the JSON payload.
    """
    global logging_enabled
    logging_enabled = False
    content = "".join(log_buffer).encode("utf-8")
    return {"csv": content.decode("utf-8")}


# ----------------------------- WebSocket stream ------------------------------

@app.websocket("/api/stream")
async def stream(ws: WebSocket):
    """
    Pushes:
      - on connect: a 'connected' snapshot
      - periodically: 'health' if idle
      - batches of received frames as 'frames'
    """
    await ws.accept()

    # Instantiate/get the bus lazily so WS is responsive even if init takes time
    bus = await get_bus()

    # One-time connection snapshot so the UI can show a banner/badge
    await ws.send_json({"type": "connected", "info": bus_health_snapshot_safe()})

    try:
        while True:
            # Pull a batch of frames from the bus
            batch = await bus.get_rx_batch(timeout=0.02, max_items=200)
            items = []
            for fr in batch:
                dec = decode_frame(fr)
                items.append(
                    {
                        "ts": fr.ts,
                        "id_hex": fr.id_hex,
                        "data_hex": safe_hex(fr.data),
                        "pgn": dec.get("pgn"),
                        "sa": dec.get("sa"),
                        "decoded": dec.get("decoded"),
                        "name": PGN_NAME_MAP.get(dec.get("pgn")),
                    }
                )
            if items:
                await ws.send_json({"type": "frames", "items": items})
            else:
                # Lightweight heartbeat and health snapshot while idle
                await asyncio.sleep(0.05)
                await ws.send_json({"type": "health", "value": bus_health_snapshot_safe()})
    except WebSocketDisconnect:
        return
