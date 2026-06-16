"""Bridge to the native pywebview window for OS file/folder pickers.

``app.py`` creates the window and hands it here via :func:`set_window`, so the API
routes (running on the Uvicorn thread) can pop a real native dialog. When the backend
runs without a window — e.g. the Vite dev server hitting ``uvicorn`` directly — the
pickers report themselves unavailable instead of crashing, and the UI hides the buttons.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

# pywebview is a hard dependency of the app, but guard the import so the bare backend
# (used in dev / tests) still loads if it isn't importable for some reason.
try:
    import webview
except Exception:  # pragma: no cover - environment without pywebview
    webview = None  # type: ignore

_window = None


def set_window(window) -> None:
    """Register the live pywebview ``Window`` (called once from ``app.py``)."""
    global _window
    _window = window


def available() -> bool:
    return webview is not None and _window is not None


def pick_folder() -> Optional[str]:
    """Open a native folder picker. Returns the chosen path, or ``None`` if cancelled."""
    _require()
    selection = _window.create_file_dialog(webview.FOLDER_DIALOG)
    if not selection:
        return None
    # pywebview returns a tuple/list of paths even for a single folder.
    return selection[0] if isinstance(selection, (list, tuple)) else str(selection)


def pick_files() -> List[str]:
    """Open a native multi-file picker. Returns the chosen paths (empty if cancelled)."""
    _require()
    selection = _window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
    if not selection:
        return []
    return list(selection)


def save_file(filename: str, data: bytes) -> Optional[str]:
    """Open a native save dialog and write ``data``. Returns the path, or None if cancelled."""
    _require()
    clean_name = filename.strip() or "omnivert-output.md"
    selection = _window.create_file_dialog(webview.SAVE_DIALOG, save_filename=clean_name)
    if not selection:
        return None
    if isinstance(selection, (list, tuple)):
        if not selection:
            return None
        target = Path(selection[0])
    else:
        target = Path(str(selection))
    target.write_bytes(data)
    return str(target)


def _require() -> None:
    if not available():
        raise RuntimeError(
            "Native file dialogs are only available when running inside the desktop app."
        )
