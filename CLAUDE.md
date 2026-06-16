# CLAUDE.md

This file provides guidance to Claude Code, Codex, and other coding agents when working
in this repository.

## What This Repository Is

Omnivert is a Windows desktop GUI for a bundled conversion engine. The app
uses a FastAPI backend, a React/Vite frontend, and pywebview for the native desktop
window. The packaged Windows distribution is a PyInstaller onedir build wrapped by an
Inno Setup `Setup.exe`. The GitHub release repo is `BrandonDry/Omnivert`.

## Environment

- Primary dev OS: Windows 11 / PowerShell.
- Local wrapper workspace keeps the virtual environment at `..\.venv\`.
- From this repo root, run Python commands with `..\.venv\Scripts\python.exe` if using
  the existing local environment, or install the package into another environment with
  `python -m pip install -e .`.
- The conversion engine is pinned in `pyproject.toml` with curated extras. Do not use
  `markitdown[all]`; the YouTube extra has Python-version caveats.

## Common Commands

```powershell
# Build frontend and copy it into the Python package
build.bat

# Launch desktop app from the local wrapper venv
run.bat

# Backend dev server
$env:PYTHONPATH="$PWD\src"
..\.venv\Scripts\python.exe -m uvicorn omnivert.main:app --app-dir src --port 8765

# Frontend dev server
npm run dev --prefix frontend

# Checks
npm run build --prefix frontend
npm run lint --prefix frontend
..\.venv\Scripts\python.exe -m compileall src
$env:PYTHONPATH="$PWD\src"; ..\.venv\Scripts\python.exe tests\engine_smoke.py
$env:PIP_CACHE_DIR="$PWD\.pip-cache"; ..\.venv\Scripts\python.exe -m pip wheel --no-deps --no-build-isolation . -w dist\wheel-check
```

## Architecture

- `src/omnivert/main.py`: FastAPI routes and static frontend mount.
- `src/omnivert/launcher.py`: pywebview desktop launcher.
- `src/omnivert/conversion.py`: conversion engine service wrapper.
- `src/omnivert/updates.py`: conversion engine update check/apply.
- `src/omnivert/app_updates.py`: Omnivert app update check/apply.
- `src/omnivert/installer_update.py`: frozen Windows installer-update path.
- `src/omnivert/build_info.py`: build-time GitHub repo metadata.
- `frontend/`: React/Vite UI.
- `packaging/`: PyInstaller and Inno Setup files.
- `.github/workflows/`: release and automated engine update workflows.

## Licensing

- Omnivert's own code is **Apache License 2.0** (`LICENSE`), Copyright 2026 BrandonDry.
  `pyproject.toml` declares `license = "Apache-2.0"` (PEP 639 SPDX, needs setuptools>=77)
  and `license-files = ["LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"]`, so the built wheel
  carries all three under `dist-info/licenses/`.
- The bundled **Microsoft MarkItDown** engine is MIT (Copyright (c) Microsoft Corporation).
  Its full MIT text is reproduced verbatim in `THIRD_PARTY_NOTICES.md`; `NOTICE` summarizes
  the attribution. Keep these in sync if the engine is swapped/updated.
- Attribution is surfaced in three places: `README.md` (Credits + License sections), the
  in-app **Capabilities** dialog footer (`frontend/src/components/CapabilitiesDialog.tsx`),
  and the bundled notice files. The frozen build ships LICENSE/NOTICE/THIRD_PARTY_NOTICES.md
  (added to `packaging/app.spec` datas), and the Inno installer shows `LICENSE` via
  `LicenseFile` (`packaging/installer.iss`).
- Omnivert is an independent project, not affiliated with/endorsed by Microsoft — keep that
  disclaimer wherever MarkItDown/Microsoft are named.

## Update Model

- Dev/venv mode can pip-update the conversion engine and pip-install app wheels.
- Frozen Windows builds cannot pip-update. App updates download and run the newer
  `Setup.exe`; conversion engine updates are bundled into new app releases.
- The app still checks PyPI/GitHub for newer conversion engine versions in frozen mode,
  but it disables direct engine apply and tells users to install the next Omnivert release.
- GitHub automation watches PyPI for a newer **stable** conversion engine (pre-releases are
  skipped), pins it, runs smoke checks, then builds a **draft** GitHub Release. Users are only
  prompted once a maintainer clicks **Publish** on the draft — that publish is the human
  approval gate.
- App update checks run at launch **and** re-run in-session (~24h timer + on window focus,
  throttled to once/hour), so a long-running window learns about a release without a restart.
  `auto_check_updates` and `skipped_app_version` still gate/suppress prompts.
- Release notes embed the bundled MarkItDown changelog (`scripts/compose_release_notes.py`),
  and the in-app update dialog shows the bundled "engine X → Y" delta.
- `tests/engine_smoke.py` (the auto-bump gate) covers txt/csv/html **and** pdf/docx/pptx/xlsx,
  with fixtures generated in-process (no committed binaries).

## Handoff

Read `PHASES.md` for the detailed phase history, current status, and kickoff lines.

### Naming conventions

- The source package, distribution name, console script, frontend surfaces, docs, scripts,
  workflows, PyInstaller/Inno metadata, settings path, and installer asset names use
  **Omnivert**. Keep `markitdown` / `MarkItDown` only where it refers to the upstream
  Microsoft conversion engine package/API, usually imported as
  `from markitdown import MarkItDown as Engine`.

### Build / packaging gotchas (durable)

- **Curated engine extras only.** The conversion engine is pinned in `pyproject.toml` with a
  curated extras list, **not** `markitdown[all]` (the YouTube extra has Python-version
  caveats). If you need to repair/reinstall the environment, reinstall the same curated
  extras pin. `azure-ai-contentunderstanding` may pull a pydantic pre-release if prereleases
  are allowed — pin `pydantic<2.14` back to stable afterward.
- **`packaging/app.spec` — two fixes are in place; don't regress them:**
  1. `ROOT` is `Path(SPECPATH).parent` (the spec lives in `packaging/`, so its parent is the
     repo root). An extra `.parent` climbs out of the repo and breaks the freeze with
     *"script freeze_entry.py not found"*.
  2. The spec calls `copy_metadata("markitdown", recursive=True)` plus an explicit
     `copy_metadata` list for the optional deps in `_OPTIONAL_DEPS`
     (`src/omnivert/capabilities.py`). Without this, frozen builds return `None` from
     `importlib.metadata.version(...)` and the Capabilities dialog shows no versions. Keep
     the two lists in sync.
- **Wheel build:** clean the ignored `build\` cache first, then use
  `pip wheel --no-deps --no-build-isolation . -w dist\wheel-check`
  (with a repo-local `PIP_CACHE_DIR`). Prefer this over `python -m build` when a generated
  `build\` directory exists.
- **Inno Setup** is provided by `JRSoftware.InnoSetup` (`ISCC.exe`). Per-user installs may
  land it under `%LOCALAPPDATA%\Programs\Inno Setup 6\`, not `Program Files`.

### Validated build/release chain

The Windows build chain has been validated end-to-end: PyInstaller freeze →
`dist\Omnivert\Omnivert.exe`; Inno Setup compile → `dist\installer\Omnivert-Setup-<ver>.exe`;
silent per-user install (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`) →
`%LOCALAPPDATA%\Programs\Omnivert\`; installed app boots, serves `/api`, reports
`frozen:true`, and converts files. Update-over-install upgrades in place (single Uninstall
entry, no side-by-side). All three workflows (`release.yml`, `engine-watch.yml`,
`engine-update.yml`) are active on `BrandonDry/Omnivert`.

### Update-pipeline notes

`engine-update.yml` → `release.yml` builds a **draft** release (maintainer Publish = the
approval gate); `scripts/check_latest_engine.py` uses `packaging.version` and skips
pre-releases; `engine-watch.yml` skips dispatch when a `bot/conversion-engine-v<ver>` PR is
already open; `release.yml` composes notes via `scripts/compose_release_notes.py`; the
frontend re-checks for updates in-session and shows the bundled engine delta.

### Environment caveat

If Python imports start failing for files that clearly exist (missing submodules, broken
console-script trampolines), suspect a file-sync/placeholder layer (e.g. cloud-synced
folders that dehydrate files on disk) and reinstall the curated dependencies before
debugging further.
