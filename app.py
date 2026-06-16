"""Compatibility launcher.

Prefer ``python -m omnivert`` from the app root. This shim remains so older
shortcuts or notes that call ``app.py`` still launch the packaged backend.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from omnivert.launcher import main

raise SystemExit(main())

