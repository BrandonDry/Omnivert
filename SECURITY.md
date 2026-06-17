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
fix. Coordinated disclosure is appreciated — please give us a reasonable window to release a
patch before any public discussion.

## Supported versions

Omnivert is pre-1.0 and ships frequent releases. Security fixes target the **latest**
released version. Please update to the newest release before reporting an issue.

## Security model and known limitations

Omnivert runs locally on your machine. A few properties are worth understanding:

- **Local-only API.** The bundled FastAPI backend binds to loopback (`127.0.0.1`) only, and
  the frozen desktop UI is same-origin. There is no remote network listener. As a
  defense-in-depth measure against DNS rebinding, the backend also rejects any request whose
  `Host` header is not a loopback name, so a website cannot reach the local API by pointing
  its own hostname at `127.0.0.1`.
- **Local file access is intentional.** The folder/paths conversion endpoints read the files
  and folders you select (via the native picker or a typed path) so they can be converted to
  Markdown. Reading your own files is the app's purpose; the API does not write to arbitrary
  paths (saving goes through the native save dialog).
- **URL conversion is restricted.** The URL converter accepts only `http`/`https` URLs and
  rejects other schemes (e.g. `file:`) and hosts that resolve to loopback, private, or
  link-local address ranges, to avoid local-file and internal-network access.
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
  it is not a substitute for a cryptographic signature — it does not, on its own, prove
  authorship.

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
