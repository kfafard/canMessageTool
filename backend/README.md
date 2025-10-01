# CAN Tool (Browser App)

Shiny, cross-platform CAN send/receive app for bench & field testing.

## Stack
- Frontend: React + Vite + Tailwind (minimal scaffold)
- Backend: FastAPI + python-can (asyncio RX loop, WebSocket stream)

## Quick Start (Local)

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# (Optional) bring up vcan on Linux:
./scripts/setup_vcan.sh
uvicorn app:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
The frontend expects backend at http://localhost:8000

## Docker
```bash
docker compose up --build
```

## Endpoints
- `GET /api/interfaces`
- `POST /api/connect` `{ "channel":"vcan0", "bitrate":null }`
- `POST /api/disconnect`
- `POST /api/send` `{ "frames": [{"id_hex":"18FEE5FF","data_hex":"A0860100FFFFFFFF"}] }`
- `GET /api/presets` / `POST /api/presets`
- `GET /api/groups` / `POST /api/groups`
- `POST /api/log/start` / `POST /api/log/stop`
- `WS /api/stream`

## Dev demo
- Start backend + vcan
- In another shell:
  ```bash
  cd backend
  python scripts/demo_send_presets.py
  ```
- Watch frames arrive via WebSocket (frontend Traffic Viewer)

## Notes
- This scaffold implements all required decoders for specified PGNs/SPNs.
- Health TEC/REC are placeholders (backend exposes keys; extend per HW/driver).
