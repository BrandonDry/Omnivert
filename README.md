# Omnivert

Omnivert is a Windows desktop GUI built around the **Microsoft
[MarkItDown](https://github.com/microsoft/markitdown)** conversion engine. It
converts files, folders, URLs, and pasted text into Markdown without requiring users to
run terminal commands.

Current private release repository: `BrandonDry/Omnivert`.

## Install

Download the latest `Omnivert-Setup-*.exe` from GitHub Releases and run it.
The installer is per-user and does not require admin rights.

Settings are stored outside the repo at:

```text
%LOCALAPPDATA%\Omnivert\settings.json
```

That file may contain API keys. Do not commit it or copy it into support logs.

## Development

This repo expects the local wrapper virtual environment at `..\.venv\`. Run commands from
this `omnivert-app` directory unless noted.

```powershell
build.bat
run.bat
```

For the split dev loop:

```powershell
$env:PYTHONPATH="$PWD\src"
..\.venv\Scripts\python.exe -m uvicorn omnivert.main:app --app-dir src --port 8765
npm run dev --prefix frontend
```

The backend package lives under `src/omnivert`. `app.py` is only a compatibility
shim; new commands should use `python -m omnivert` or the `omnivert`
console script after installation.

## Local Checks

These are the main Phase 8 smoke checks:

```powershell
# Python compile/import checks
..\.venv\Scripts\python.exe -m compileall src
$env:PYTHONPATH="$PWD\src"; ..\.venv\Scripts\python.exe -c "import omnivert.main; import omnivert.launcher"

# Representative text conversions
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

Then call `GET http://127.0.0.1:8765/api/health` and a representative conversion endpoint
such as `POST /api/convert/text`.

## Updates

The app checks your GitHub Releases for newer Omnivert versions. Installed
Windows builds update by downloading and running the next `Setup.exe`.

Conversion engine updates are bundled into Omnivert releases. A GitHub workflow
checks PyPI for newer conversion engine versions, validates the new engine, and creates a new
Omnivert release when safety checks pass.

## Packaging

```powershell
npm ci --prefix frontend
npm run build --prefix frontend
python scripts\copy_web_assets.py
python -m pip install -e ".[build]"
pyinstaller packaging\app.spec --noconfirm --clean
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DMyAppVersion="0.1.0" packaging\installer.iss
```

The installer is written to `dist/installer/`.

## Troubleshooting

- If the desktop window shows a build notice or a blank page, run `build.bat` so
  `frontend/dist` is rebuilt and copied into `src/omnivert/web`.
- Non-WAV audio conversion needs `ffmpeg` on `PATH`. Without it, the engine may emit a
  non-fatal warning and audio conversion can be limited.
- The `markitdown[all]` extra is intentionally not used here because the YouTube extra has
  Python-version caveats. YouTube URL support may still work if a compatible
  `youtube-transcript-api` is present in the local environment.
- Claude image captions and Azure Document Intelligence/Content Understanding require
  valid keys in Settings. The API redacts stored secrets on read.
- Unsigned Windows installers can trigger SmartScreen until code signing is added.

## Credits

Omnivert's document conversion is powered by **Microsoft
[MarkItDown](https://github.com/microsoft/markitdown)** (MIT License, Copyright (c)
Microsoft Corporation). Omnivert bundles and runs MarkItDown but is an independent
project and is not affiliated with, endorsed by, or sponsored by Microsoft.

Full third-party license texts are in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## License

Omnivert's own code is licensed under the **Apache License 2.0** — see
[`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). Bundled third-party software retains its
own license; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
