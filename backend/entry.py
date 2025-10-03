# backend/entry.py
# Launch Uvicorn on a free port (prefer 8000) and open the browser there.

import webbrowser
import uvicorn
from auto_setup import find_free_port
from app import app  # your FastAPI instance

def main():
    port = find_free_port(8000, max_tries=10)
    url = f"http://127.0.0.1:{port}"
    print(f"[launch] Starting CAN Tool at {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[launch] Could not open browser: {e}")
    uvicorn.run(app, host="127.0.0.1", port=port)

if __name__ == "__main__":
    main()
