"""Check for and install conversion engine updates from PyPI.

Omnivert pins the conversion engine to a curated set of extras — **never** ``[all]``, which can't
resolve on Python 3.14 (its ``youtube-transcript-api~=1.0.0`` pin has no 3.14 wheel).
``check_for_updates`` compares the installed version against the latest release on PyPI
(the authoritative source for what pip would install) and attaches GitHub release notes
for review. ``start_update`` shells out to *this* interpreter's pip in a background
thread the UI polls; a restart is required afterwards because the running process has
already imported the old ``markitdown``.

Everything here is best-effort and network-tolerant: failures surface as a structured
``error`` string rather than raising, so the UI degrades gracefully when offline.
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from importlib import metadata
from typing import Dict, List, Optional

from . import gh

# Accept only a PEP 440-style release version (optional pre/post/dev suffix). The pip spec
# is built from this, so reject anything that could smuggle extra markers/options.
_VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+)*((a|b|rc)[0-9]+)?(\.post[0-9]+)?(\.dev[0-9]+)?$")

PACKAGE = "markitdown"
# Mirror the documented install (see CLAUDE.md). Keep in sync; never add "all" here.
EXTRAS: List[str] = [
    "pptx",
    "docx",
    "xlsx",
    "xls",
    "pdf",
    "outlook",
    "az-doc-intel",
    "az-content-understanding",
    "audio-transcription",
]

PYPI_URL = f"https://pypi.org/pypi/{PACKAGE}/json"
GITHUB_RELEASES_URL = "https://api.github.com/repos/microsoft/markitdown/releases"
GITHUB_RELEASES_PAGE = "https://github.com/microsoft/markitdown/releases"

# Background-install state, guarded by a lock (the worker runs off-request).
_lock = threading.Lock()
_state: Dict[str, object] = {
    "state": "idle",  # idle | running | success | error
    "message": None,
    "output": None,
    "old_version": None,
    "new_version": None,
    "restart_required": False,
}


# --- version helpers -----------------------------------------------------------------

def installed_version() -> Optional[str]:
    try:
        return metadata.version(PACKAGE)
    except metadata.PackageNotFoundError:
        return None


def _query_installed_version() -> Optional[str]:
    """Read the version from a *fresh* interpreter so it reflects a just-finished
    install (this process's importlib metadata cache may still be stale)."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c",
             "import importlib.metadata as m; print(m.version('markitdown'))"],
            capture_output=True, text=True, timeout=30,
        )
        return proc.stdout.strip() or None
    except Exception:
        return installed_version()


# --- network -------------------------------------------------------------------------

def _github_notes(version: str) -> Dict[str, Optional[str]]:
    """Find the GitHub release whose tag matches ``version``. microsoft/markitdown is a
    monorepo, so tags look like ``markitdown-0.1.6`` rather than ``v0.1.6`` — match on a
    substring and fall back to just linking the releases page."""
    fallback = {"release_notes": None, "release_url": GITHUB_RELEASES_PAGE, "published_at": None}
    try:
        releases = gh.get_json(GITHUB_RELEASES_URL)
    except Exception:
        return fallback
    if isinstance(releases, list):
        for rel in releases:
            if version in (rel.get("tag_name") or ""):
                return {
                    "release_notes": rel.get("body") or None,
                    "release_url": rel.get("html_url") or GITHUB_RELEASES_PAGE,
                    "published_at": rel.get("published_at"),
                }
    return fallback


def check_for_updates() -> Dict[str, object]:
    current = installed_version()
    checked_at = datetime.now(timezone.utc).isoformat()
    frozen = is_frozen()
    try:
        pypi = gh.get_json(PYPI_URL)
        latest = pypi["info"]["version"]
    except Exception as exc:
        return {
            "installed": current,
            "latest": None,
            "update_available": False,
            "channel": "bundled" if frozen else "pypi",
            "release_notes": None,
            "release_url": GITHUB_RELEASES_PAGE,
            "published_at": None,
            "error": f"Couldn't reach PyPI: {exc}",
            "checked_at": checked_at,
            "can_apply": False,
            "apply_note": (
                "The conversion engine is bundled with this Windows app."
                if frozen
                else None
            ),
        }
    notes = _github_notes(str(latest))
    return {
        "installed": current,
        "latest": latest,
        "update_available": gh.is_newer(str(latest), current),
        "channel": "bundled" if frozen else "pypi",
        "error": None,
        "checked_at": checked_at,
        "can_apply": not frozen,
        "apply_note": (
            "The conversion engine is bundled with this Windows app. "
            "Install the next Omnivert release to get the newer engine."
            if frozen
            else None
        ),
        **notes,
    }


# --- install -------------------------------------------------------------------------

def get_status() -> Dict[str, object]:
    with _lock:
        return dict(_state)


def start_update(version: Optional[str]) -> Dict[str, object]:
    """Kick off the upgrade in a daemon thread (no-op if one is already running)."""
    if is_frozen():
        return _fail(
            "The conversion engine is bundled with this Windows app. "
            "Install the next Omnivert release to get a newer engine."
        )
    if version is not None and not _VERSION_RE.match(version):
        return _fail(f"Refusing to install an invalid engine version: {version!r}")
    with _lock:
        if _state["state"] == "running":
            return dict(_state)
        _state.update(
            {
                "state": "running",
                "message": "Installing update… this can take a minute.",
                "output": None,
                "old_version": installed_version(),
                "new_version": None,
                "restart_required": False,
            }
        )
    threading.Thread(target=_run_install, args=(version,), daemon=True).start()
    return get_status()


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _fail(message: str) -> Dict[str, object]:
    with _lock:
        _state.update(
            {
                "state": "error",
                "message": message,
                "output": None,
                "old_version": installed_version(),
                "new_version": installed_version(),
                "restart_required": False,
            }
        )
    return get_status()


def _requirement(version: Optional[str]) -> str:
    spec = f"{PACKAGE}[{','.join(EXTRAS)}]"
    return f"{spec}=={version}" if version else spec


def _run_install(version: Optional[str]) -> None:
    # only-if-needed (pip's default since 20.3) avoids churning transitive deps that the
    # new markitdown doesn't actually require.
    cmd = [
        sys.executable, "-m", "pip", "install", "--upgrade",
        "--upgrade-strategy", "only-if-needed", _requirement(version),
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
                    "new_version": _query_installed_version() if ok else installed_version(),
                    "restart_required": ok,
                }
            )
    except subprocess.TimeoutExpired:
        with _lock:
            _state.update(
                {"state": "error", "message": "Update timed out after 15 minutes.",
                 "output": None, "restart_required": False}
            )
    except Exception as exc:  # noqa: BLE001 - reported to the UI
        with _lock:
            _state.update(
                {"state": "error", "message": f"Update failed: {exc}",
                 "output": None, "restart_required": False}
            )
