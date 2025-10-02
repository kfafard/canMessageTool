# CAN Tool

CAN Tool is a combined backend (FastAPI) + frontend (Vite/React) project for working with CAN bus devices (SocketCAN and Intrepid).
It also includes helpers for managing a CAN interface (`can0`) and running quick hardware tests.

---
## Packaged Executable

For non-technical users, you can download the prebuilt **CAN Tool** binary:

- Windows: `can-tool.exe`
- Linux: `CAN_Tool-x86_64.AppImage`

### Usage
1. Double-click the executable
2. Your browser will open automatically to [http://127.0.0.1:8000](http://127.0.0.1:8000)
3. Connect to your CAN interface and use the tool

### Notes
- Make sure your CAN interface drivers are installed
- Linux users may need `can-utils` and socket permissions (see below)

---

## Backend Quick Start

The backend provides the REST API and WebSocket stream.

### Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

Make sure you have `uvicorn` installed (comes from `requirements.txt`). If needed:

```bash
pip install uvicorn[standard] fastapi
```

### Run backend

```bash
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Verify

* Open [http://localhost:8000/docs](http://localhost:8000/docs) for Swagger API UI
* Health check: `curl http://localhost:8000/api/health`

Logs: backend writes to `backend/backend.log` when run via `run.sh`.

---

## Frontend Quick Start

The frontend is a Vite + React app for interacting with the backend.

### Install dependencies

```bash
cd frontend
npm install
```

### Run frontend (dev mode with hot reload)

```bash
npm run dev
```

### Verify

* Open [http://localhost:5173](http://localhost:5173) in your browser

Logs: frontend writes to `frontend/frontend.log` when run via `run.sh`.

---

## Running Backend + Frontend Together

We use a top-level `run.sh` orchestrator script that manages both backend (FastAPI on port **8000**) and frontend (Vite dev server on port **5173**) with simple commands.

### Start both (background)

```bash
./run.sh start
```

### Stop both

```bash
./run.sh stop
```

### Restart both

```bash
./run.sh restart
```

### Status

```bash
./run.sh status
```

This will show whether backend/frontend are running, their PIDs, and the CAN interface status.

### Dev mode (frontend logs in terminal, Ctrl+C stops both)

```bash
./run.sh up
```

This mode starts the backend in the background and runs the frontend (`npm run dev`) in the foreground so you can see build logs and hot-reload messages.
Press `Ctrl+C` once to stop **both frontend and backend** cleanly.

---

## CAN Interface Integration

This project includes helpers to manage your CAN adapter alongside backend/frontend services.

### CAN Commands

```bash
./run.sh can-up       # Load modules and bring up CAN interface at 250000 bps
./run.sh can-down     # Stop candump (if any) and bring the CAN interface down
./run.sh can-test     # Bring up (if needed), start candump, send one test frame, show log
```

### Auto-CAN Mode

If you want the CAN interface to automatically come up when you start the tool (and shut down cleanly when you stop):

```bash
AUTO_CAN=1 ./run.sh start
AUTO_CAN=1 ./run.sh stop
```

This also works for `./run.sh up`.

### Status

The `status` command now shows CAN info:

```bash
./run.sh status
```

Example output:

```
--- Backend ---
Backend is running (PID=1234)
--- Frontend ---
Frontend is running (PID=5678).
--- CAN Status ---
can0             UP             <NOARP,UP,LOWER_UP,ECHO>
candump: not running
```

---

## Quick Test Workflow

For verifying that your CAN hardware is functional:

```bash
./run.sh can-up         # bring up CAN at 250k
./run.sh can-test       # send test frame + log
./run.sh can-down       # clean shutdown
```

---

## Notes

* Backend runs with **Uvicorn** → [http://localhost:8000](http://localhost:8000) (Swagger UI at `/docs`)
* Frontend runs with **Vite** → [http://localhost:5173](http://localhost:5173)
* Logs for background runs:

  * `backend/backend.log`
  * `frontend/frontend.log`
* PID files (managed by `run.sh`):

  * `backend.pid`
  * `frontend.pid`
  * `candump.pid`

---

## Example API Commands

### Check backend health

```bash
curl http://localhost:8000/api/health
```

### List interfaces

```bash
curl http://localhost:8000/api/interfaces
```

### Connect to an interface

```bash
curl -X POST http://localhost:8000/api/connect \
     -H "Content-Type: application/json" \
     -d '{"channel":"can0","bitrate":250000}'
```

### Start WebSocket stream

```bash
# Example with websocat
websocat ws://localhost:8000/api/stream
```