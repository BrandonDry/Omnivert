<p align="center">
  <img src="assets/omnivert-banner.png" alt="Omnivert: Convert anything to Markdown" width="640">
</p>

<p align="center">
  A Windows desktop app that turns files, folders, URLs, and pasted text into clean
  Markdown, no terminal required.
</p>

<p align="center">
  <a href="https://github.com/BrandonDry/Omnivert/releases/latest"><img src="https://img.shields.io/github/v/release/BrandonDry/Omnivert?label=download&color=7e14ff" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License: Apache-2.0"></a>
  <img src="https://img.shields.io/badge/platform-Windows-0078d4" alt="Platform: Windows">
  <a href="https://github.com/BrandonDry/Omnivert/actions/workflows/ci.yml"><img src="https://github.com/BrandonDry/Omnivert/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
</p>

---

## What is Omnivert?

Omnivert is a friendly graphical wrapper around the Microsoft
**[MarkItDown](https://github.com/microsoft/markitdown)** conversion engine. Point it at
almost any document and it gives you back Markdown that's ready to paste into notes, docs,
or a large language model.

It runs entirely on your machine. Conversions happen locally, and optional cloud features
(image captioning, Azure Document Intelligence) are off until you add your own keys.

## Features

- **Many input types:** PDF, Word (DOCX), PowerPoint (PPTX), Excel (XLSX/XLS), Outlook
  messages (MSG), images, audio, HTML, CSV, JSON/JSONL, XML/RSS/Atom, EPUB, Jupyter
  notebooks, ZIP archives, and plain text.
- **Four ways to convert:** drop in files, point at a whole folder (optionally recursive),
  paste a URL, or paste raw text.
- **Batch conversion:** convert many files at once and download everything as a single
  `.md` or a `.zip`.
- **Live preview:** switch between the rendered Markdown and the raw source, copy with one
  click, or save to disk.
- **Optional AI image captions:** bring your own Claude or Azure key to describe images
  inside documents.
- **Light / dark / system themes** and keyboard shortcuts (Ctrl+Enter to convert).
- **Self-updating:** the app checks GitHub for new releases and can update itself.
- **Private by default:** conversions run on your machine, there is no telemetry and no
  account. The only servers Omnivert contacts on its own are GitHub (for new Omnivert
  releases) and PyPI (to see whether a newer conversion engine exists); both checks can be
  turned off in Settings. Your documents are never uploaded unless you switch on a cloud
  option and supply your own key.

## Install

1. Download the latest **`Omnivert-Setup-*.exe`** from the
   [Releases page](https://github.com/BrandonDry/Omnivert/releases/latest).
2. Run the installer. It installs per-user and **does not require administrator rights**.
3. Launch **Omnivert** from the Start menu.

### "Windows protected your PC" (SmartScreen)

Omnivert installers are not yet code-signed, so Windows SmartScreen may warn you the first
time you run the installer. The download is safe. To proceed:

1. On the blue SmartScreen dialog, click **More info**.
2. Click **Run anyway**.

To independently verify your download, each release publishes a `SHA256SUMS` file. Compare
it against your downloaded installer:

```powershell
Get-FileHash .\Omnivert-Setup-<version>.exe -Algorithm SHA256
```

The printed hash should match the matching line in `SHA256SUMS`. Code signing is a planned
follow-up, see [SECURITY.md](SECURITY.md).

## Use it

1. Open Omnivert.
2. Choose a tab: **Files**, **Folder**, **URL**, or **Text**.
3. Add your input (drag-and-drop files, pick a folder, paste a URL or text).
4. Click **Convert** (or press **Ctrl+Enter**).
5. Preview the Markdown, then **Copy** or **Save** / **Download**.

Settings (including any API keys) are stored outside the app at:

```text
%LOCALAPPDATA%\Omnivert\settings.json
```

That file may contain secrets. It is stored in plaintext on your machine, so don't share it
or paste it into support logs. See [SECURITY.md](SECURITY.md) for details.

## Updates

Omnivert checks its GitHub Releases for newer versions, both at launch and periodically
while running. Installed Windows builds update by downloading and running the next
`Setup.exe`.

The conversion engine is bundled into each Omnivert release. A GitHub workflow watches PyPI
for new MarkItDown versions, validates them, and rolls them into a new Omnivert release once
the safety checks pass.

---

## For developers

Omnivert is a **FastAPI** backend + **React/Vite/TypeScript/Tailwind** frontend, shipped as
a native window via **pywebview** and packaged for Windows with PyInstaller + Inno Setup.

This repo expects a Python virtual environment at `..\.venv\` (the local working setup) or
any environment with the package installed via `python -m pip install -e .`. Run commands
from this directory unless noted.

```powershell
build.bat   # npm install + build -> frontend/dist -> copy into the package web/
run.bat     # launch the desktop window
```

For the split dev loop (hot-reloading frontend + backend):

```powershell
$env:PYTHONPATH="$PWD\src"
..\.venv\Scripts\python.exe -m uvicorn omnivert.main:app --app-dir src --port 8765
npm run dev --prefix frontend   # proxies /api -> 127.0.0.1:8765
```

The backend package lives under `src/omnivert`; run it with `python -m omnivert` or the
`omnivert` console script.

See [CLAUDE.md](CLAUDE.md) for the architecture map and [CONTRIBUTING.md](CONTRIBUTING.md)
for how to set up, build, and submit changes.

### Local checks

```powershell
# Python compile/import checks
..\.venv\Scripts\python.exe -m compileall src
$env:PYTHONPATH="$PWD\src"; ..\.venv\Scripts\python.exe -c "import omnivert.main; import omnivert.launcher"

# Unit tests (no PYTHONPATH needed: pyproject sets pythonpath = ["src"])
..\.venv\Scripts\python.exe -m pytest -q

# Representative conversions (also the CI engine-bump gate; pytest does not collect this)
$env:PYTHONPATH="$PWD\src"; ..\.venv\Scripts\python.exe tests\engine_smoke.py

# Frontend
npm run lint --prefix frontend
npm run build --prefix frontend

# Copy built UI into the Python package
..\.venv\Scripts\python.exe scripts\copy_web_assets.py

# Wheel check
$env:PIP_CACHE_DIR="$PWD\.pip-cache"
..\.venv\Scripts\python.exe -m pip wheel --no-deps --no-build-isolation . -w dist\wheel-check
```

To smoke-test the API locally:

```powershell
$env:PYTHONPATH="$PWD\src"
..\.venv\Scripts\python.exe -m uvicorn omnivert.main:app --app-dir src --host 127.0.0.1 --port 8765
```

Then call `GET http://127.0.0.1:8765/api/health` and a conversion endpoint such as
`POST /api/convert/text`.

### Packaging

```powershell
npm ci --prefix frontend
npm run build --prefix frontend
python scripts\copy_web_assets.py
python -m pip install -e ".[build]"
pyinstaller packaging\app.spec --noconfirm --clean

# The installer version is required, not defaulted, so read it from the single source of truth
$v = (Select-String -Path src\omnivert\app_version.py -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DMyAppVersion="$v" packaging\installer.iss
```

The installer is written to `dist/installer/`. Release automation is documented in
[RELEASING.md](RELEASING.md).

### Troubleshooting

- If the desktop window shows a build notice or a blank page, run `build.bat` so
  `frontend/dist` is rebuilt and copied into `src/omnivert/web`.
- Non-WAV audio conversion needs `ffmpeg` on `PATH`. Without it, the engine emits a
  non-fatal warning and audio conversion can be limited.
- The `markitdown[all]` extra is intentionally not used here because the YouTube extra has
  Python-version caveats. YouTube transcript extraction is therefore **not** available in
  installed builds, and the UI no longer advertises it. Running from a checkout, you can
  still add a compatible `youtube-transcript-api` to the environment yourself.
- The Capabilities dialog marks a format **unavailable** when a dependency that gates it
  cannot be found, and names the dependency. Every dependency it lists ships with Omnivert,
  so anything reported missing means a damaged install rather than a normal state: reinstall
  to repair it. Note it detects a *missing* dependency, not a present-but-broken one, so a
  conversion can still fail with a healthy-looking dialog.
- Claude image captions and Azure Document Intelligence/Content Understanding require valid
  keys in Settings. The API redacts stored secrets on read.

## Credits

Omnivert's document conversion is powered by **Microsoft
[MarkItDown](https://github.com/microsoft/markitdown)** (MIT License, Copyright (c)
Microsoft Corporation). Omnivert bundles and runs MarkItDown but is an **independent
project and is not affiliated with, endorsed by, or sponsored by Microsoft**.

Third-party licensing and attribution are documented in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), which reproduces MarkItDown's MIT
licence in full, names every bundled component that is not permissively licensed, and says
where the rest of the licence texts sit inside an installation.

## License

Omnivert's own code is licensed under the **Apache License 2.0**, see [`LICENSE`](LICENSE)
and [`NOTICE`](NOTICE). Bundled third-party software retains its own license; see
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
