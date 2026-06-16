# CLAUDE.md

This file provides guidance to Claude Code, Codex, and other coding agents when working
in this repository.

## What This Repository Is

Omnivert is a Windows desktop GUI for a bundled conversion engine. The app
uses a FastAPI backend, a React/Vite frontend, and pywebview for the native desktop
window. The packaged Windows distribution is a PyInstaller onedir build wrapped by an
Inno Setup `Setup.exe`. The current private GitHub release repo is `BrandonDry/Omnivert`.

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
  approval gate (no paid review tooling; the private repo can't use Environments/GHAS for free).
- App update checks run at launch **and** re-run in-session (~24h timer + on window focus,
  throttled to once/hour), so a long-running window learns about a release without a restart.
  `auto_check_updates` and `skipped_app_version` still gate/suppress prompts.
- Release notes embed the bundled MarkItDown changelog (`scripts/compose_release_notes.py`),
  and the in-app update dialog shows the bundled "engine X → Y" delta.
- `tests/engine_smoke.py` (the auto-bump gate) covers txt/csv/html **and** pdf/docx/pptx/xlsx,
  with fixtures generated in-process (no committed binaries — avoids Proton dehydration).

## Handoff

Read `PHASES.md` for the detailed phase history, current status, kickoff lines, and the
latest Phase 8 verification record.

Current handoff as of June 16, 2026:

- The app rename is mostly complete. The source package, distribution name, console script,
  frontend surfaces, docs, scripts, workflows, PyInstaller/Inno metadata, settings path, temp
  prefixes, and installer asset names use Omnivert. Keep `markitdown` / `MarkItDown` only where
  it is the upstream Microsoft conversion engine package/API, usually imported as
  `from markitdown import MarkItDown as Engine`.
- The app folder has been renamed to `omnivert-app`, and the outer wrapper folder has now been
  renamed to `Omnivert` (done June 16, 2026 by the user). The live workspace is rooted at
  `D:\Proton Drive\My files\Documents\AI Projects\Omnivert`. The full rename is complete; no
  stale `Microsoft Markitdown` path references remain in the docs.
- **Rename side effect fixed (June 16, 2026):** the `.venv` was repaired *in place* while the
  workspace was still named `Microsoft Markitdown`, so uv baked that old absolute path into
  every console-script `.exe` trampoline (`markitdown.exe`, `pip.exe`, `uvicorn.exe`, etc.) and
  the `.py` script shebangs. After the folder rename those shims failed with
  `uv trampoline failed to canonicalize script path` (the app itself was unaffected — it launches
  via `python -m omnivert` / `python -m uvicorn`, and `python.exe`/`pythonw.exe` are venv
  launchers, not uv trampolines). Fixed by re-running the documented curated reinstall from the
  new path (regenerates all trampolines/shebangs), then re-pinning `pydantic<2.14`. Verified:
  `markitdown.exe`, `pip.exe`, `uvicorn.exe` work and a CSV→Markdown convert succeeds; no
  `Microsoft Markitdown` strings remain anywhere in `.venv`. `fastapi.exe` "fails" only because
  the optional `fastapi[standard]` extra isn't installed (expected — the app uses
  `uvicorn[standard]`, not the fastapi CLI). **Lesson: if the venv is ever repaired/created at one
  path and the folder is later renamed/moved, re-run the reinstall to rebuild the trampolines.**
- Post-rename static scans passed for stale app identifiers:
  `markitdown-app`, `MarkItDown Studio`, `MarkItDownStudio`, `markitdown_studio`,
  `markitdown-studio`, `check_latest_markitdown`, `pin_markitdown_version`, and
  `markitdown_version`.
- Local checks that passed after the rename: `python -m compileall src`,
  `npm run lint --prefix frontend`, `npm run build --prefix frontend`, and
  `python scripts/copy_web_assets.py`. Git ignore coverage includes `frontend/node_modules`,
  `frontend/dist`, `src/omnivert/web`, `build`, `dist`, `.pip-cache`, `.uv-cache`, and egg-info.
- **Venv repaired (June 16, 2026).** The corruption was caused by Proton Drive dehydrating files
  into cloud placeholders (this workspace lives inside Proton Drive). Repaired in place — no
  second env — with
  `uv pip install --python .venv\Scripts\python.exe --prerelease=allow --reinstall pip fastapi "uvicorn[standard]" python-multipart trio pywebview "markitdown[pptx,docx,xlsx,xls,pdf,outlook,az-doc-intel,az-content-understanding,audio-transcription]==0.1.6"`,
  then `uv pip install --python .venv\Scripts\python.exe "pydantic<2.14"` to undo the pydantic
  alpha that `--prerelease=allow` (required only by `azure-ai-contentunderstanding>=1.2.0b1`)
  had pulled in. `pip`, `trio`, and the engine all import cleanly afterward.
- **Full Phase 8 smoke pass (June 16, 2026)** after the repair: `python -m compileall src`,
  `omnivert.main`/`omnivert.launcher` imports, `tests/engine_smoke.py`, Uvicorn boot,
  `/api/health`, `/api/app/version`, `/api/capabilities`, `/api/plugins`, `/api/convert/text`,
  multipart `/api/convert/file`, frontend lint + build, `scripts/copy_web_assets.py`, and a
  clean wheel (28 entries, 0 `markitdown_studio` entries, only current `omnivert/web` assets).
- **Wheel build note:** clean the ignored `build\` cache and any stale `dist\markitdown_studio-*.whl`
  first, then use the documented `pip wheel --no-deps --no-build-isolation . -w dist\wheel-check`.
  Proton may hold a placeholder lock on a previously-built `dist\wheel-check\*.whl` (access
  denied to delete); build into a fresh dir (e.g. `dist\wheel-verify\`) and delete the stale one
  manually once Proton releases it. Both dirs are gitignored.
- **Windows build chain validated (June 16, 2026).** PyInstaller freeze →
  `dist\Omnivert\Omnivert.exe`; Inno Setup 6 compile → `dist\installer\Omnivert-Setup-0.1.0.exe`;
  silent install (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`) →
  `%LOCALAPPDATA%\Programs\Omnivert\Omnivert.exe` + Start-Menu shortcut; installed app boots,
  serves `/api`, reports `frozen:true` + `engine_version:0.1.6`, and converts a CSV to a
  Markdown table. Two `packaging/app.spec` fixes were needed (now in place): (1) `ROOT` was off
  by one level (`Path(SPECPATH).parent.parent` → `.parent`) — the extra `.parent` pointed at the
  outer `Omnivert\` wrapper and broke the freeze with "freeze_entry.py not found"; (2) added
  `copy_metadata("markitdown", recursive=True)` + an explicit `copy_metadata` list for the
  `_OPTIONAL_DEPS` in `capabilities.py` so `importlib.metadata.version(...)` works frozen and the
  Capabilities dialog shows engine/dep versions. Inno Setup installed via
  `winget install --id JRSoftware.InnoSetup` (ISCC landed at
  `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`, not Program Files).
- **Update-over-install validated (June 16, 2026):** a 0.1.1 installer run silently over the
  installed 0.1.0 upgraded **in place** (Windows Uninstall version 0.1.0 → 0.1.1, single entry,
  no side-by-side); upgraded app booted + converted. Repo reverted to 0.1.0 afterward.
- **Published to GitHub (June 16, 2026):** initial commit on `main` of `BrandonDry/Omnivert`
  (private), plus Release **v0.1.0** with `Omnivert-Setup-0.1.0.exe` attached
  (https://github.com/BrandonDry/Omnivert/releases/tag/v0.1.0). The repo's branch is `main`.
- **CI workflows are live (corrected June 16, 2026).** The earlier "workflows not pushed / no
  `workflow` scope" note is **stale**: the `gh` token now has `workflow`, all three workflows
  (`release.yml`, `engine-watch.yml`, `engine-update.yml`) are `active` on `BrandonDry/Omnivert`,
  and `v0.1.0` is released with `Omnivert-Setup-0.1.0.exe`. The only unvalidated item is a real
  end-to-end CI run of the engine-bump → draft-release chain (no markitdown bump has occurred
  since; PyPI `0.1.6` == the pin).
- **Update-pipeline hardening (June 16, 2026).** `engine-update.yml` → `release.yml` now builds
  a **draft** release (maintainer Publish = approval gate); `scripts/check_latest_engine.py`
  uses `packaging.version` and skips pre-releases; `engine-watch.yml` installs `packaging` and
  skips dispatch when a `bot/conversion-engine-v<ver>` PR is already open; `release.yml` composes
  notes via `scripts/compose_release_notes.py`; `engine_smoke.py` covers binary formats; the
  frontend re-checks for updates in-session and shows the bundled engine delta.
