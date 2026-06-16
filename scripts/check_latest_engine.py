"""Report whether PyPI has a newer *stable* conversion engine release than pyproject.toml pins.

Uses PEP 440 parsing (``packaging.version``) so comparisons are correct and pre-releases are
skipped — an auto-bump must never ship a markitdown alpha/beta to users. The latest stable is
chosen from PyPI's full release list rather than ``info.version`` (which can point at a
pre-release). Falls back to a digit-tuple compare only if ``packaging`` is somehow unavailable.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
match = re.search(r'markitdown\[[^\]]+\]==([^"]+)', text)
if not match:
    raise SystemExit("Could not find pinned conversion engine version.")

current = match.group(1)
with urllib.request.urlopen("https://pypi.org/pypi/markitdown/json", timeout=60) as response:
    data = json.loads(response.read().decode("utf-8"))

releases = data.get("releases") or {}
info_version = data["info"]["version"]


def _digit_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", value)[:4])


try:
    from packaging.version import InvalidVersion, Version

    def _is_stable(value: str) -> bool:
        try:
            v = Version(value)
        except InvalidVersion:
            return False
        return not (v.is_prerelease or v.is_devrelease)

    def _not_fully_yanked(files: object) -> bool:
        # A version with no files, or every file yanked, isn't installable.
        if not isinstance(files, list) or not files:
            return False
        return any(not f.get("yanked", False) for f in files)

    stable = [v for v, files in releases.items() if _is_stable(v) and _not_fully_yanked(files)]
    latest = max(stable, key=Version) if stable else info_version
    update_available = Version(latest) > Version(current)
except Exception:  # pragma: no cover - packaging should always be present in CI
    latest = info_version
    update_available = _digit_tuple(latest) > _digit_tuple(current)

print(f"current={current}")
print(f"latest={latest}")
print(f"update_available={str(update_available).lower()}")

github_output = os.environ.get("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a", encoding="utf-8") as handle:
        handle.write(f"current={current}\n")
        handle.write(f"latest={latest}\n")
        handle.write(f"update_available={str(update_available).lower()}\n")
