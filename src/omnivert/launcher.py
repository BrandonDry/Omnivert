r"""Omnivert desktop launcher.

Boots the FastAPI backend (Uvicorn) on a free localhost port in a background thread,
waits for it to come up, then opens a native pywebview window pointing at it. Closing
the window shuts the server down and exits.

Run via ``run.bat`` (which calls the project venv's Python) or directly:
    ..\.venv\Scripts\python -m omnivert
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn
import webview

PACKAGE_DIR = Path(__file__).resolve().parent
APP_DIR = PACKAGE_DIR.parents[1]
FRONTEND_DIST = PACKAGE_DIR / "web"
if not FRONTEND_DIST.exists():
    frozen_web = Path(getattr(sys, "_MEIPASS", "")) / "web"
    FRONTEND_DIST = frozen_web if frozen_web.exists() else APP_DIR / "frontend" / "dist"

WINDOW_TITLE = "Omnivert"

# Shown when the frontend hasn't been built yet.
_NOT_BUILT_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>Omnivert</title>
<style>
  body { font-family: Segoe UI, system-ui, sans-serif; background:#0b0b0c; color:#e8e8ea;
         display:flex; min-height:100vh; align-items:center; justify-content:center; margin:0; }
  .card { max-width:520px; padding:2rem 2.25rem; border:1px solid #2a2a2e; border-radius:14px;
          background:#151517; }
  h1 { margin:0 0 .5rem; font-size:1.35rem; }
  code { background:#222; padding:.15rem .4rem; border-radius:6px; font-size:.9em; }
  p { color:#a8a8ad; line-height:1.55; }
</style></head><body>
  <div class="card">
    <h1>Frontend not built yet</h1>
    <p>The UI hasn't been compiled. Build it once, then relaunch:</p>
    <p><code>build.bat</code> &nbsp;(or&nbsp; <code>npm run build --prefix frontend</code>)</p>
    <p>The backend API is already running and reachable under <code>/api</code>.</p>
  </div>
</body></html>
"""


def _free_port(preferred: int = 8765) -> int:
    """Return a usable localhost port, preferring 8765, else an OS-assigned one."""
    for candidate in (preferred, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", candidate))
                return s.getsockname()[1]
        except OSError:
            continue
    return preferred


class BackendServer:
    """Runs Uvicorn in a daemon thread and exposes start/wait/stop."""

    def __init__(self, port: int):
        from .main import app

        self.port = port
        config = uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="warning", access_log=False
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def wait_until_ready(self, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if getattr(self._server, "started", False):
                return True
            time.sleep(0.05)
        return False

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)


def main() -> int:
    port = _free_port()
    server = BackendServer(port)
    server.start()
    if not server.wait_until_ready():
        print("Backend failed to start in time.", file=sys.stderr)
        return 1

    base_url = f"http://127.0.0.1:{port}"
    if FRONTEND_DIST.exists():
        window_kwargs = {"url": base_url}
    else:
        # Backend is up but UI isn't built — show instructions instead of a blank window.
        window_kwargs = {"html": _NOT_BUILT_HTML}

    window = webview.create_window(
        WINDOW_TITLE,
        width=1200,
        height=820,
        min_size=(880, 620),
        **window_kwargs,
    )

    # Hand the live window to the backend so its routes can open native file/folder
    # pickers (see window_bridge.py).
    from . import window_bridge

    window_bridge.set_window(window)

    try:
        webview.start()  # blocks on the main thread until the window closes
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
