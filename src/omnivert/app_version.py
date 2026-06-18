"""Single source of truth for the Omnivert app version.

Bump ``__version__`` and tag a matching ``vX.Y.Z`` GitHub Release to ship an update (see
RELEASING.md). ``pyproject.toml`` reads ``__version__`` dynamically so the built wheel's
version always matches what the running app reports at ``GET /api/app/version``.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

__version__ = "0.1.3"

# Repo root = the app dir; ..\.venv lives outside it in the working wrapper.
_APP_DIR = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def git_commit() -> str | None:
    """Best-effort short commit SHA when running from a git checkout (else None)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(_APP_DIR), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return proc.stdout.strip() or None if proc.returncode == 0 else None
    except Exception:
        return None
