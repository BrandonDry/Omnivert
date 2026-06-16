"""Installer-based update helpers for frozen Windows builds."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of a file (read in chunks)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_installer(download_url: str, expected_sha256: Optional[str] = None) -> Path:
    """Download a release Setup.exe to a temporary directory.

    If ``expected_sha256`` is given (from the release's SHA256SUMS asset), the download is
    verified before it is returned, and a mismatch raises. This catches a corrupted or
    in-transit-tampered download; it does **not** establish publisher authenticity — that
    needs a signed installer (see SECURITY.md)."""
    if not download_url:
        raise ValueError("No installer URL provided.")
    parsed = urlparse(download_url)
    name = Path(parsed.path).name or "Omnivert-Setup.exe"
    if not name.lower().endswith(".exe"):
        raise ValueError("The selected release asset is not a Windows installer.")

    target_dir = Path(tempfile.mkdtemp(prefix="omnivert-update-"))
    target = target_dir / name
    with urllib.request.urlopen(download_url, timeout=120) as response:
        target.write_bytes(response.read())
    if target.stat().st_size == 0:
        raise ValueError("Downloaded installer is empty.")

    if expected_sha256:
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
