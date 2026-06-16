# Changelog

All notable changes to Omnivert are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-16

Initial release.

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
- Apache-2.0 licensed, with MarkItDown (MIT) attribution and third-party notices.

### Security

- URL conversion restricted to `http`/`https` and blocked from loopback/private/link-local
  hosts.
- Request-size and batch-output bounds to prevent memory exhaustion.
- Local-only (loopback) API binding.
- Published `SHA256SUMS` for release artifacts as an interim integrity measure (code signing
  is a planned follow-up; see SECURITY.md).

[Unreleased]: https://github.com/BrandonDry/Omnivert/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/BrandonDry/Omnivert/releases/tag/v0.1.0
