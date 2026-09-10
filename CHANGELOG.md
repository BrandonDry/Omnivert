# Changelog

All notable changes to Omnivert are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Image captioning now works on a clean install.** The "Describe images with Claude"
  toggle always failed with *"The 'openai' package is required for image captioning but is
  not installed"*, because `openai` is not pulled in by the conversion engine under any
  extra (not even `[all]`) and Omnivert never declared it either. It is now a declared
  dependency.
- **Capabilities dialog reports the truth.** The supported-format table omitted `.markdown`,
  `.text`, `.jsonl` and `.atom`, all of which the bundled engine accepts. The optional
  dependency list omitted `lxml`, `pandas`, `olefile` and `azure-identity` (all shipped)
  while listing `Pillow` and `youtube-transcript-api` (neither pinned).
- **`packaging/app.spec` metadata list realigned** with `capabilities._OPTIONAL_DEPS`. It had
  drifted in both directions, so the frozen build reported no version for several bundled
  dependencies. A test now enforces the sync that CLAUDE.md only asked for in prose.

### Changed

- **Batch conversions are substantially faster.** The engine was rebuilt for every file, at
  roughly 36 ms each; it is now cached per worker thread, so a folder batch pays that cost
  once instead of once per file (measured: 36 ms/file to 2.4 ms/file on small inputs). The
  cache is thread-local rather than global because an engine holds a `requests.Session`,
  which is not thread-safe.
- Formats whose gating dependency is missing are now shown as unavailable in the
  Capabilities dialog, and name the dependency they are waiting on, instead of being
  advertised as though they worked.
- Removed the YouTube capability badge and URL-tab notice. The bundled pin does not include
  the `youtube-transcription` extra, and a frozen build cannot install it, so the indicator
  could never read anything but "not installed".

### Added

- **Azure Document Intelligence file-type filter**, matching the one Content Understanding
  already had, so a specific set of extensions can be routed to the cloud backend.
- A `pytest` suite covering settings redaction, the SSRF URL guard, batch packaging, and the
  engine-cache invariants. `tests/engine_smoke.py` is unchanged and still runs as the
  auto-bump gate.

## [0.1.4] - 2026-07-30

### Changed

- Bundled conversion engine updated from MarkItDown 0.1.6 to 0.1.7 (PPTX chart conversion no
  longer O(n^2), PPTX SVG images without a rasterized fallback are handled, and several
  equation-conversion LaTeX macros are fixed). Shipped by the automated engine-update
  workflow.

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

[Unreleased]: https://github.com/BrandonDry/Omnivert/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/BrandonDry/Omnivert/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/BrandonDry/Omnivert/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/BrandonDry/Omnivert/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/BrandonDry/Omnivert/releases/tag/v0.1.1
