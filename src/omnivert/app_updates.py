"""Self-update for Omnivert from the developer's GitHub Releases.

The check path is shared by dev and frozen builds. Applying an update is runtime-aware:
dev/package installs can use a release wheel via pip, while PyInstaller-frozen Windows
builds download and launch the release ``Setup.exe``.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from datetime import datetime, timezone
from importlib import metadata
from typing import Dict, List, Optional

from . import gh
from . import installer_update
from . import settings as settings_module
from .app_version import __version__ as APP_VERSION

# The distribution name the app is published under (Phase B packaging).
APP_PACKAGE = "omnivert"

_lock = threading.Lock()
_state: Dict[str, object] = {
    "state": "idle",  # idle | running | success | error
    "message": None,
    "output": None,
    "old_version": None,
    "new_version": None,
    "restart_required": False,
}


# --- config --------------------------------------------------------------------------

def _repo() -> Optional[str]:
    repo = (settings_module.load().get("app_repo") or "").strip().strip("/")
    # Accept "owner/repo"; ignore blanks and the placeholder default.
    if repo and repo.count("/") == 1 and repo.lower() != "owner/repo":
        return repo
    return None


# --- check ---------------------------------------------------------------------------

def _wheel_asset(release: dict) -> Optional[str]:
    for asset in release.get("assets") or []:
        name = (asset.get("name") or "").lower()
        if name.endswith(".whl"):
            return asset.get("browser_download_url")
    return None


def _installer_asset(release: dict) -> Optional[str]:
    for asset in release.get("assets") or []:
        name = (asset.get("name") or "").lower()
        if name.endswith(".exe") and "omnivert" in name and "setup" in name:
            return asset.get("browser_download_url")
    return None


def check_for_app_update() -> Dict[str, object]:
    checked_at = datetime.now(timezone.utc).isoformat()
    repo = _repo()
    base = {
        "configured": repo is not None,
        "installed": APP_VERSION,
        "latest": None,
        "update_available": False,
        "repo": repo,
        "release_notes": None,
        "release_url": None,
            "download_url": None,
            "installer_url": None,
        "published_at": None,
        "error": None,
        "checked_at": checked_at,
    }
    if repo is None:
        return base
    try:
        rel = gh.get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    except Exception as exc:
        base["error"] = f"Couldn't reach GitHub: {exc}"
        base["release_url"] = f"https://github.com/{repo}/releases"
        return base

    tag = (rel.get("tag_name") or "").strip()
    latest = tag[1:] if tag[:1].lower() == "v" else tag
    base.update(
        {
            "latest": latest or None,
            "update_available": gh.is_newer(latest, APP_VERSION),
            "release_notes": rel.get("body") or None,
            "release_url": rel.get("html_url") or f"https://github.com/{repo}/releases",
            "download_url": _installer_asset(rel) if is_frozen() else _wheel_asset(rel),
            "installer_url": _installer_asset(rel),
            "published_at": rel.get("published_at"),
        }
    )
    return base


# --- install -------------------------------------------------------------------------

def get_status() -> Dict[str, object]:
    with _lock:
        return dict(_state)


def _editable_install() -> bool:
    """True when the app is installed in editable/dev mode (``pip install -e``)."""
    try:
        text = metadata.distribution(APP_PACKAGE).read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return False
    except Exception:
        return False
    if not text:
        return False
    import json

    try:
        return bool(json.loads(text).get("dir_info", {}).get("editable"))
    except Exception:
        return False


def _packaged() -> bool:
    try:
        metadata.version(APP_PACKAGE)
        return True
    except metadata.PackageNotFoundError:
        return False


def start_app_update(download_url: Optional[str]) -> Dict[str, object]:
    """Kick off the update in a daemon thread."""
    with _lock:
        if _state["state"] == "running":
            return dict(_state)

    if is_frozen():
        if not download_url:
            return _fail("This release has no Windows Setup.exe attached yet.")
        with _lock:
            _state.update(
                {
                    "state": "running",
                    "message": "Downloading the installer...",
                    "output": None,
                    "old_version": APP_VERSION,
                    "new_version": None,
                    "restart_required": False,
                }
            )
        threading.Thread(target=_run_installer_update, args=(download_url,), daemon=True).start()
        return get_status()

    if not download_url:
        return _fail("This release has no installable wheel attached yet.")
    if not _packaged():
        return _fail(
            "This copy isn't installed as a package, so it can't self-update. "
            "Update it the way it was installed (e.g. git pull), or use a packaged release."
        )
    if _editable_install():
        return _fail("You're on a development checkout — update with git instead of pip.")

    with _lock:
        _state.update(
            {
                "state": "running",
                "message": "Downloading and installing the update…",
                "output": None,
                "old_version": APP_VERSION,
                "new_version": None,
                "restart_required": False,
            }
        )
    threading.Thread(target=_run_install, args=(download_url,), daemon=True).start()
    return get_status()


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _fail(message: str) -> Dict[str, object]:
    with _lock:
        _state.update(
            {"state": "error", "message": message, "output": None,
             "old_version": APP_VERSION, "new_version": None, "restart_required": False}
        )
    return get_status()


def _installed_dist_version() -> Optional[str]:
    """Read the freshly-installed dist version from a child interpreter (this process's
    metadata cache is stale until restart)."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c",
             f"import importlib.metadata as m; print(m.version('{APP_PACKAGE}'))"],
            capture_output=True, text=True, timeout=30,
        )
        return proc.stdout.strip() or None
    except Exception:
        return None


def _run_install(download_url: str) -> None:
    cmd: List[str] = [
        sys.executable, "-m", "pip", "install", "--upgrade",
        "--upgrade-strategy", "only-if-needed", download_url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
        ok = proc.returncode == 0
        with _lock:
            _state.update(
                {
                    "state": "success" if ok else "error",
                    "message": (
                        "Update installed. Restart Omnivert to finish."
                        if ok
                        else "Update failed — see details below."
                    ),
                    "output": output[-8000:],
                    "new_version": _installed_dist_version() if ok else APP_VERSION,
                    "restart_required": ok,
                }
            )
    except subprocess.TimeoutExpired:
        with _lock:
            _state.update({"state": "error", "message": "Update timed out after 15 minutes.",
                           "output": None, "restart_required": False})
    except Exception as exc:  # noqa: BLE001 - reported to the UI
        with _lock:
            _state.update({"state": "error", "message": f"Update failed: {exc}",
                           "output": None, "restart_required": False})


def _run_installer_update(download_url: str) -> None:
    try:
        installer_path = installer_update.download_installer(download_url)
        installer_update.launch_installer(installer_path)
        with _lock:
            _state.update(
                {
                    "state": "success",
                    "message": (
                        "Installer launched. Close Omnivert if Windows does not "
                        "close it automatically."
                    ),
                    "output": str(installer_path),
                    "new_version": None,
                    "restart_required": True,
                }
            )
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI
        with _lock:
            _state.update(
                {
                    "state": "error",
                    "message": f"Installer update failed: {exc}",
                    "output": None,
                    "restart_required": False,
                }
            )
