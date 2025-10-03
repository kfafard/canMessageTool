# backend/auto_setup.py
# Helpers to make the app "just work": find a free port, detect CAN,
# and (on Linux) optionally bring up vcan0 using pkexec if no hardware is present.

from __future__ import annotations
import os, platform, socket, subprocess, shutil, sys, json
from typing import Dict, Any

def find_free_port(preferred: int = 8000, max_tries: int = 10) -> int:
    """
    Return a TCP port we can bind, preferring `preferred` and walking upward.
    Avoids crashes when 8000 is already taken.
    """
    port = preferred
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port  # it’s free
            except OSError:
                port += 1
    return preferred  # last resort

def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a command, capture text output, never raise."""
    return subprocess.run(cmd, text=True, capture_output=True)

def _is_linux() -> bool:
    return platform.system() == "Linux"

def list_can_links() -> Dict[str, Any]:
    """
    Enumerate CAN-like interfaces on Linux via `ip -br link`.
    Returns dict: { "ifaces": ["can0","vcan0",...], "raw": "...output..." }
    On non-Linux, returns empty list.
    """
    if not _is_linux():
        return {"ifaces": [], "raw": ""}
    ip = shutil.which("ip")
    if not ip:
        return {"ifaces": [], "raw": "ip-not-found"}
    cp = _run([ip, "-br", "link"])
    ifaces = []
    for line in cp.stdout.splitlines():
        name = line.split()[0]
        if name.startswith("can") or name.startswith("vcan"):
            ifaces.append(name)
    return {"ifaces": ifaces, "raw": cp.stdout.strip()}

def try_create_vcan_with_pkexec(vcan: str = "vcan0") -> Dict[str, Any]:
    """
    Use pkexec (GUI privilege prompt) to:
      modprobe vcan; ip link add dev vcan0 type vcan || true; ip link set vcan0 up
    Returns a result dict with success, message, and logs.
    """
    if not _is_linux():
        return {"success": False, "message": "Not Linux", "logs": {}}

    pkexec = shutil.which("pkexec")
    if not pkexec:
        return {
            "success": False,
            "message": "pkexec not found. Please install polkit, or run the shown commands manually.",
            "logs": {},
        }

    script = (
        "set -e\n"
        "modprobe vcan || true\n"
        f"ip link add dev {vcan} type vcan 2>/dev/null || true\n"
        f"ip link set {vcan} up\n"
    )
    # Write a temporary script because pkexec runs an executable path.
    import tempfile, stat
    with tempfile.NamedTemporaryFile("w", delete=False, prefix="can-setup-", suffix=".sh") as f:
        f.write("#!/usr/bin/env bash\n" + script)
        tmp_path = f.name
    os.chmod(tmp_path, os.stat(tmp_path).st_mode | stat.S_IXUSR)

    # Run pkexec bash /tmp/script.sh (GUI password prompt appears on most desktops)
    cp = _run([pkexec, "bash", tmp_path])
    os.unlink(tmp_path)
    if cp.returncode == 0:
        return {"success": True, "message": "Created/started vcan0 using pkexec.", "logs": {"stdout": cp.stdout, "stderr": cp.stderr}}
    return {
        "success": False,
        "message": "pkexec failed or was canceled.",
        "logs": {"stdout": cp.stdout, "stderr": cp.stderr, "returncode": cp.returncode},
    }

def ensure_can_environment() -> Dict[str, Any]:
    """
    High-level “make CAN usable” routine:
      - If Linux and any can*/vcan* exists → success immediately.
      - Else on Linux, try pkexec to create vcan0.
      - Otherwise, return instructions the UI can show as a fallback.
    This never throws; it returns a status dict for the frontend to display.
    """
    result = {"success": False, "action": "", "message": "", "details": {}}

    ifaces = list_can_links()
    if ifaces["ifaces"]:
        result.update({
            "success": True,
            "action": "noop",
            "message": f"Found CAN interfaces: {', '.join(ifaces['ifaces'])}",
            "details": {"ip_br_link": ifaces["raw"]},
        })
        return result

    if _is_linux():
        # Try privileged vcan bring-up
        vcan = try_create_vcan_with_pkexec("vcan0")
        if vcan["success"]:
            after = list_can_links()
            result.update({
                "success": True,
                "action": "created_vcan",
                "message": "No hardware found; created virtual CAN (vcan0).",
                "details": {"ip_br_link_after": after["raw"]},
            })
            return result

        # pkexec not available or canceled → give copy/paste fallback
        result.update({
            "success": False,
            "action": "show_manual_steps",
            "message": (
                "Could not create vcan automatically. "
                "Please run these commands once, then click Retry:"
            ),
            "details": {
                "linux_commands": [
                    "sudo modprobe vcan",
                    "sudo ip link add dev vcan0 type vcan || true",
                    "sudo ip link set vcan0 up",
                ],
                "pkexec_stdout": vcan["logs"].get("stdout", ""),
                "pkexec_stderr": vcan["logs"].get("stderr", ""),
            },
        })
        return result

    # Non-Linux (Windows/macOS) – we can still operate with vendor backends (e.g., Kvaser),
    # but there is no SocketCAN. The UI can just proceed.
    result.update({
        "success": True,
        "action": "non_linux",
        "message": "Non-Linux platform: SocketCAN not required. Proceed with vendor backends.",
        "details": {"platform": platform.platform()},
    })
    return result

def log_env_summary(logger_print=print) -> None:
    """
    Optional: print a short diagnostic on startup so logs explain what's happening.
    """
    try:
        info = list_can_links()
        logger_print(f"[env] platform={platform.system()} can_ifaces={info['ifaces']}")
    except Exception as e:
        logger_print(f"[env] summary failed: {e}")
