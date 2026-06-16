"""Copy the Vite production build into the Python package."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / "frontend" / "dist"
PACKAGE_WEB = ROOT / "src" / "omnivert" / "web"

if not (FRONTEND_DIST / "index.html").is_file():
    raise SystemExit("frontend/dist/index.html is missing. Run npm run build first.")

if PACKAGE_WEB.exists():
    shutil.rmtree(PACKAGE_WEB)
shutil.copytree(FRONTEND_DIST, PACKAGE_WEB)
print(f"Copied {FRONTEND_DIST} -> {PACKAGE_WEB}")

