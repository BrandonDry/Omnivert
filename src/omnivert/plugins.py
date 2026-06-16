"""List installed third-party converter plugins (entry-point group 'markitdown.plugin')."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import List

from .schemas import PluginInfo


def list_plugins() -> List[PluginInfo]:
    found: List[PluginInfo] = []
    try:
        eps = entry_points(group="markitdown.plugin")
    except TypeError:  # pragma: no cover - very old importlib.metadata
        eps = entry_points().get("markitdown.plugin", [])  # type: ignore[attr-defined]
    for ep in eps:
        found.append(PluginInfo(name=ep.name, value=ep.value))
    return found
