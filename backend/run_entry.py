# backend/run_entry.py
import threading, time, webbrowser, socket
import uvicorn
from app import app  # your FastAPI instance

HOST = "127.0.0.1"
PORT = 8000
URL  = f"http://{HOST}:{PORT}/"

def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) != 0

def _open_browser_when_ready():
    # wait until the server is actually listening, then open default browser
    for _ in range(120):  # ~6s total max
        if not _port_is_free(HOST, PORT):
            time.sleep(0.2)
            try:
                webbrowser.open(URL)
            except Exception:
                pass
            return
        time.sleep(0.05)

if __name__ == "__main__":
    t = threading.Thread(target=_open_browser_when_ready, daemon=True)
    t.start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
