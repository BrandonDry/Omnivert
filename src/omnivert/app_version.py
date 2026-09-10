"""Single source of truth for the Omnivert app version.

Bump ``__version__`` and tag a matching ``vX.Y.Z`` GitHub Release to ship an update (see
RELEASING.md). ``pyproject.toml`` reads ``__version__`` dynamically so the built wheel's
version always matches what the running app reports at ``GET /api/app/version``.
"""

from __future__ import annotations

import subprocess
import sys
from functools import lru_cache
from pathlib import Path

__version__ = "0.1.7"

# Repo root = the app dir; ..\.venv lives outside it in the working wrapper.
_APP_DIR = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def git_commit() -> str | None:
    """Best-effort short commit SHA when running from a git checkout (else None).

    A frozen build returns None without spawning anything. Its ``__file__`` points inside
    the bundle, so any SHA it found would belong to whatever repository happened to sit
    above the extraction directory (measured: a build made inside the checkout reported the
    checkout's HEAD), and a windowed PyInstaller app spawning a console process risks a
    console window flashing on the user's screen for an answer that was wrong anyway.
    """
    if getattr(sys, "frozen", False):
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(_APP_DIR), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return proc.stdout.strip() or None if proc.returncode == 0 else None
    except Exception:
        return None
