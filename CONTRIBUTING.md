# Contributing to Omnivert

Thanks for your interest in improving Omnivert! This project is a Windows desktop GUI around
the Microsoft [MarkItDown](https://github.com/microsoft/markitdown) conversion engine.
Contributions of all kinds are welcome — bug reports, fixes, features, and docs.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report a bug** — open an issue using the **Bug report** template.
- **Request a feature** — open an issue using the **Feature request** template.
- **Fix or build something** — see the workflow below.
- **Security issues** — please do **not** open a public issue. Follow
  [SECURITY.md](SECURITY.md) instead.

## Project layout

Omnivert is a **FastAPI** backend + **React/Vite/TypeScript/Tailwind** frontend, shipped as a
native window via **pywebview** and packaged for Windows with PyInstaller + Inno Setup.

- `src/omnivert/` — Python backend (FastAPI routes, conversion service, updaters, launcher).
- `frontend/` — React UI; the built assets are copied into `src/omnivert/web/`.
- `packaging/` — PyInstaller spec + Inno Setup script.
- `scripts/` — build/release helpers.
- `tests/engine_smoke.py` — conversion smoke tests (also the CI engine-bump gate).
- `.github/workflows/` — release and engine auto-update automation.

See [CLAUDE.md](CLAUDE.md) for a fuller architecture map.

## Development setup

Primary development happens on **Windows 11 / PowerShell**.

1. Create or reuse a Python environment (3.11+). The local working setup keeps a virtual
   environment at `..\.venv\`; alternatively install the package into your own environment:

   ```powershell
   python -m pip install -e ".[build,test]"
   ```

2. Install frontend dependencies and build the UI:

   ```powershell
   npm ci --prefix frontend
   npm run build --prefix frontend
   python scripts\copy_web_assets.py
   ```

3. Run the app, or use the split dev loop with hot reload:

   ```powershell
   run.bat
   # or:
   $env:PYTHONPATH="$PWD\src"
   python -m uvicorn omnivert.main:app --app-dir src --port 8765
   npm run dev --prefix frontend
   ```

## Before you open a pull request

Please run the local checks and make sure they pass:

```powershell
# Backend
python -m compileall src
$env:PYTHONPATH="$PWD\src"; python tests\engine_smoke.py

# Frontend
npm run lint --prefix frontend
npm run build --prefix frontend
```

Guidelines:

- Keep changes focused; one logical change per PR.
- Match the surrounding code style (the frontend uses ESLint; keep `npm run lint` clean).
- Update docs (`README.md`, `CLAUDE.md`, `CHANGELOG.md`) when behavior or setup changes.
- Add a `CHANGELOG.md` entry under **Unreleased** for user-visible changes.
- Reference any related issue in the PR description.

## Pull request flow

1. Fork the repo and create a topic branch off `main`.
2. Make your change with clear, descriptive commits.
3. Run the checks above.
4. Open a PR against `main` using the pull request template.
5. A maintainer will review. Please be responsive to feedback.

## Reporting bugs effectively

Good bug reports include:

- Your Omnivert version (Help / About, or the installer filename) and Windows version.
- The input type you were converting and, if possible, a small sample file.
- What you expected vs. what happened, including any error text or warnings shown.

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](LICENSE), the same license as the project.
