"""Installer-based update helpers for frozen Windows builds."""

from __future__ import annotations

import subprocess
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def download_installer(download_url: str) -> Path:
    """Download a release Setup.exe to a temporary directory."""
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
    return target


def launch_installer(path: Path) -> None:
    """Launch the installer detached so it can replace the running app."""
    if not path.is_file():
        raise FileNotFoundError(path)
    subprocess.Popen([str(path)], close_fds=True)
