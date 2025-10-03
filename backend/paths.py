import sys, os, shutil
from pathlib import Path

APP_NAME = "can-tool"

def get_data_dir() -> Path:
    """
    Return a user-writable data dir, creating it if needed.
    - Linux/macOS: ~/.can-tool
    - Windows: %APPDATA%\\can-tool
    """
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home()
    data_dir = base / f".{APP_NAME}"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def ensure_user_file(filename: str) -> Path:
    """
    Ensure <filename> exists in the user data dir.
    - If missing, copy it from bundled _MEIPASS or backend/ as a default.
    - Always return the user-writable path.
    """
    user_dir = get_data_dir()
    user_path = user_dir / filename

    if not user_path.exists():
        bundle_base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
        candidate = bundle_base / filename
        if candidate.exists():
            shutil.copy(candidate, user_path)
        else:
            user_path.write_text("{}", encoding="utf-8")

    return user_path
