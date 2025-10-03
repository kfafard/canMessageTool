# CAN Tool

A combined backend (FastAPI) + frontend (Vite/React) app for working with CAN bus devices.

- **Windows 11 (Kvaser)**: Uses Kvaser CANlib via python-can.
- **Linux Mint (SocketCAN)**: Uses native SocketCAN (can0) and can auto-bring-up the interface using `pkexec`.

---

## Download (prebuilt)

Go to the Releases page and download:

- **Windows**: `can-tool-windows-<tag>.exe`
- **Linux Mint**: `can-tool-linux-<tag>`

> Replace `<tag>` with the release you want (e.g. `v0.0.5`).

---

## Non-technical quick start

### Windows 11 (Kvaser)

1. Install **Kvaser CANlib drivers** (required for Kvaser hardware).
2. Double-click `can-tool-windows-<tag>.exe`.
3. Your browser opens at **http://127.0.0.1:8000**.
4. In **Interface**, pick **kvaser0** (use kvaser1 if you have multiple).
5. Click **Connect** and start using the tool.

**Notes**
- “Bring up” is not needed on Windows/Kvaser.
- If it won’t connect, check **Kvaser Device Guide** and your drivers.

### Linux Mint (SocketCAN)

1. Make the file executable (first time only), then run it:
   ```bash
   chmod +x can-tool-linux-<tag>
   ./can-tool-linux-<tag>

    Your browser opens at http://127.0.0.1:8000

    .

    In Interface, pick can0 (or vcan0 for virtual testing).

    Click Bring up can0 (250,000 bps).

        A pkexec password prompt may appear to allow ip link commands.

    Click Connect and start using the tool.

Notes

    Avoid prompts by granting capabilities once:

sudo apt install -y libcap2-bin
sudo setcap 'cap_net_raw,cap_net_admin+eip' ./can-tool-linux-<tag>

If port 8000 is “busy”:

    sudo lsof -i TCP:8000 -sTCP:LISTEN -n -P
    kill -9 <PID>

Developer quick start (optional)
Backend

cd backend
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000

Frontend

cd frontend
npm ci
npm run dev

Open http://localhost:5173

in your browser.
CAN helpers (Linux)

The app exposes:

    GET /api/interfaces – list candidate interfaces

    GET /api/can/status?iface=can0 – show current link state

    POST /api/can/bringup – perform SocketCAN bring-up (uses pkexec if needed)

Building a release (tags-only)

# from the repo root
git add .
git commit -m "Win (Kvaser) support; Linux bring-up UX; docs"
git tag v0.0.5
git push origin v0.0.5

The CI workflow publishes:

    can-tool-windows-<tag>.exe

    can-tool-linux-<tag>

to the GitHub Release.


**Why:** Keeps the docs focused on the two platforms we care about, with a non-technical path for each.

---

## what changed, why, and what it fixes (quick)

- **Error we saw (Linux):** `address already in use` on port **8000** → caused by a previous `can-tool` still running.  
  **Fix:** kill PID; no code changes needed.

- **Error we saw (Linux):** `No such device can0` → interface not brought up.  
  **Fix in product:** “Bring up” button calls `/api/can/bringup` (with sudo via `pkexec` if needed).

- **Windows couldn’t “bring up”** → because Windows has **no SocketCAN**.  
  **Fix in product:** add **Kvaser backend** via `python-can` and **hide the Bring Up button** on Windows.  
  Users select `kvaser0` and click **Connect**.

---

## after you paste these in

```bash
# from repo root
git checkout -b feat/kvaser-and-linux-ux
git add backend/requirements.txt backend/bus.py backend/app.py frontend/src/components/ConnectPanel.tsx README.md
git commit -m "Windows Kvaser support + Linux socketcan bring-up UX; docs"
git push -u origin feat/kvaser-and-linux-ux

# build a release (tags-only workflow)
git tag v0.0.5
git push origin v0.0.5