"""Report whether PyPI has a newer conversion engine release than pyproject.toml pins."""

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
    latest = json.loads(response.read().decode("utf-8"))["info"]["version"]

def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", value)[:4])

update_available = version_tuple(latest) > version_tuple(current)
print(f"current={current}")
print(f"latest={latest}")
print(f"update_available={str(update_available).lower()}")

github_output = os.environ.get("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a", encoding="utf-8") as handle:
        handle.write(f"current={current}\n")
        handle.write(f"latest={latest}\n")
        handle.write(f"update_available={str(update_available).lower()}\n")
