"""Pin the bundled conversion engine version in pyproject.toml."""

from __future__ import annotations

import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: python scripts/pin_engine_version.py 0.1.6")

version = sys.argv[1].lstrip("v")
root = Path(__file__).resolve().parents[1]
pyproject = root / "pyproject.toml"
text = pyproject.read_text(encoding="utf-8")
updated = re.sub(
    r'markitdown\[([^\]]+)\]==[^"]+',
    rf"markitdown[\1]=={version}",
    text,
)
if updated == text:
    raise SystemExit("Could not update conversion engine dependency pin.")
pyproject.write_text(updated, encoding="utf-8")
print(version)
