"""Bump Omnivert's patch version."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "omnivert" / "app_version.py"

text = VERSION_FILE.read_text(encoding="utf-8")
match = re.search(r'__version__ = "(\d+)\.(\d+)\.(\d+)"', text)
if not match:
    raise SystemExit("Could not find __version__.")

if len(sys.argv) == 2:
    new_version = sys.argv[1].lstrip("v")
else:
    major, minor, patch = map(int, match.groups())
    new_version = f"{major}.{minor}.{patch + 1}"

updated = re.sub(r'__version__ = "\d+\.\d+\.\d+"', f'__version__ = "{new_version}"', text)
VERSION_FILE.write_text(updated, encoding="utf-8")
print(new_version)

