# Changelog

All notable changes to Omnivert are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.7] - 2026-09-10

0.1.4, 0.1.5 and 0.1.6 were all built and never published. Coming from 0.1.3, this release
carries every one of them: the conversion engine bump to MarkItDown 0.1.7, the security
fixes, the licensing and bundle corrections, and the upgrade fix below.

### Fixed

- **Upgrading left the previous release's files behind.** The installer only ever added and
  overwrote files, so an upgrade layered the new release on top of the old one instead of
  replacing it. Because PyInstaller puts the version in every `dist-info` directory name,
  installing over an older Omnivert left two of them for seventeen packages, and the version
  lookup then returned whichever it found first. The visible symptom: after upgrading from
  0.1.3, the Capabilities dialog reported **conversion engine 0.1.6** on a build that ships
  **0.1.7**, and every other dependency version it listed was equally unreliable.
  Conversions were unaffected, because the code was the new code and only the metadata was
  stale, which is why nothing but an actual install test could have caught it. The installer
  now clears its own program files before writing the new ones. Your settings are stored
  outside the application directory and are not touched.

## [0.1.6] - 2026-09-10

0.1.4 and 0.1.5 were both built and never published, so everything in their sections below
reaches users for the first time here. Coming from 0.1.3, this release carries all three:
0.1.4's conversion engine bump to MarkItDown 0.1.7, 0.1.5's security fixes, and this.

### Security

- **The packaged app no longer serves its own API documentation.** `/docs` and `/redoc` are
  not self-contained pages: each loads its real JavaScript from `cdn.jsdelivr.net`. In a
  frozen build that meant Omnivert fetching remote script into the very origin its
  unauthenticated local API trusts, reachable by a single same-origin navigation, and a
  converted document's Markdown preview renders links. `/openapi.json` handed any local caller
  the whole route surface for no benefit, since nothing in the UI reads it. All three are off
  in packaged builds and unchanged in development. Confirmed against the frozen build, not
  just the source.
- **Four Settings fields were execution, not configuration, and are now checked.**
  `exiftool_path` is handed to the conversion engine, which runs it as a program
  (`subprocess.run([it, "-ver"])`), so a write to the local API followed by any image
  conversion ran a program of the caller's choosing as you. Reproduced with a batch file that
  wrote a marker naming the logged-in user. It must now be a real local file whose name
  starts with `exiftool` and ends in `.exe` (so the official `exiftool(-k).exe` download
  works as-is), and never a network path, checked before anything touches the filesystem so
  a network path cannot make Omnivert reach out to a host a caller named. Separately,
  `claude_base_url`,
  `docintel_endpoint` and `cu_endpoint` decide which server receives the matching API key, so
  repointing one exfiltrated the key that reading settings back carefully redacts; they must
  now be `https`, or plain `http` only on this machine, which keeps a local gateway working.
  Rejections are reported as a 422 naming the field. All four are re-checked again at the
  point of use, because loading settings deliberately does not validate, so a file written
  by an older build is exactly the case that would otherwise slip past the write-time check.
- **Narrowed, not closed, and worth being exact about.** Someone who can reach the local API
  can still point an endpoint at an `https` host they control. A website cannot reach it, and
  that is tested; local code can, which for same-user malware changes nothing and on a machine
  with more than one account is a real escalation, because Windows loopback is not isolated
  per user. The per-session token in SECURITY.md remains the fix for the whole class.
- The release workflow no longer leaves a repository-write token in the workspace while `npm
  ci` and `pip install` run lifecycle code from around a hundred upstream packages
  (`persist-credentials: false`), and its permissions are granted per job instead of to the
  whole workflow.

### Fixed

- **A folder pick could hang the app before the file limit applied.** The 1000-file cap was
  checked after walking the entire tree, so on a drive root the walk itself was the hang the
  cap claimed to prevent. It now stops one file past the limit, and the message no longer
  reports a total it did not count.
- **The static frontend could be served from the wrong directory.** With `sys._MEIPASS`
  unset, the fallback resolved to the relative path `web`, taken from the working directory,
  so running from a checkout in a folder that happened to contain a `web` directory would
  mount it as the app's UI. Both the API and the launcher now require `_MEIPASS` to be set
  before using it.
- **Frozen builds no longer shell out to `git`.** The commit lookup meant nothing inside a
  bundle (measured: a build made inside a checkout reported that checkout's HEAD), and a
  windowed build spawning a console process risks flashing a console window at the user.
- The version badge in the header now reads **engine v0.1.7** rather than a bare version.
  Unlabelled, it was Omnivert's most visible number and it was not Omnivert's; bug reports
  cited it as the app version. Omnivert's own version is in the Updates dialog.
- The release asset allowlist refuses `..` outright. A bare prefix test accepted a URL that
  climbed back out of the pinned repository, which no real GitHub asset URL can produce, but
  this is the one gate deciding which executable gets launched.
- The update repository setting is validated against the shape GitHub actually allows,
  instead of being accepted on holding exactly one slash.

### Changed

- **A saved setting may now be refused when you next open Settings.** The checks above are
  applied on save, so a value that was accepted before can be rejected now: an ExifTool path
  that is not an `exiftool*.exe` file on this machine, or a cloud endpoint on plain `http`
  to anything other than this machine. Only a field you actually change is checked, so an
  older value you leave alone will not block you from saving anything else, and the dialog
  shows exactly what is wrong when it does refuse one.
  Conversions themselves are unaffected: an unusable ExifTool path is simply ignored, the
  same position a broken path already left you in, and a refused cloud endpoint only stops
  the cloud backend you selected.
- **The download is smaller, and no longer carries the build tool that made it.** The frozen
  executable embedded PyInstaller's own build modules, all of `pytest`, and the whole of
  `pygments`: 447 modules of build-time tooling in a binary that never invokes a build tool.
  They arrived through pywebview's own PyInstaller hook. Beyond the dead weight, PyInstaller
  is GPL-2.0-or-later and its bootloader exception does not cover those modules, so an
  Apache-2.0 binary was shipping GPL code with no licence text alongside it. The executable
  drops from 33.6 MB to 30.6 MB.
- **`THIRD_PARTY_NOTICES.md` is accurate now.** It claimed every bundled component was
  permissively licensed. Four are not: certifi is MPL-2.0, the FLAC binaries used for audio
  transcription are GPLv2, Eigen compiled into onnxruntime is MPL-2.0, and the WebView2
  assemblies are proprietary Microsoft components (redistributable, but not open source).
  Each is now named with what it actually requires, and the file says where to find licence
  text in an install and which components ship without any. None of it affects your right to
  use Omnivert, and none conflicts with its Apache-2.0 licence.
- The Inno Setup script no longer defaults the version. It went stale two releases running,
  and because the version names the output file, a local build of 0.1.5 silently produced
  `Omnivert-Setup-0.1.3.exe`. A compile without `/DMyAppVersion` now fails and says so.
- The published package summary was circular ("A Windows desktop GUI for Omnivert document
  conversion"), a leftover from the rename, and now describes what the app does.
- The Python 3.13 classifier is gone. CI runs 3.11 and 3.12; advertising a version nothing
  tests is how a supported version quietly breaks.

## [0.1.5] - 2026-09-10

### Security

- **Redirects bypassed the URL guard.** The guard validated the URL you typed, then handed
  the original string to the engine, which followed redirects with no limit and no timeout.
  A public URL answering `302 Location: http://127.0.0.1:<port>/api/settings` reached the
  app's own API on hop two, and every target the guard exists to refuse was one redirect
  away. Conversion now runs through a session whose adapter re-checks every hop, caps the
  chain, and applies a connect/read timeout. Reproduced before and after.
- **A website could make Omnivert work on its behalf.** The loopback Host guard closes DNS
  rebinding only; a page can address `127.0.0.1` directly and the Host is then a loopback
  name that must be allowed. Because `multipart/form-data` is CORS-safelisted, a cross-origin
  POST needed no preflight, so `/api/convert/file` ran with attacker-chosen options that
  spend your configured Claude or Azure keys, and the native pickers popped dialogs over your
  desktop. Verified at HTTP 200 before the fix, 403 after. A new middleware refuses requests a
  browser reports as cross-site, and the dev allowance is scoped to the Vite origins CORS
  already grants rather than any loopback port.
- **`/api/app/updates/apply` downloaded and executed a URL from the request body**, with no
  allowlist, no scheme restriction, and a checksum that was skipped whenever the filename was
  absent from the release's `SHA256SUMS`. The endpoint now ignores the body entirely and
  resolves the asset itself, pinned to this build's own repository for both the installer and
  the checksum file, with a missing or mismatched checksum fatal. A host allowlist would not
  have been enough: `app_repo` is a free-text setting, every GitHub account serves from
  `github.com`, and a release's `SHA256SUMS` is written by whoever published it, so an
  attacker's checksum matches an attacker's binary by construction.
- The apply route also never checked `update_available`, so a same-origin POST would
  re-download and launch the current release's installer on a machine already running it.

### Fixed

- A refused redirect target, a timeout, and an over-long redirect chain now report what
  happened instead of "Unexpected error during conversion".
- Removed a dead `asset_host_allowed` helper that referenced an undefined constant and would
  have raised `NameError` the moment anyone called it. It read like the asset gate and was
  not one.
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
- **The Azure file-type fields could only ever hold one extension.** Both the new Document
  Intelligence field and the existing Content Understanding one derived their displayed text
  from the parsed array, so typing a comma re-rendered the field without it and the separator
  was swallowed. They now keep the raw text and parse alongside it.
- **URL guard:** carrier-grade NAT (`100.64.0.0/10`) was not treated as non-public, and four
  URL shapes a user can type (out-of-range port, non-numeric port, unclosed IPv6 bracket,
  over-long hostname label) raised out of the guard as a 500 instead of returning the
  structured error every other conversion failure returns.
- **Download filenames** are taken from a converted document's `<title>`, and a raw CR or LF
  in one reached the `Content-Disposition` response header verbatim. Control characters are
  now stripped in both the filename builder and the header builder.

### Changed

- **Batch conversions are substantially faster.** The engine was rebuilt for every file, at
  roughly 36 ms each; it is now cached per worker thread, so a folder batch pays that cost
  once instead of once per file (measured: 36 ms/file to 2.4 ms/file on small inputs). The
  cache is thread-local rather than global because an engine holds a `requests.Session`,
  which is not thread-safe, and is released at the end of each request: worker threads
  outlive the requests that ran on them, and each retained engine pins its own ONNX session
  at roughly 8 MB.
- Formats whose gating dependency is missing are now shown as unavailable in the
  Capabilities dialog, and name the dependency they are waiting on, instead of being
  advertised as though they worked.
- `fastapi` is floored at `>=0.132` and `openai` bounded to one major. Both were previously
  unbounded, which let a build resolve a FastAPI old enough to parse a body with no
  `Content-Type` as JSON (a cross-origin request needs no CORS preflight to send one).
- Removed the YouTube capability badge and URL-tab notice. The bundled pin does not include
  the `youtube-transcription` extra, and a frozen build cannot install it, so the indicator
  could never read anything but "not installed".

### Added

- **Azure Document Intelligence file-type filter**, matching the one Content Understanding
  already had, so a specific set of extensions can be routed to the cloud backend.
- A `pytest` suite covering settings redaction, the SSRF URL guard, batch packaging, and the
  engine-cache invariants. `tests/engine_smoke.py` is unchanged and still runs as the
  auto-bump gate.
- **A CI workflow.** Pull requests previously ran only dependency review and the labeler: no
  tests, no typecheck, no lint. `ci.yml` now runs the Python suite on 3.11 and 3.12 plus the
  frontend typecheck, build and lint on every push and pull request, and both `release.yml`
  and `engine-update.yml` run the suite before building anything. The README gains a CI badge.

### Documentation

- **SECURITY.md overstated the loopback Host guard.** It read as "a website cannot reach the
  local API", which is true of DNS rebinding and misleading about everything else: a page can
  address `127.0.0.1` directly and the guard must allow it, because that is how the app's own
  UI talks to the API. The section now states the residual and its bound (no cross-origin
  allow header, so a hostile page cannot read any response) and what would close it properly.
- **RELEASING.md** still warned that the release workflow was unvalidated, four releases after
  it was validated, and never mentioned that releases are created as a **draft** that a
  maintainer must publish. It also had no CHANGELOG step.
- **Nothing told a contributor the test suite exists.** The word `pytest` appeared in no
  document in the repo. CONTRIBUTING, README, CLAUDE.md and the pull request template now all
  run it, and CONTRIBUTING names CI so a contributor knows what will fail if they skip it.
- `CLAUDE.md` gains a Testing section, the newer modules in its architecture map, the
  `service.batch()` contract a new conversion route can silently break, and a note recording
  that `openai` is Omnivert's own dependency rather than the engine's, so a future dependency
  tidy-up does not delete it and reship the captioning bug.
- The bug report template now asks for the Capabilities dialog, which turns a class of
  "conversion failed" reports into a one-line diagnosis.
- Em and en dashes removed from every tracked file. Three UI placeholders that rendered a
  bare dash for a missing value now name what is missing instead.

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

[Unreleased]: https://github.com/BrandonDry/Omnivert/compare/v0.1.7...HEAD
[0.1.7]: https://github.com/BrandonDry/Omnivert/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/BrandonDry/Omnivert/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/BrandonDry/Omnivert/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/BrandonDry/Omnivert/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/BrandonDry/Omnivert/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/BrandonDry/Omnivert/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/BrandonDry/Omnivert/releases/tag/v0.1.1
