# CAN Tool

A simple, bundled **backend (FastAPI)** + **frontend (Vite/React)** app for working with CAN bus on:

* **Linux Mint** via **SocketCAN** (real adapters or virtual `vcan`).
* **Windows 10/11** via **Kvaser CANlib** (python-can “kvaser” backend).

The app bundles everything into a single executable per OS. When you start it, your browser opens to **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

---

## Quick downloads (non-technical users)

1. Go to the **GitHub Releases** page of this repo.
2. Download the file for your OS:

   * **Windows:** `can-tool-windows-vX.Y.Z.exe`
   * **Linux Mint:** `can-tool-linux-vX.Y.Z`
3. Follow the platform guide below.

> Tip: Each tag `vX.Y.Z` automatically builds and attaches the latest executables.

---

## Windows 10/11 (Kvaser) — non-technical guide

**Prerequisites**

* Install **Kvaser CANlib drivers** (from Kvaser). Plug in your Kvaser adapter.

**Run the tool**

1. Double-click `can-tool-windows-vX.Y.Z.exe`.
2. Your browser should open to **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.
3. **Interface**: pick `kvaser0` (or `kvaser1` if you have more than one).
4. Click **Connect**. (There’s no “Bring up” on Windows; bitrate is set through CANlib.)
5. Use **Presets** (right panel) or the **Message Builder** to transmit frames.

**Troubleshooting**

* *No Kvaser interfaces*: install Kvaser CANlib and replug the adapter.
* *Windows Defender SmartScreen*: click **More info → Run anyway** (you built this 🙂

---

## Linux Mint (SocketCAN) — non-technical guide

**Prerequisites (one-time)**

Open Terminal and run:

```bash
sudo apt update
sudo apt install -y can-utils libcap2-bin
```

**Run the tool**

```bash
# In the folder where you downloaded it
chmod +x can-tool-linux-vX.Y.Z
./can-tool-linux-vX.Y.Z
```

The app opens **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

**Choose an interface**

* **Virtual** testing: select `vcan0`.
* **Real hardware**: select your device (often `can0` for USB adapters).

**Bring the link up (Linux only)**

1. Click **Bring up** (sets bitrate for `can*` or creates/ups `vcan*`).

   * For `can*`: the backend does `down → type can bitrate 250000 → up`.
   * For `vcan*`: it creates `vcan0` if missing and brings it up (no bitrate).
   * It will use privileges automatically; if needed you’ll see a password prompt.

2. Click **Connect**.

**Optional (avoid password prompts)**
Grant the binary CAN capabilities once:

```bash
sudo setcap 'cap_net_raw,cap_net_admin+eip' ./can-tool-linux-vX.Y.Z
getcap ./can-tool-linux-vX.Y.Z
# expect: ./can-tool-linux-vX.Y.Z cap_net_admin,cap_net_raw=eip
```

**Troubleshooting**

* **Port 8000 already in use**

  ```bash
  sudo lsof -i TCP:8000 -sTCP:LISTEN -n -P
  kill -9 <PID_SHOWN>
  ```
* **“RTNETLINK answers: Device or resource busy”**
  You tried to set bitrate while the link was up or it’s `vcan`.
  Click **Bring up** again (the tool now forces **down → set type/bitrate → up** for `can*` and skips bitrate on `vcan*`).
* **“Could not access SocketCAN device can0 (No such device)”**
  Your adapter isn’t exposed as `can0`. Check:

  ```bash
  ip -br link | grep -E '^(v?can)'
  dmesg | grep -i can
  ```
* **Diagnostics bundle** (optional):
  `scripts/linux/can_diag.sh` collects logs into a tar.gz you can share.

---

## What’s inside / how it works

* **Backend**: `backend/app.py` (FastAPI).

  * Serves the UI and provides `/api/*`.
  * Linux-only **bring-up** endpoint `/api/can/bringup`:

    * `vcan*`: create if missing, then `ip link set <iface> up`.
    * `can*`: `ip link set <iface> down` → `type can bitrate <bps>` → `up`.
      Uses direct `ip` if the binary has `cap_net_admin`; otherwise falls back to `pkexec` for a GUI elevation prompt.
  * Streams frames over `/api/stream`.
  * Stores user **presets** and **groups** in your user profile (see `/api/config-paths`).

* **CAN backends**

  * **Linux**: SocketCAN via `python-can` (loopback enabled so self-test echoes on `vcan`).
  * **Windows**: Kvaser via `python-can`’s `kvaser` interface (requires CANlib).
  * (Optional) Intrepid `icsneopy` support exists but we’re focusing on Windows+Mint now.

* **Frontend**: Vite/React in `frontend/` (compiled assets are served by the backend).

---

## Developer quick start

### Backend (dev)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
# API docs: http://localhost:8000/docs
```

### Frontend (dev)

```bash
cd frontend
npm ci
npm run dev
# App: http://localhost:5173  (talks to backend on :8000)
```

### Build the bundled executables locally

> CI handles this for releases (see below). For manual builds:

```bash
# 1) Frontend build → copy into backend/static
cd frontend && npm ci && npm run build
mkdir -p ../backend/static && cp -r dist/* ../backend/static/

# 2) Backend bundle
cd ../backend
pip install -r requirements.txt
pip install pyinstaller
pyinstaller can-tool.spec
# Output in dist/ (Windows: can-tool.exe, Linux: can-tool)
```

---

## CI/CD (GitHub Actions)

* Workflow: `.github/workflows/build-and-release.yml`
* **Trigger:** When you push a **tag** matching `v*` (e.g., `v0.0.6`) or run it manually.
* **Matrix:** **ubuntu-latest** and **windows-latest** (macOS disabled).
* **Outputs:** Attaches:

  * `can-tool-linux-vX.Y.Z`
  * `can-tool-windows-vX.Y.Z.exe`

**Tag & push to release:**

```bash
# from your main branch
git pull
git tag v0.0.6
git push origin v0.0.6
```

The workflow builds both executables, uploads them as artifacts, and publishes a GitHub Release for that tag.

---

## API snippets

* Health:
  `curl http://127.0.0.1:8000/api/health`
* List interfaces:
  `curl http://127.0.0.1:8000/api/interfaces`
* Bring up (Linux):
  `curl -X POST http://127.0.0.1:8000/api/can/bringup -H 'Content-Type: application/json' -d '{"iface":"can0","bitrate":250000}'`
* WebSocket stream: `ws://127.0.0.1:8000/api/stream`

---

## Known limitations

* Windows supports **Kvaser** adapters via CANlib. Other Windows adapters are not configured here.
* Linux bring-up requires either:

  * one-time `setcap` (recommended), **or**
  * a pkexec password prompt when you press **Bring up**.

---

## Support

If something doesn’t work:

1. Include your OS, adapter type, and the error popup text.
2. On Linux, attach the diagnostics bundle:

   ```bash
   scripts/linux/can_diag.sh
   ```
3. If port 8000 is stuck, show:

   ```bash
   sudo lsof -i TCP:8000 -sTCP:LISTEN -n -P
   ```

Thanks!
