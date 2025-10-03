# backend/app.py
from __future__ import annotations

import asyncio
import json
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from paths import ensure_user_file

# Local modules
from bus import BusManager, Frame
from decoder import decode_frame, safe_hex
from j1939_maps import PGN_NAME_MAP
from models import ConnectRequest, SendRequest, LogStartRequest

# -----------------------------------------------------------------------------
# FastAPI app + CORS
# -----------------------------------------------------------------------------
app = FastAPI(title="CAN Tool Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # relax for dev; tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Paths for data files
# -----------------------------------------------------------------------------

PRESETS_PATH = ensure_user_file("presets.json")
GROUPS_PATH  = ensure_user_file("groups.json")

# -----------------------------------------------------------------------------
# BusManager lazy initialization
# -----------------------------------------------------------------------------
_bus: Optional[BusManager] = None
_bus_init_lock = asyncio.Lock()

async def get_bus() -> BusManager:
    global _bus
    if _bus is not None:
        return _bus
    async with _bus_init_lock:
        if _bus is None:
            _bus = await asyncio.to_thread(BusManager)
    return _bus

def bus_health_snapshot_safe() -> Dict[str, Any]:
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
# Helpers for bring-up
# -----------------------------------------------------------------------------
def _which_any(*names: str) -> str:
    """Return first existing absolute path for a binary name; raise if none."""
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    raise FileNotFoundError(f"Missing required tool: {', '.join(names)}")

def _safe_bitrate(bps: int) -> int:
    allowed = {125000, 250000, 500000, 1000000}
    if bps in allowed:
        return bps
    raise HTTPException(status_code=400, detail=f"Unsupported bitrate {bps}")

def _safe_iface(name: str) -> str:
    import re
    if re.fullmatch(r"(v?can)\d{1,3}", name):
        return name
    raise HTTPException(status_code=400, detail=f"Bad interface name {name}")

# -----------------------------------------------------------------------------
# API routes
# -----------------------------------------------------------------------------

@app.get("/api/interfaces")
async def list_interfaces():
    bus = await get_bus()
    detected = await bus.discover_interfaces()
    base = ["vcan0", "can0"]
    uniq = list(dict.fromkeys(base + detected))
    return {"interfaces": uniq}

@app.post("/api/connect")
async def connect(req: ConnectRequest):
    bus = await get_bus()
    ok, msg = await bus.connect(req.channel, bitrate=req.bitrate)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "connected", "channel": req.channel, "info": bus.health_snapshot()}

@app.post("/api/selftest")
async def selftest():
    bus = await get_bus()
    return await bus.selftest(timeout_ms=300)

@app.post("/api/disconnect")
async def disconnect():
    bus = await get_bus()
    await bus.disconnect()
    return {"status": "disconnected"}

@app.get("/api/health")
async def health():
    return bus_health_snapshot_safe()

@app.post("/api/send")
async def send(req: SendRequest):
    bus = await get_bus()
    out = []
    for it in req.frames:
        try:
            await bus.send(it["id_hex"], it["data_hex"])
            out.append({"id_hex": it["id_hex"], "ok": True})
        except Exception as e:
            out.append({"id_hex": it["id_hex"], "ok": False, "error": str(e)})
    return {"results": out}

# ----------------------------- CAN bring-up (Linux) --------------------------

@app.get("/api/can/status")
async def can_status(iface: str = "can0"):
    """
    Returns a compact 'ip -brief link show dev <iface>' line so the UI can
    infer UP/DOWN. Safe to call even if iface doesn't exist.
    """
    iface = _safe_iface(iface)
    ip = _which_any("ip")
    try:
        proc = subprocess.run(
            [ip, "-brief", "link", "show", "dev", iface],
            capture_output=True, text=True, timeout=3
        )
        out = (proc.stdout or proc.stderr or "").strip()
        ok = proc.returncode == 0
        return {"iface": iface, "ok": ok, "output": out}
    except Exception as e:
        return {"iface": iface, "ok": False, "output": f"error: {e}"}

@app.post("/api/can/bringup")
async def can_bringup(
    payload: Dict[str, Any] = Body(..., example={"iface": "can0", "bitrate": 250000})
):
    iface = _safe_iface(str(payload.get("iface", "can0")))
    bitrate = _safe_bitrate(int(payload.get("bitrate", 250000)))

    # Try to load modules (non-privileged; harmless if already loaded)
    modprobe = _which_any("modprobe")
    for mod in ("kvaser_usb", "can", "can_raw"):
        subprocess.run([modprobe, mod], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # pkexec for elevation with GUI prompt
    pk = shutil.which("pkexec")
    if not pk:
        raise HTTPException(
            status_code=500,
            detail="pkexec (PolicyKit) not found. Install polkit or run the command manually with sudo."
        )

    ip = _which_any("ip")
    cmd = f"{ip} link set {iface} up type can bitrate {bitrate}"
    try:
        res = subprocess.run([pk, "bash", "-lc", cmd],
                             capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timed out waiting for pkexec approval.")

    if res.returncode != 0:
        msg = (res.stderr or res.stdout or "Unknown error").strip()
        if "dismissed authentication" in msg.lower():
            raise HTTPException(status_code=400, detail="Cancelled by user.")
        raise HTTPException(status_code=500, detail=f"pkexec failed: {msg}")

    return {"ok": True, "iface": iface, "bitrate": bitrate}

# ----------------------------- Presets / Groups ------------------------------

@app.get('/api/presets')
async def get_presets():
    try:
        with PRESETS_PATH.open('r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"presets": [], "frames": []}

    presets, frames = [], []
    if isinstance(data, dict):
        if "presets" in data and isinstance(data["presets"], list):
            presets = data["presets"]
            frames = [
                {"id_hex": p.get("id_hex"), "data_hex": p.get("data_hex"), "name": p.get("name")}
                for p in presets if "id_hex" in p and "data_hex" in p
            ]
        elif "frames" in data and isinstance(data["frames"], list):
            frames = data["frames"]
            presets = [
                {"name": f.get("name"), "id_hex": f.get("id_hex"), "data_hex": f.get("data_hex")}
                for f in frames if "id_hex" in f and "data_hex" in f
            ]
    return {"presets": presets, "frames": frames}

@app.post("/api/presets")
async def save_presets(payload: Dict[str, Any]):
    tmp = PRESETS_PATH.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(PRESETS_PATH)
    return {"status": "ok"}

@app.get("/api/groups")
async def get_groups():
    try:
        with GROUPS_PATH.open("r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"groups": []}

@app.post("/api/groups")
async def save_groups(payload: Dict[str, Any]):
    tmp = GROUPS_PATH.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(GROUPS_PATH)
    return {"status": "ok"}

# ----------------------------- Logging control -------------------------------

@app.post("/api/log/start")
async def log_start(req: LogStartRequest):
    global logging_enabled, log_buffer
    logging_enabled = True
    log_buffer = ["timestamp,id_hex,pgn,sa,data_hex,decoded_json\n"]
    return {"status": "logging"}

@app.post("/api/log/stop")
async def log_stop():
    global logging_enabled
    logging_enabled = False
    content = "".join(log_buffer).encode("utf-8")
    return {"csv": content.decode("utf-8")}

# ----------------------------- WebSocket stream ------------------------------

@app.websocket("/api/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    bus = await get_bus()
    await ws.send_json({"type": "connected", "info": bus_health_snapshot_safe()})

    try:
        while True:
            batch = await bus.get_rx_batch(timeout=0.02, max_items=200)
            items = []
            for fr in batch:
                dec = decode_frame(fr)
                items.append({
                    "ts": fr.ts,
                    "id_hex": fr.id_hex,
                    "data_hex": safe_hex(fr.data),
                    "pgn": dec.get("pgn"),
                    "sa": dec.get("sa"),
                    "decoded": dec.get("decoded"),
                    "name": PGN_NAME_MAP.get(dec.get("pgn")),
                })
            if items:
                await ws.send_json({"type": "frames", "items": items})
            else:
                await asyncio.sleep(0.05)
                await ws.send_json({"type": "health", "value": bus_health_snapshot_safe()})
    except WebSocketDisconnect:
        return

# ----------------------------- Static UI (mounted last) ----------------------

def _static_dir() -> Path:
    # PyInstaller-safe: when bundled, data is in sys._MEIPASS/static
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    cand = base / "static"
    return cand if cand.exists() else Path(__file__).parent / "static"

STATIC_DIR = _static_dir()
if STATIC_DIR.exists():
    # Serve built Vite UI at site root. /api/* remains handled by API routes.
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")

@app.get("/api/config-paths")
async def config_paths():
    return {
        "presets": str(PRESETS_PATH),
        "groups": str(GROUPS_PATH),
    }
