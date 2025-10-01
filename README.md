# CAN Tool

CAN Tool is a combined backend (FastAPI) + frontend (Vite/React) project for working with CAN bus devices (SocketCAN and Intrepid).

---

## Backend Quick Start

The backend provides the REST API and WebSocket stream.

### Install dependencies

```bash
cd backend
pip install -r requirements.txt
````

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
cd ~/Desktop/'CAN Message Tool'/can-tool
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

This will show whether backend/frontend are running and their PIDs.

### Dev mode (frontend logs in terminal, Ctrl+C stops both)

```bash
./run.sh up
```

This mode starts the backend in the background and runs the frontend (`npm run dev`) in the foreground so you can see build logs and hot-reload messages.
Press `Ctrl+C` once to stop **both frontend and backend** cleanly.

---

## Notes

* Backend runs with **Uvicorn** → [http://localhost:8000](http://localhost:8000) (Swagger UI at `/docs`)
* Frontend runs with **Vite** → [http://localhost:5173](http://localhost:5173)
* Logs for background runs:

  * `backend/backend.log`
  * `frontend/frontend.log`
* PID files:

  * `backend.pid`
  * `frontend.pid`
    These are used by `run.sh` to kill processes cleanly.

---

## Example Commands

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
curl -X POST http://localhost:8000/api/connect -H "Content-Type: application/json" -d '{"channel":"can0","bitrate":250000}'
```

### Start WebSocket stream

```bash
# Example with websocat
websocat ws://localhost:8000/api/stream
```
