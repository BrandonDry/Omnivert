"""Tiny shared helpers for the PyPI / GitHub-backed updaters.

Both ``updates.py`` (conversion engine, from PyPI) and ``app_updates.py`` (this app, from
GitHub Releases) need to fetch JSON and compare versions, so those live here to avoid
duplication. Network calls are deliberately stdlib-only (``urllib``) so the updaters add no
dependencies, and every caller is expected to handle failures rather than have these raise
into a request.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Optional

USER_AGENT = "Omnivert-Updater"
TIMEOUT = 10  # seconds per network call


def get_json(url: str):
    """GET ``url`` and parse the JSON body. Raises on network/parse errors."""
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_newer(latest: Optional[str], current: Optional[str]) -> bool:
    """True when ``latest`` is a strictly newer version than ``current``."""
    if not latest or not current:
        return False
    try:
        from packaging.version import Version

        return Version(latest) > Version(current)
    except Exception:
        return latest != current  # best-effort fallback if packaging is unavailable
