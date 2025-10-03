# CAN Tool

CAN Tool is a combined **backend (FastAPI)** + **frontend (Vite/React)** app for working with CAN bus devices (SocketCAN, Intrepid, etc.).  
It includes helpers for bringing up a CAN interface (e.g., `can0`) and for quick hardware tests.

---

## 🚀 Quick Download (Non-Technical Users)

You don’t need to install anything. Download the prebuilt app for **your OS** from GitHub Releases.

### Step-by-step (all platforms)

1) Open the project’s **Releases** page (top bar → **Releases**) and click the **latest version** (looks like `vX.Y.Z`).  
2) Under **Assets**, download the file for **your OS**:
   - **Windows** → typically a ZIP named like `can-tool-windows-<tag>.zip`.
   - **macOS (Apple Silicon)** → a ZIP like `can-tool-macos-<tag>.zip`.  
     _Note: built for Apple Silicon (arm64)._
   - **Linux (x86_64)** → a TAR/ZIP like `can-tool-ubuntu-<tag>.tar.gz` (from Ubuntu 24.04, glibc 2.39).
3) **Extract** the archive (right-click → Extract / “Open archive”).
4) Inside the extracted folder, run the app:
   - **Windows**: double-click `can-tool.exe`.
   - **macOS**: in Finder, **Right-click → Open** on `can-tool` the first time (bypasses Gatekeeper), then click **Open**.
   - **Linux**: open Terminal in that folder:
     ```bash
     chmod +x ./can-tool
     ./can-tool
     ```
5) Your browser will open to **http://127.0.0.1:8000** (the tool’s UI).  
6) Connect to your CAN interface and use the tool.

### Notes for each OS

- **Windows**
  - If SmartScreen warns about an unknown publisher: click **More info → Run anyway**.
  - If a firewall prompt appears: allow access on **Private networks** (localhost only).
  - Install your adapter’s drivers (Kvaser, Intrepid, etc.).

- **macOS (Apple Silicon)**
  - First launch: **Right-click → Open** (Gatekeeper) as mentioned above.
  - If you blocked it accidentally: System Settings → **Privacy & Security** → allow the app.

- **Linux**
  - Built on **Ubuntu 24.04**. On older distros you may need newer glibc.
  - To use SocketCAN you may need `can-utils` and interface permissions:
    ```bash
    sudo apt update
    sudo apt install -y can-utils
    # Example bring-up at 250 kbit/s
    sudo ip link set can0 type can bitrate 250000
    sudo ip link set can0 up
    ```
  - Or use the helper commands in **run.sh** (see below).

---

## 🏗️ How Releases Are Built (CI)

- Builds are created **only when you push a Git tag** (example: `v0.3.0`).  
- The GitHub Action compiles the app for **Windows**, **macOS (arm64)**, and **Linux (x86_64)** and attaches the artifacts to that Release.

### Cut a new Release (maintainers)

```bash
# 1) Commit all changes on your branch
git add -A
git commit -m "Your message"

# 2) Tag with a semver-style tag (this is what triggers the build)
git tag v0.3.0

# 3) Push the tag to GitHub (this starts the CI build + release)
git push origin v0.3.0
````

Then go to **GitHub → Actions** or **Releases** and download the artifacts.

---

## 🧪 Local Development (from source)

### Backend (FastAPI)

**Requirements:** Python 3.12

```bash
# From repo root
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Verify:

* Swagger UI → [http://localhost:8000/docs](http://localhost:8000/docs)
* Health → `curl http://localhost:8000/api/health`

### Frontend (Vite + React)

**Requirements:** Node.js 20

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

---

## ▶️ Running Backend + Frontend Together (dev helper)

`run.sh` manages both backend (port **8000**) and frontend (Vite on **5173**):

```bash
./run.sh start     # start both in background
./run.sh stop      # stop both
./run.sh restart
./run.sh status    # shows backend/frontend PIDs + CAN status
./run.sh up        # backend in background, frontend in foreground (Ctrl+C stops both)
```

**Logs (background runs):**

* `backend/backend.log`
* `frontend/frontend.log`

**PID files:** `backend.pid`, `frontend.pid`, `candump.pid`

---

## 🚌 CAN Interface Helpers

```bash
./run.sh can-up       # Load modules and bring up CAN (250000 bps) as can0
./run.sh can-down     # Stop candump (if any) and bring can0 down
./run.sh can-test     # Bring up (if needed), run candump, send one test frame, show log
```

**Auto-CAN mode** (start/stop brings CAN up/down automatically):

```bash
AUTO_CAN=1 ./run.sh start
AUTO_CAN=1 ./run.sh stop
# also works with: AUTO_CAN=1 ./run.sh up
```

Quick sanity test:

```bash
./run.sh can-up
./run.sh can-test
./run.sh can-down
```

---

## 🔌 Ports & URLs

* Backend (Uvicorn): **[http://localhost:8000](http://localhost:8000)** (Swagger at `/docs`)
* Frontend (Vite dev): **[http://localhost:5173](http://localhost:5173)**
* Packaged app (all-in-one): opens **[http://127.0.0.1:8000](http://127.0.0.1:8000)** automatically

---

## 🧰 Example API Calls

```bash
# Health
curl http://localhost:8000/api/health

# List interfaces
curl http://localhost:8000/api/interfaces

# Connect to a CAN interface
curl -X POST http://localhost:8000/api/connect \
     -H "Content-Type: application/json" \
     -d '{"channel":"can0","bitrate":250000}'

# WebSocket stream (example using websocat)
# websocat ws://localhost:8000/api/stream
```

---

## 🧯 Troubleshooting

**Non-technical users**

* Browser didn’t open? Manually visit [http://127.0.0.1:8000](http://127.0.0.1:8000) after starting the app.
* “Port already in use”? Close other apps using port **8000** and try again.

**Windows**

* SmartScreen blocked it → click **More info → Run anyway**.
* “MSVCP…”/runtime errors → run Windows Update and install vendor CAN drivers.

**macOS**

* “App is from an unidentified developer” → **Right-click → Open** (first launch).
* If blocked: System Settings → **Privacy & Security** → allow the app.

**Linux**

* “Permission denied” → `chmod +x ./can-tool`.
* “Address already in use” → another app uses port **8000**. Kill it or change port.
* SocketCAN: ensure `can0` is **UP** (`ip -details link show can0`) or use `./run.sh can-up`.

**Developers (building the frontend)**

* If you ever see `Cannot find module @rollup/rollup-<platform>` during `vite build`, it’s npm’s optional-deps quirk. Fix locally with:

  ```bash
  # from frontend/
  npm ci
  # then one of:
  npm i -D @rollup/rollup-linux-x64-gnu@^4
  npm i -D @rollup/rollup-darwin-arm64@^4
  npm i -D @rollup/rollup-win32-x64-msvc@^4
  ```

---

## 📦 Packaging Locally (optional, for maintainers)

The CI uses **PyInstaller** with `can-tool.spec`. To build manually:

```bash
# Build frontend for production
cd frontend
npm ci
npm run build
cd ..

# Stage frontend assets into backend/static
mkdir -p backend/static
cp -r frontend/dist/* backend/static/

# Build the one-file executable
pip install -U pip pyinstaller -r backend/requirements.txt
pyinstaller can-tool.spec

# Result appears under: dist/
```

---

## ✅ Support Matrix

* **Windows**: 64-bit, Windows 10/11, vendor CAN drivers required.
* **macOS**: Apple Silicon (arm64). Use Right-click → Open on first run.
* **Linux**: x86_64 (built on Ubuntu 24.04 / glibc 2.39). SocketCAN users may need `can-utils`.

---

