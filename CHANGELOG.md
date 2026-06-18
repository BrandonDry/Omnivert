# Changelog

All notable changes to Omnivert are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.3] - 2026-06-18

### Fixed

- Ensure the new "converge arrow" logo actually reaches users on install/update. The frozen
  `Omnivert.exe` now carries a proper Windows version resource (product name + per-release
  `FileVersion`/`ProductVersion`); previously it had none, so Windows labelled it the generic
  "Windows Application" and was prone to serving a stale cached icon after an in-place update.
- The installer now refreshes the Windows icon cache (`ie4uinit.exe -show`) after copying
  files, so updated Start-menu, desktop, and taskbar shortcuts repaint with the new logo
  immediately instead of keeping the previously cached icon.

### Changed

- Aligned the residual brand color `#863bff` (the old logo's fill) with the new mark's core
  purple `#7e14ff` in the PWA/web `theme-color` and the README release badge.

## [0.1.2] - 2026-06-18

### Changed

- Replaced the application logo with an original "converge arrow" mark (multiple inputs
  converging into a single rightward output). The previous icon was a recolored copy of the
  Vite logo; the new mark is unique to Omnivert and reused across the app UI, favicon/PWA
  icons, the embedded `Omnivert.exe`/installer icon, and the README/social images.

### Fixed

- `packaging/generate_logo_assets.py` no longer reproduces the old Vite-derived glyph; it
  now generates all branding assets from the new mark so regenerating stays in sync.

## [0.1.1] - 2026-06-17

Initial public release.

### Added

- Windows desktop GUI around the Microsoft MarkItDown conversion engine, shipped as a native
  pywebview window (FastAPI backend + React/Vite frontend).
- Convert from four input modes: **Files** (drag-and-drop, multi-file), **Folder** (with
  optional recursive walk), **URL**, and pasted **Text**.
- Batch conversion with combined download as a single `.md` or a `.zip`.
- Live Markdown preview with rendered/raw toggle, copy, and save/download.
- Optional AI image captioning via Claude or Azure Document Intelligence / Content
  Understanding (bring your own keys).
- Light / dark / system themes and keyboard shortcuts.
- In-app update checks for both the app (GitHub Releases) and the bundled conversion engine
  (PyPI), with self-update via the next `Setup.exe` on installed Windows builds.
- Per-user Windows installer (PyInstaller + Inno Setup); no admin rights required.
- Application and installer branding: the Omnivert logo is embedded in `Omnivert.exe`, the
  `Setup.exe` installer, the Start-menu and desktop shortcuts, and the uninstall entry.
- Apache-2.0 licensed, with MarkItDown (MIT) attribution and third-party notices.

### Security

- URL conversion restricted to `http`/`https` and blocked from loopback/private/link-local
  hosts.
- Request-size and batch-output bounds to prevent memory exhaustion.
- Local-only (loopback) API binding.
- Release artifacts include the Python wheel and a published `SHA256SUMS` file as an interim
  integrity measure (code signing is a planned follow-up; see SECURITY.md).

[Unreleased]: https://github.com/BrandonDry/Omnivert/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/BrandonDry/Omnivert/releases/tag/v0.1.1
