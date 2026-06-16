"""Patch build-time release repo metadata."""

from __future__ import annotations

import sys
from pathlib import Path

if len(sys.argv) != 2 or sys.argv[1].count("/") != 1:
    raise SystemExit("Usage: python scripts/set_build_repo.py owner/repo")

target = Path(__file__).resolve().parents[1] / "src" / "omnivert" / "build_info.py"
target.write_text(
    '"""Build-time metadata patched by release workflows."""\n\n'
    f'DEFAULT_APP_REPO = "{sys.argv[1]}"\n',
    encoding="utf-8",
)
print(f"Set DEFAULT_APP_REPO={sys.argv[1]}")

