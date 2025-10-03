# backend/app.py
from __future__ import annotations

import asyncio
import json
import sys
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel 
from paths import ensure_user_file
from auto_setup import ensure_can_environment, log_env_summary

# Local modules
from bus import BusManager
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

# ---------------- Privileged runner and link helpers ----------------

# backend/app.py  (replace _run_priv)
def _run_priv(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """
    Run a privileged netlink command.

    Behavior:
    - Try normally first.
    - If it fails (non-zero exit), and it *looks* like a permission problem,
      retry via pkexec (GUI password) when available.
    - If check=True, raise CalledProcessError for a non-zero final result.
    """
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or "")
        looks_perm = (
            "Operation not permitted" in stderr
            or "permission denied" in stderr.lower()
            or proc.returncode in (1, 126, 127)
        )
        if looks_perm and shutil.which("pkexec"):
            proc = subprocess.run(["pkexec", *cmd], text=True, capture_output=True)

    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr)

    return proc

def _ip_exists(iface: str) -> bool:
    r = subprocess.run(["ip", "-br", "link", "show", iface], text=True, capture_output=True)
    return r.returncode == 0

def _ip_details(iface: str) -> str:
    r = subprocess.run(["ip", "-br", "link", "show", iface], text=True, capture_output=True)
    return (r.stdout or r.stderr or "").strip()


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
def _safe_iface(name: str) -> str:
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
def api_can_status(iface: str):
    if not sys.platform.startswith("linux"):
        # Keep behavior consistent; Windows brings up Kvaser via python-can, not iproute
        return {"iface": iface, "ok": True, "output": "status not applicable on this OS"}
    exists = _ip_exists(iface)
    return {"iface": iface, "ok": exists, "output": _ip_details(iface) if exists else f"{iface}: not present"}

class BringUpReq(BaseModel):
    iface: str
    bitrate: Optional[int] = 250000  # ignored for vcan*

@app.post("/api/can/bringup")
def api_can_bringup(req: BringUpReq):
    if not sys.platform.startswith("linux"):
        raise HTTPException(status_code=400, detail="Bring-up only supported on Linux.")

    iface = req.iface.strip()
    bitrate = int(req.bitrate or 250000)

    # Load base CAN modules; ignore if already loaded
    for mod in ("can", "can_raw"):
        try:
            _run_priv(["modprobe", mod], check=False)
        except Exception:
            pass

    # Snapshot before, for debugging in UI
    exists = _ip_exists(iface)
    before = _ip_details(iface) if exists else f"{iface}: (not present)"

    try:
        if iface.startswith("vcan"):
            # Create vcanX if missing (ignore race "File exists")
            if not exists:
                try:
                    _run_priv(["ip", "link", "add", "dev", iface, "type", "vcan"], check=True)
                except subprocess.CalledProcessError as e:
                    if "File exists" not in (e.stderr or ""):
                        raise
            # Ensure it's UP (no bitrate on vcan)
            _run_priv(["ip", "link", "set", iface, "up"], check=True)
            final = _ip_details(iface)
            return {"ok": True, "iface": iface, "bitrate": None, "before": before, "output": final}

        # Physical SocketCAN device: DOWN -> type can bitrate -> UP
        # Bring it down first (ignore error if it's already down)
        try:
            _run_priv(["ip", "link", "set", iface, "down"], check=True)
        except subprocess.CalledProcessError:
            # Ignore errors like "Cannot find device" — the next steps will clarify state
            pass
        # Configure bitrate/type (this is what fails if you try it on vcan or while UP)
        _run_priv(["ip", "link", "set", iface, "type", "can", "bitrate", str(bitrate)], check=True)
        # Bring it up
        _run_priv(["ip", "link", "set", iface, "up"], check=True)

    except subprocess.CalledProcessError as e:
        # Convert iproute2 errors to a clean message for the toast
        msg = (e.stderr or e.stdout or str(e)).strip()
        raise HTTPException(status_code=500, detail=f"pkexec failed: {msg}")

    final = _ip_details(iface)
    return {"ok": True, "iface": iface, "bitrate": bitrate, "before": before, "output": final}


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

@app.get("/api/platform")
async def api_platform():
    """
    Report the server's platform: 'linux', 'win32', 'darwin', etc.
    Frontend uses this to hide Bring Up on Windows (not needed for Kvaser).
    """
    return {"platform": sys.platform}

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
    
@app.on_event("startup")
async def _env_summary():
    # Writes a one-line summary into the log for support
    log_env_summary()

@app.post("/api/auto_setup")
def api_auto_setup():
    """
    UI hits this when the user clicks 'Fix CAN' or on first-run.
    Never throws; returns a dict with success/message/details.
    """
    return ensure_can_environment()


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
