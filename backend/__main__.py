# backend/__main__.py
from __future__ import annotations
import os
import uvicorn

def _get_app():
    # Import your FastAPI app from backend/app.py
    from app import app  # noqa: WPS433 (runtime import is fine here)
    return app

def main() -> None:
    host = os.getenv("CAN_TOOL_HOST", "127.0.0.1")
    port = int(os.getenv("CAN_TOOL_PORT", "8000"))
    uvicorn.run(_get_app(), host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
