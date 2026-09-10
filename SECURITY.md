# Security Policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report privately using GitHub's **[private vulnerability reporting](https://github.com/BrandonDry/Omnivert/security/advisories/new)**
("Report a vulnerability" under the repository's **Security** tab). This keeps the details
confidential until a fix is available.

When reporting, please include:

- A description of the issue and its potential impact.
- Steps to reproduce, or a proof-of-concept, if possible.
- The Omnivert version and your Windows version.

We aim to acknowledge reports within a few days and will keep you informed as we work on a
fix. Coordinated disclosure is appreciated, so please give us a reasonable window to release a
patch before any public discussion.

## Supported versions

Omnivert is pre-1.0 and ships frequent releases. Security fixes target the **latest**
released version. Please update to the newest release before reporting an issue.

## Security model and known limitations

Omnivert runs locally on your machine. A few properties are worth understanding:

- **Local-only API.** The bundled FastAPI backend binds to loopback (`127.0.0.1`) only, and
  the frozen desktop UI is same-origin. There is no remote network listener, so nothing else
  on your network can reach it. As a defense-in-depth measure against DNS rebinding, the
  backend also rejects any request whose `Host` header is not a loopback name, which stops a
  website from pointing its own hostname at `127.0.0.1` and then reading the API's responses
  as though they were its own.
- **Cross-site requests are refused.** A page you visit can still address
  `http://127.0.0.1:<port>` directly, and the `Host` header is then a loopback name the guard
  above has to allow, because that is also how the app's own UI talks to the API. The backend
  therefore also checks where the browser says the request came from: the `Sec-Fetch-Site` and
  `Origin` headers must say this app's own window, or the request is refused with a 403 before
  any route runs. Previously such a request was accepted and acted on: a form post from a
  hostile page could make Omnivert convert content it supplied, with options that spent your
  configured Claude or Azure credits, or pop a native file picker over your desktop.
- **Anything that can reach the API is trusted completely.** The backend has no
  authentication at all, so this is worth stating plainly rather than leaving to be inferred.
  A caller that reaches it can read any file your account can read (that is what the folder
  and paths converters do), and two Settings fields turn into more than configuration: the
  `exiftool_path` setting is passed to the conversion engine, which runs it as a program, and
  the Claude base URL decides which server the app sends your Claude API key to. Writing those
  through `PUT /api/settings` and then converting a file is therefore **arbitrary program
  execution as you, and disclosure of the stored key**, for anyone who can make the request.
  A website cannot: that is what the cross-site check above stops, and it is tested. What
  remains is local code, which for same-user malware changes nothing (it could already read
  your files and run programs as you), but on a machine with more than one account it is a
  real escalation, because Windows loopback is not isolated per user. The per-session token
  named below is the fix for this whole class, not just for the cross-site half.
- **What that still does not cover.** Both headers are set by the browser, so the check is
  only as good as the browser making the request. `Sec-Fetch-Site` arrived in Chromium 76
  (2019), Firefox 90 (2021) and Safari 16.4 (2023). A client that sends neither header is
  allowed through, because refusing it would break every non-browser client of a local API
  that has no authentication at all, and because pywebview falls back to an older renderer
  when the WebView2 runtime is missing. Every browser still in service sends `Origin` on
  requests that change something, so what the allowance leaves open is a cross-site `GET`,
  whose response the page still cannot read. Fully closing this needs a per-session token
  shared between the bundled UI and the API.
- **Development builds are slightly more permissive.** A copy that is not the packaged
  Windows build (a `pip install`, or running from source) also accepts the Vite dev server's
  two origins, `http://localhost:5173` and `http://127.0.0.1:5173`, which are the same two
  the dev CORS policy grants. That is the whole of the difference: any other local origin,
  including another port such as `http://localhost:3000`, is refused in dev exactly as it is
  in a packaged build. The packaged installer build has no dev allowance at all and accepts
  only its own window's origin.
- **Local file access is intentional.** The folder/paths conversion endpoints read the files
  and folders you select (via the native picker or a typed path) so they can be converted to
  Markdown. Reading your own files is the app's purpose; the API does not write to arbitrary
  paths (saving goes through the native save dialog).
- **URL conversion is restricted.** The URL converter accepts only `http`/`https` URLs and
  rejects other schemes (e.g. `file:`) and hosts that resolve to loopback, private, or
  link-local address ranges, to avoid local-file and internal-network access. The check is
  re-applied to **every redirect hop**, not just the address you type, so a public URL cannot
  bounce the fetch onto a local or internal one; chains are capped and every fetch has a
  timeout.
- **The URL check and HTTP proxies.** If your machine is configured with an `HTTP_PROXY` or
  `HTTPS_PROXY`, Omnivert uses it, and the proxy then resolves hostnames instead of Omnivert.
  Addresses written literally (`http://127.0.0.1/`, `http://10.0.0.5/`) are still refused,
  because they need no lookup, but a **name** that your proxy resolves to an internal address
  can get through. Ignoring a configured proxy would break the URL tab entirely on machines
  that have no other route out, which we judged the worse outcome.
- **Other limits of the URL check.** The response size is not capped, so an allowed URL can
  still return a very large document. A host that resolves differently between the check and
  the fetch (DNS rebinding) can still win that race. And the check refuses hosts by resolving
  them, so it depends on the Windows resolver's refusal to resolve obfuscated forms such as
  `http://2130706433/`; Omnivert is a Windows application and this reasoning does not carry
  to other platforms.
- **Request/output bounds.** Upload size and batch output size are capped to avoid
  exhausting memory.

### Installer authenticity (unsigned builds)

Omnivert installers are currently **not code-signed**. This means:

- Windows SmartScreen may warn on first run (see the README for the
  "More info → Run anyway" workaround).
- As an interim integrity measure, every release publishes a **`SHA256SUMS`** file. You can
  verify a download by comparing its SHA-256 hash against that file:

  ```powershell
  Get-FileHash .\Omnivert-Setup-<version>.exe -Algorithm SHA256
  ```

  Note: a published checksum protects against **corruption and tampering in transit**, but
  it is not a substitute for a cryptographic signature, and it does not, on its own, prove
  authorship.

**How the in-app updater uses that file.** When you apply an update, the app resolves the
release asset itself; nothing in the request chooses what is downloaded. The asset must be a
release of the repository **this build was made from**, not the one in Settings: the "update
repository" setting can point the *check* anywhere, but installing is pinned, because a host
check like "must be on github.com" says nothing about who published the release, and a
release's `SHA256SUMS` is written by whoever published it. Its SHA-256 must then match that
file, and a missing, unreadable, or non-matching checksum **stops the update** rather than
being skipped.

Be clear about what that does and does not prove. Together they establish that the bytes came
from this project's own releases and arrived intact. They do **not** prove who published the
release, because the checksum and the file come from the same place. That still needs a code
signature.

One narrower path remains: on a development or `pip`-installed copy (not the packaged
Windows build), an update installs a release **wheel** by handing its URL to `pip`. That URL
is pinned to the same repository and `pip` verifies TLS, but the wheel's checksum is not
independently confirmed the way the installer's is.

> **Planned follow-up:** Authenticode / Azure Trusted Signing of the installer and binaries.
> This is the real fix for installer authenticity and SmartScreen reputation, and is tracked
> as a post-launch item.

### Secrets at rest

API keys you enter in Settings (Claude, Azure) are stored in plaintext at:

```text
%LOCALAPPDATA%\Omnivert\settings.json
```

- This file is **never committed** (it is gitignored) and the API **redacts** secrets when
  reading settings back to the UI.
- Because it is plaintext on disk, treat it like any other credential file: don't share it,
  don't paste it into logs, and be cautious if your user profile is synced to the cloud.

> **Planned follow-up:** OS-level encryption of stored secrets (Windows DPAPI) so keys are
> not readable as plaintext at rest.
