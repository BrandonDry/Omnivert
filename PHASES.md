# Omnivert — Build Phases (handoff doc)

> Purpose: a self-contained, detailed phase breakdown to feed future chats. Start each new chat
> by telling it to read **`CLAUDE.md`** (repo root) and **this file**, then quote the "Kickoff
> line" for the phase you want. Always re-verify the status table against the live code first —
> chats may have advanced the build.

## Project snapshot
- **What:** A native desktop app that exposes the full conversion engine feature surface
  (file/URL/text → Markdown) through a polished GUI, so no terminal is needed.
- **Stack:** FastAPI + Uvicorn backend (runs in the repo's existing `..\.venv`, imports
  `markitdown` directly) · React + Vite + TypeScript + Tailwind v4 + shadcn/ui frontend
  (`react-markdown` + `remark-gfm`, `sonner`, `lucide-react`) · packaged as a native window
  via **pywebview** (`src/omnivert/launcher.py`; `app.py` is a compatibility shim).
- **Key conventions:**
  - Dev backend on **port 8765**; Vite dev server proxies `/api` → `127.0.0.1:8765`.
    Production: the package serves copied `src/omnivert/web` assets and the API on one port.
  - Frontend calls **relative `/api/...`** paths (works in both dev and prod).
  - Reuse the existing `.venv` — do **not** create a second Python env.
  - Settings + secrets live in `%LOCALAPPDATA%\Omnivert\settings.json`, **redacted**
    on read (`__REDACTED__` + `has_<field>` booleans), preserved when the UI sends blanks or
    `__REDACTED__`, never logged; gitignored.
  - Windows installs are per-user under `%LOCALAPPDATA%\Programs\Omnivert`. Omnivert has its
    own Inno AppId and does not migrate previous app installs/settings.
  - **YouTube** URLs may work (leftover `youtube-transcript-api 1.2.4`) even though the
    `youtube-transcription` extra can't pip-install on Python 3.14. **ffmpeg** is absent, so
    non-WAV audio surfaces a non-fatal warning the UI should show.

## File map
```
omnivert-app/
  app.py              # compatibility shim -> omnivert.launcher
  run.bat / build.bat # launch / (npm install + build -> frontend/dist -> package web/)
  pyproject.toml      # package metadata + conversion engine pin
  src/omnivert/
    launcher.py       # pywebview launcher: free port (pref 8765), uvicorn daemon thread, window
    main.py           # FastAPI routes + CORS(dev) + static mount of frontend/dist
    conversion.py     # ConversionService: builds engine instances, StreamInfo, warning capture, error mapping, cloud gates
    capabilities.py   # version, optional-dep detection, ffmpeg/youtube checks, format table
    plugins.py        # entry_points(group="markitdown.plugin")
    settings.py       # load/save JSON, SECRET_FIELDS redaction, DEFAULT_CLAUDE_MODEL
    claude_shim.py    # OpenAI client -> Anthropic base_url for image captioning
    jobs.py           # in-memory batch registry + .md/.zip packaging
    updates.py        # conversion engine check/dev apply; frozen builds cannot apply directly
    app_updates.py    # app GitHub release check; wheel apply in dev, installer apply when frozen
    installer_update.py # download/launch Setup.exe in frozen builds
    window_bridge.py  # pywebview native file/folder picker bridge
    schemas.py        # ConvertOptions, ConversionResult, BatchResult, *Request, discovery models
    web/              # copied Vite build; gitignored
  packaging/          # PyInstaller spec + Inno Setup script
  .github/workflows/  # release + engine auto-update automation
  frontend/src/
    lib/  api.ts (typed client) · types.ts (mirror of schemas) · theme.tsx · utils.ts
    components/  Header, ConvertPanel, FileDropzone, OptionsPanel, ResultCard, Markdown,
                 CapabilitiesDialog, PluginsDialog, SettingsDialog, ThemeToggle, SourceIcon,
                 ui/ (shadcn)
    App.tsx, main.tsx, index.css (theme tokens + .md-preview prose)
```

## Backend API contract (current)
- `GET /api/health` · `GET /api/capabilities` · `GET /api/plugins`
- `POST /api/convert/file` — multipart: `files[]` + `options` (JSON string) → `BatchResult`
- `POST /api/convert/paths` — `{paths, options}` → `BatchResult`
- `POST /api/convert/folder` — `{path, recursive, options}` → `BatchResult`
- `POST /api/convert/url` — `{url, options}` → `ConversionResult`
- `POST /api/convert/text` — `{content, extension, charset, options}` → `ConversionResult`
- `GET /api/download/{batch_id}` — successful batch output as one `.md` or a `.zip`
- `POST /api/save-markdown` — `{filename, content}` → native desktop save dialog (`SaveResult`)
- `POST /api/save-download/{batch_id}` — native desktop save dialog for a batch `.md`/`.zip`
- `GET /api/native` · `POST /api/pick-files` · `POST /api/pick-folder`
- `GET /api/settings` (redacted) · `PUT /api/settings` (merges; keeps secrets if sent redacted)
- **`ConvertOptions`**: `extension?`, `mimetype?`, `charset?`, `keep_data_uris`, `enable_plugins`,
  `describe_images`, `azure_backend: "none"|"docintel"|"cu"`.
- **`ConversionResult`**: `filename`, `ok`, `markdown?`, `title?`, `warnings[]`, `error?`,
  `error_kind?`, `remediation?`.
- **`BatchResult`**: `batch_id`, `results[]`.

## Current status (verify against live code — chats may have advanced it)
| Phase | Title | Status |
|------|-------|--------|
| 1 | Scaffold + deps | ✅ done |
| 2 | Backend + conversion service | ✅ done |
| 3 | pywebview launcher + scripts | ✅ done |
| 4 | Convert UI (file/url/text) | ✅ done |
| 5 | Batch/folder + native pick + ZIP | ✅ done |
| 6 | Settings + Claude + Azure | ✅ done (Settings coverage, redaction, cloud gates, CU routing; real cloud calls still need valid keys/network) |
| 7 | Plugins + About + polish | ✅ done (Plugins dialog, capabilities, theme, toasts, shortcuts, empty/loading states, file-type icons, warnings/remediation callouts) |
| 8 | Docs + end-to-end verification | ✅ done — full local smoke pass on June 16, 2026 after venv repair; remaining items are Windows/GitHub manual validation |
| 9 | Windows packaging (Setup.exe) + app/engine auto-update | 🟡 implemented — structure/update automation present; Windows installer and GitHub workflow verification still manual |

> **Phase 9A (DONE):** in-app update *checks* for both the **engine** (PyPI, `updates.py`) and
> the **app** (GitHub Releases, `app_updates.py` + `gh.py` + `app_version.py`), a unified
> `UpdatesDialog`/`UpdateSection` UI, `/api/updates/*` + `/api/app/*` endpoints, and settings
> `app_repo`/`auto_check_updates`/`skipped_app_version`. Verified (tsc/lint/build + backend
> smoke tests). **9B–9E:** package restructure, PyInstaller/Inno metadata, frozen-aware app
> update apply, frozen engine-update gating, release workflows, and docs are implemented in
> repo form. Still manually verify PyInstaller/Inno install/update on Windows and wire the real
> GitHub repo settings/secrets/branch rules.

---

## Phase 1 — Scaffold + dependencies ✅
- **Goal:** Project skeleton + all tooling.
- **Deliverables:** `omnivert-app/{backend,frontend}`, `.gitignore`, `requirements-app.txt`;
  backend deps in venv (fastapi, uvicorn[standard], python-multipart, pywebview); Vite React-TS;
  Tailwind v4 via `@tailwindcss/vite`; shadcn baseline (`components.json`, `@/*` alias, `cn`,
  theme tokens); react-markdown/remark-gfm/sonner/lucide.
- **Acceptance:** `npm run build` compiles; `npx shadcn add <c>` works.

## Phase 2 — Backend + conversion service ✅
- **Goal:** All conversion + discovery endpoints around `markitdown`.
- **Deliverables:** the seven backend modules; endpoints for capabilities/plugins/convert(file,
  url,text)/settings. `ConversionService` uses `convert_stream` with `StreamInfo` (narrowest
  method), captures warnings via `warnings.catch_warnings(record=True)`, maps
  `UnsupportedFormat/MissingDependency/FileConversion` exceptions to friendly `error_kind` +
  `remediation`.
- **Acceptance:** CSV/HTML/JSON/data-URI convert correctly; no-key captioning returns a clean
  config error; settings redaction round-trips.

## Phase 3 — Desktop launcher ✅
- **Goal:** Open as a native window.
- **Deliverables:** `app.py` (free port pref 8765, Uvicorn in daemon thread, readiness gate,
  pywebview window, "build the UI first" fallback page); `run.bat`, `build.bat`.
- **Acceptance:** `run.bat` opens the window; server reachable; closes cleanly.

## Phase 4 — Convert UI ✅
- **Goal:** Point-and-click conversion for the three input modes.
- **Deliverables:** `ConvertPanel` (Files / URL / Text tabs), `FileDropzone` (drag-drop multi),
  `OptionsPanel` (extension/mime/charset hints, keep-data-uris, enable-plugins, describe-images,
  Azure backend selector — gated by capabilities/settings), `ResultCard` (Rendered↔Raw toggle
  via `Markdown.tsx` + `.md-preview`, copy, download `.md`), `Header`.
- **Acceptance:** Convert a PDF/DOCX/HTML and a URL; rendered + raw both correct; copy/download work.
- **Kickoff line:** *"Omnivert phase 4 (Convert UI). Read CLAUDE.md + PHASES.md. Backend
  on 8765, Vite proxies /api. Build the file/url/text convert flow per the phase-4 spec."*

## Phase 5 — Batch / folder / ZIP ✅
- **Goal:** Convert many files and a whole local folder; download all results.
- **Backend deliverables:**
  - `POST /api/convert/folder` `{path, recursive, options}` → walks the folder, converts each,
    returns `BatchResult`; recursive walks skip `.git`, `.venv`, `node_modules`, `dist`, and
    `__pycache__`.
  - `POST /api/convert/paths` converts local paths from native file picking and returns per-file
    missing/read errors without failing the whole batch.
  - `GET /api/download/{id}` → a single `.md` when exactly one item succeeded, otherwise a `.zip`
    containing successful Markdown files plus `_conversion-report.txt`.
  - `POST /api/pick-folder` / `POST /api/pick-files` trigger pywebview native dialogs through
    `window_bridge.py`; `GET /api/native` reports availability so dev mode can hide these buttons.
- **Frontend deliverables:** Files tab handles upload batches and native file paths; Folder tab
  supports pasted/picked folder paths plus recursive mode; results reuse `ResultCard`; successful
  batches show "Download all". In the desktop app, save/download actions use pywebview native
  save dialogs; browser-style downloads remain the dev fallback.
- **Acceptance:** backend smoke verified health, text, upload batch, paths with missing-file error,
  flat + recursive folder conversion, single `.md` download, and multi-result `.zip` contents.

## Phase 6 — Settings + Claude + Azure ✅
- **Goal:** Configure secrets/options; enable cloud + captioning paths.
- **Deliverables:** `SettingsDialog` for Azure (Doc Intelligence endpoint/key/api-version;
  Content Understanding endpoint/key/analyzer/file-types), Claude (api key/model/base url),
  exiftool path, style map, UI defaults, theme. Persists via `PUT /api/settings` (send redacted
  secrets unchanged). Captioning wired through `claude_shim` (`describe_images` + key).
- **Completed:** Settings dialog covers every `settings.py` field; blank or `__REDACTED__`
  secret submissions preserve stored keys; the frontend only enables Claude/DocIntel/CU controls
  when the matching key and endpoint are configured; backend conversion returns structured
  configuration errors instead of silently falling back when Claude/Azure settings are absent;
  `cu_file_types` is normalized (`.pdf`, `jpg`, etc.) and passed to the engine's
  `ContentUnderstandingFileType` list.
- **Verified:** compileall backend, frontend build, frontend lint, focused backend settings/cloud
  gate checks, and API-level settings/convert smoke checks. Real Claude/Azure service calls were
  not exercised in this pass because no live keys/network were used; with keys present these paths
  are wired to the engine and gate cleanly when absent.
- **Kickoff line:** *"Omnivert phase 6 review. Read CLAUDE.md + PHASES.md. Verify the
  Settings dialog covers every settings.py field, saving keeps redacted secrets, and the Claude
  captioning + both Azure backends work end-to-end (gate gracefully when keys absent)."*

## Phase 7 — Plugins + About + polish ✅
- **Goal:** Remaining surfaces + UX finish.
- **Completed:** `PluginsDialog` lists `GET /api/plugins`, shows installed plugin entry-points,
  handles loading/error/retry, and shows a "none installed" state with venv `pip install` guidance
  plus the `markitdown-plugin` discovery hint. `Header` exposes Plugins next to Capabilities.
  `ConvertPanel` supports Ctrl/Cmd+Enter conversion, a visible shortcut hint, and empty/loading
  states. `SourceIcon` adds file-type-aware icons to queued files, native paths, and results.
  `ResultCard` surfaces warnings as callouts and remediation as a distinct failure callout.
- **Follow-up fix:** pywebview can ignore browser-style blob downloads, so individual `.md`
  saves and batch downloads now use native save dialogs via `/api/save-markdown` and
  `/api/save-download/{batch_id}` when `GET /api/native` reports desktop dialogs are available.
- **Verified:** frontend
  type-check, frontend lint, production build, backend compile/import, `/api/health`,
  `/api/plugins`, and a simple `/api/convert/text` smoke check passed. Vite still emits the known
  non-blocking >500 kB chunk warning, and backend import still surfaces the documented missing
  ffmpeg RuntimeWarning.
- **Kickoff line:** *"Omnivert phase 7 (Plugins UI + polish). Read CLAUDE.md + PHASES.md.
  Add a Plugins view backed by /api/plugins, then keyboard shortcuts, empty/loading states, and
  surface ConversionResult.warnings/remediation in the UI."*

## Phase 8 — Docs + end-to-end verification 🟡
- **Goal:** Ship-ready docs + full smoke pass.
- **Completed:** `README.md` now covers install, settings location, dev/run commands,
  package-root smoke checks, API boot smoke, update model, packaging commands, and
  troubleshooting for build assets, ffmpeg, YouTube extras, Claude/Azure settings, and
  unsigned installers. `RELEASING.md` now calls out local pre-release checks and the manual
  Windows/GitHub validation boundary. `CLAUDE.md` records the latest local verification and
  the remaining manual work. The release workflow version extraction was corrected during
  verification.
- **June 16, 2026 rename update:** The app/project rename to Omnivert is mostly complete.
  Static scans are clean for stale app identifiers (`markitdown-app`, `MarkItDown Studio`,
  `MarkItDownStudio`, `markitdown_studio`, `markitdown-studio`, old helper script names, and
  `markitdown_version`). Remaining `markitdown` / `MarkItDown` references should be upstream
  engine package/API references only. The app folder is `omnivert-app` (the GitHub repo root).
  The rename is complete.
- **Verified locally on June 15, 2026:** backend `compileall`; package imports
  (`omnivert.main`, `omnivert.launcher`); representative text conversions
  via `tests/engine_smoke.py`; Uvicorn boot on `127.0.0.1:8765`; `/api/health`,
  `/api/capabilities`, `/api/plugins`, `/api/convert/text`, and multipart
  `/api/convert/file`; frontend lint; frontend production build; `scripts/copy_web_assets.py`;
  wheel build via `pip wheel --no-deps --no-build-isolation`; and wheel contents for package
  `web/` assets.
- **Verified locally on June 16, 2026 after rename:** `python -m compileall src`,
  frontend lint, frontend production build, package web asset copy, stale app-identifier scan,
  and git-ignore coverage for generated/dependency folders.
- **Full smoke pass on June 16, 2026:** `python -m compileall src`;
  `import omnivert.main, omnivert.launcher`;
  `tests/engine_smoke.py` (exit 0); Uvicorn boot on `127.0.0.1:8765`; `/api/health`,
  `/api/app/version`, `/api/capabilities`, `/api/plugins`, `/api/convert/text`, and multipart
  `/api/convert/file` (CSV→Markdown table); frontend lint + production build;
  `scripts/copy_web_assets.py`; and a clean wheel build. (If module files ever go missing in a
  cloud-synced working folder, reinstall the curated engine extras pin and re-pin
  `pydantic<2.14` to stable — see CLAUDE.md "Environment caveat".)
- **Wheel verified:** cleaned the ignored `build\` cache, rebuilt the wheel via the documented
  `pip wheel --no-deps --no-build-isolation`. The `omnivert-0.1.0-py3-none-any.whl`
  has **28 entries, 0 stale entries**, and contains only current `omnivert/web`
  assets plus the `omnivert` package + `dist-info`.
- **Notes:** The missing `ffmpeg` warning is still expected for audio-related imports. Vite
  still emits the known non-blocking >500 kB chunk warning. `python -m build --wheel` is not
  the preferred local check when a generated `build\` directory exists; use the documented
  `pip wheel` command with repo-local `PIP_CACHE_DIR` instead.
- **Still manual:** drag/drop PDF+DOCX in the desktop window, URL conversion against live
  network, folder batch ZIP from the UI, mp3 warning in the UI, real Claude/Azure calls with
  valid keys, pywebview native save/picker UX, PyInstaller freeze, Inno Setup compile,
  installed `Setup.exe` launch/conversion, update over an existing install, and GitHub
  release/engine automation workflow permissions.
- **Kickoff line:** *"Omnivert phase 8 (docs + E2E). Read CLAUDE.md + PHASES.md. Write
  README.md, refresh the living docs, and run the full end-to-end verification, reporting results."*

## Phase 9 — Windows packaging (Setup.exe) + app/engine auto-update 🟢 build validated; update/CI automation pending

**Goal:** Ship a double-click `Setup.exe` for non-technical Windows users, published from a
GitHub repo, with the app able to detect and install its own updates. the conversion engine
engine updates are shipped by automated Omnivert releases after CI safety checks pass.

**Decisions:** app name = **Omnivert**; GitHub release repo = `BrandonDry/Omnivert`;
primary install =
PyInstaller-frozen app + **Inno Setup** `Setup.exe`; app
self-update = **download & run the new `Setup.exe`** (no pip in a frozen build); restructure
`backend/` into a proper package first; GitHub repo root = `omnivert-app/`.

> ⚠️ **A frozen app has no pip.** So the engine updater (`updates.py`) and the app's pip-apply
> become **dev-only**. The shipped app self-updates via the installer, and the **conversion
> engine version is bundled per release**. The frozen app still checks PyPI/GitHub and can prompt
> that a newer engine exists, but the direct engine "Update" button is disabled with a bundled
> engine note.

### Target GitHub layout
```
omnivert-app/
  src/omnivert/
    __init__.py
    __main__.py
    launcher.py
    main.py jobs.py conversion.py updates.py app_updates.py installer_update.py ...
    web/                         # copied frontend build; gitignored
  frontend/
  packaging/
    app.spec
    installer.iss
    freeze_entry.py
  scripts/
    copy_web_assets.py
    check_latest_engine.py
    pin_engine_version.py
    bump_app_version.py
    set_build_repo.py
  tests/
    engine_smoke.py
  .github/workflows/
    release.yml
    engine-watch.yml
    engine-update.yml
  pyproject.toml README.md RELEASING.md AGENTS.md CLAUDE.md
```

### 9A — In-app update checks + unified UI ✅ DONE (verify, don't rebuild)
- Backend: `gh.py` (shared `get_json`/`is_newer`), `app_version.py` (`__version__` + git SHA),
  `app_updates.py` (GitHub-release check + pip-apply worker + editable/not-packaged guards);
  `updates.py` refactored onto `gh.py`. Endpoints `/api/app/version`, `/api/app/updates/{check,
  apply,status}`. Schemas `AppVersionInfo`/`AppUpdateInfo`/`AppUpdateApplyRequest`. Settings
  `app_repo`/`auto_check_updates`/`skipped_app_version`.
- Frontend: `UpdatesDialog` + `UpdateSection` (App + Engine rows), api/types, launch-time check
  + header dot (`App.tsx`/`Header.tsx`), Settings repo-slug + auto-check.
- Verified: `tsc`/`lint`/`build` green; backend smoke tests (engine check/apply, app check vs
  `microsoft/markitdown`, app apply-guard).

### 9B — Restructure to a `src/omnivert` package ✅ implemented
- `backend/*.py` moved to `src/omnivert/`; `app.py` is now a compatibility shim;
  launcher logic lives in `launcher.py`; `python -m omnivert` is the primary entry.
- Intra-package imports are relative. `main.py` static web lookup is mode-aware:
  package `web/` → PyInstaller `_MEIPASS/web` → dev `frontend/dist`.
- `build.bat` builds frontend and copies `frontend/dist` into package `web/`; `run.bat` sets
  `PYTHONPATH=src` and launches the package entrypoint.

### 9C — UI bundling + freeze + installer ✅ built & validated on Windows (June 16, 2026)
- Added `pyproject.toml` with package data for `web/**` and explicit engine curated extras
  pin. Added `packaging/app.spec`, `packaging/freeze_entry.py`, and `packaging/installer.iss`.
- `release.yml` builds frontend, copies web assets, builds a wheel, freezes with PyInstaller,
  compiles Inno Setup, and uploads `Setup.exe` plus wheel to GitHub Releases.
- **Built and verified the full chain locally on Windows (June 16, 2026):**
  PyInstaller freeze → `dist\Omnivert\Omnivert.exe` (boots, serves `/api`, converts);
  Inno Setup 6 compile → `dist\installer\Omnivert-Setup-0.1.0.exe` (96 MB);
  silent install → `%LOCALAPPDATA%\Programs\Omnivert\Omnivert.exe` + Start-Menu shortcut;
  installed app boots, reports `frozen:true`, `engine_version:0.1.6`, and converts a CSV
  file to a Markdown table.
- **Two spec fixes were required and are now committed in `packaging/app.spec`:**
  1. **`ROOT` was off by one level** (`Path(SPECPATH).parent.parent` → `.parent`). The spec
     lives in `omnivert-app/packaging/`, so the old value climbed into the outer `Omnivert/`
     wrapper and PyInstaller failed with *"script freeze_entry.py not found"*. (Symptom of the
     wrapper-nesting wart — see CLAUDE.md "Licensing"/structure notes.)
  2. **Package metadata was missing in the frozen build**, so
     `importlib.metadata.version(...)` returned `None` and the Capabilities dialog showed no
     engine/dependency versions. Added `copy_metadata("markitdown", recursive=True)` plus an
     explicit `copy_metadata` list for the optional deps in `_OPTIONAL_DEPS`
     (`src/omnivert/capabilities.py`) — keep the two lists in sync.
- **Update-over-install validated (June 16, 2026):** built a 0.1.1 installer and ran it silently
  over the installed 0.1.0; Windows registered version went 0.1.0 → 0.1.1 **in place** (single
  Uninstall entry, no side-by-side), and the upgraded app booted and converted a file. (Repo
  reverted to 0.1.0 afterward; the 0.1.1 build was a throwaway test.)
- **Published to GitHub (June 16, 2026):** initial commit pushed to `main` on
  `BrandonDry/Omnivert`; Release **v0.1.0** created with the tested
  `Omnivert-Setup-0.1.0.exe` (96 MB) attached. **Caveat:** the `gh` token lacks the `workflow`
  scope, so `.github/workflows/*` were held back from the push (they remain on disk). Run
  `gh auth refresh -h github.com -s workflow`, then commit + push `.github/workflows/` to enable
  the release/engine-automation CI — that CI run is the only remaining unvalidated item.

### 9D — Pluggable self-update apply ✅ implemented
- `GET /api/app/version` exposes `frozen`. `app_updates.py` returns the installer asset URL
  as the apply URL when frozen and keeps wheel apply for dev/package mode.
- New `installer_update.py` downloads and launches the release `Setup.exe`.
- `updates.py` still checks the conversion engine/PyPI in frozen mode, but reports
  `can_apply=false` and an "engine bundled with app" note. The UI uses that to disable direct
  engine apply while still prompting that a newer engine exists.

### 9E — Repo, CI, docs, engine automation 🟡 implemented; repo wiring pending
- Added `README.md`, `RELEASING.md`, repo-local `AGENTS.md` and `CLAUDE.md`, expanded
  `.gitignore`, and helper scripts. Phase 8 polished the user-facing docs and fixed the
  release workflow's app-version extraction command.
- Added `engine-watch.yml`: scheduled/manual PyPI check for newer the conversion engine.
- Added `engine-update.yml`: pins the new engine, bumps Omnivert patch version, stamps build repo
  metadata, runs frontend build/lint, installs the updated package, runs backend import checks,
  runs representative conversion smoke tests, builds a wheel, opens a bot PR, merges/tags when
  allowed, and opens an issue if checks fail.
- Safety model: auto-release only happens after CI validation passes. If branch protection blocks
  bot merge, the PR remains for manual review.

- **Verified locally/headless:** package imports, dev `uvicorn`, API smoke tests, frontend
  `tsc`/`lint`/`build`, web asset copy, wheel build, and simulated frozen flags.
- **Verified on Windows (June 16, 2026):** PyInstaller freeze, Inno `Setup.exe` build, silent
  install, and launch/convert of the installed frozen app.
- **Verified (June 16, 2026):** installer update *over an existing install* (0.1.0 → 0.1.1 in
  place); initial push to `main` and Release v0.1.0 published on `BrandonDry/Omnivert`.
- **Still to verify:** the GitHub Actions release/engine-automation runs (blocked until the
  `.github/workflows/` files are pushed — needs the `workflow` token scope, see 9C).
- **Open risks:** unsigned `Setup.exe` triggers SmartScreen until code signing; PyInstaller may
  need extra data-file tuning for engine transitive dependencies; first install remains a
  manual `Setup.exe` download.

- **Kickoff line (Codex):** *"Read AGENTS.md, CLAUDE.md, and PHASES.md from the `omnivert-app`
  repo root. Phase 9 package restructure, frozen-aware update apply, packaging metadata,
  release workflows, engine-watch automation, and docs are implemented. Verify locally, fix any
  failures, then validate PyInstaller/Inno and GitHub workflow permissions on Windows/GitHub.
  Remember: frozen builds cannot pip-update; the conversion engine engine updates ship through
  new Omnivert releases."*
