"""Installer-based update helpers for frozen Windows builds."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from .build_info import DEFAULT_APP_REPO

# Re-derived here rather than imported from app_updates, on purpose: this module writes an
# executable and then launches it, so it checks for itself rather than trusting that its
# caller checked. Both come from the same build_info constant, so they cannot disagree.
_RELEASE_DOWNLOAD_PREFIX = f"https://github.com/{DEFAULT_APP_REPO}/releases/download/"


def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of a file (read in chunks)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_installer(download_url: str, expected_sha256: str) -> Path:
    """Download a release Setup.exe to a temporary directory and verify it.

    Both arguments are required and both are gates. ``expected_sha256`` used to be optional,
    and an absent one meant the file was launched unverified.

    The hash is also what covers the redirect: ``urlopen`` follows GitHub's 302 to
    objects.githubusercontent.com, and this code never sees the final host, so the bytes are
    trustworthy only because their hash has to match the one the release published. A mismatch
    leaves nothing on disk that could be launched.

    What this still does not establish is publisher authenticity: the URL prefix says the file
    came from this project's releases and the checksum says it arrived intact, but a checksum
    read from the same release as the file it describes cannot say who published that release.
    That needs a signed installer (see SECURITY.md)."""
    if not download_url:
        raise ValueError("No installer URL provided.")
    if not expected_sha256 or not expected_sha256.strip():
        raise ValueError("No published checksum for this installer, so it was not downloaded.")
    if not str(download_url).lower().startswith(_RELEASE_DOWNLOAD_PREFIX.lower()):
        # Pins scheme, host AND repository in one test. A host-only check would accept any
        # GitHub account's release, and urlopen speaks file: and ftp: as happily as https.
        raise ValueError(
            f"Installers are only downloaded from {DEFAULT_APP_REPO}'s GitHub releases."
        )
    # Via urlparse, not Path: a query string would otherwise land in the filename.
    name = Path(urlparse(download_url).path).name or "Omnivert-Setup.exe"
    if not name.lower().endswith(".exe"):
        raise ValueError("The selected release asset is not a Windows installer.")

    target_dir = Path(tempfile.mkdtemp(prefix="omnivert-update-"))
    target = target_dir / name
    with urllib.request.urlopen(download_url, timeout=120) as response:
        target.write_bytes(response.read())
    if target.stat().st_size == 0:
        raise ValueError("Downloaded installer is empty.")

    actual = sha256_file(target)
    if actual.lower() != expected_sha256.strip().lower():
        target.unlink(missing_ok=True)
        raise ValueError(
            "Downloaded installer failed its checksum verification "
            "(expected and actual SHA-256 differ). The download was not applied."
        )
    return target


def launch_installer(path: Path) -> None:
    """Launch the installer detached so it can replace the running app."""
    if not path.is_file():
        raise FileNotFoundError(path)
    subprocess.Popen([str(path)], close_fds=True)
