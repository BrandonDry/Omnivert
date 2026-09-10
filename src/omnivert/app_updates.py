"""Self-update for Omnivert from the developer's GitHub Releases.

The check path is shared by dev and frozen builds. Applying an update is runtime-aware:
dev/package installs can use a release wheel via pip, while PyInstaller-frozen Windows
builds download and launch the release ``Setup.exe``.
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from . import gh
from . import installer_update
from . import settings as settings_module
from .app_version import __version__ as APP_VERSION
from .build_info import DEFAULT_APP_REPO

# The distribution name the app is published under (Phase B packaging).
APP_PACKAGE = "omnivert"


def release_asset_prefix() -> str:
    """The only URL prefix an asset this build will install may have.

    Deliberately the repo this build was made from, not the repo in Settings. ``app_repo`` is
    a free-text field the user can edit (and any client that can reach the API can write), so
    a host-level "must be github.com" check does not say WHOSE release is being installed:
    every GitHub account serves assets from github.com, and a release's SHA256SUMS is written
    by whoever published that release, so the checksum matches an attacker's binary by
    construction. Pointing Settings at a fork can therefore still CHECK for updates; only
    installing is pinned. ``release.yml`` rewrites DEFAULT_APP_REPO to the repo it builds
    from (``scripts/set_build_repo.py``), so a fork that ships its own releases updates from
    its own, not from here.

    This bounds provenance, not authenticity: it says the bytes came from this project's
    releases, not that this project published them. That still needs a signed installer.
    """
    return f"https://github.com/{DEFAULT_APP_REPO}/releases/download/"


def release_asset_allowed(url: str) -> bool:
    """True when ``url`` is a release asset of the repo this build updates from.

    A prefix test works because the prefix ends inside a path GitHub controls: nobody but
    ``DEFAULT_APP_REPO`` can serve a URL under ``github.com/<that repo>/releases/download/``.
    It only works on a path that cannot climb back out of that prefix, so ``..`` is refused
    outright. A bare prefix test accepted
    ``.../releases/download/../../../attacker/evil/x.exe``, which is not reachable through a
    real asset URL (GitHub builds it, and a git ref cannot contain ``..``) but is a weaker
    check than it reads as, on the one gate that decides which executable gets launched.
    """
    text = str(url or "")
    if not text or ".." in text:
        return False
    return text.lower().startswith(release_asset_prefix().lower())

_lock = threading.Lock()
_state: Dict[str, object] = {
    "state": "idle",  # idle | running | success | error
    "message": None,
    "output": None,
    "old_version": None,
    "new_version": None,
    "restart_required": False,
}


# --- config --------------------------------------------------------------------------

# The shape GitHub actually allows for an owner and a repository name. Checked rather than
# counted: the old test accepted anything holding exactly one slash, so a value such as
# "a/..%2Fb" was interpolated straight into an api.github.com path. It could not escape the
# host and GitHub answered 404, but a settings field that becomes part of a URL should be
# shaped like the thing it claims to be.
_REPO_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?/[A-Za-z0-9._-]{1,100}$"
)


def _repo() -> Optional[str]:
    repo = (settings_module.load().get("app_repo") or "").strip().strip("/")
    # Accept "owner/repo"; ignore blanks and the placeholder default.
    if repo and _REPO_RE.match(repo) and repo.lower() != "owner/repo":
        return repo
    return None


# --- check ---------------------------------------------------------------------------

def _wheel_asset(release: dict) -> Optional[str]:
    for asset in release.get("assets") or []:
        name = (asset.get("name") or "").lower()
        if name.endswith(".whl"):
            return asset.get("browser_download_url")
    return None


def _installer_asset(release: dict) -> Optional[str]:
    for asset in release.get("assets") or []:
        name = (asset.get("name") or "").lower()
        if name.endswith(".exe") and "omnivert" in name and "setup" in name:
            return asset.get("browser_download_url")
    return None


def _checksums_asset(release: dict) -> Optional[str]:
    for asset in release.get("assets") or []:
        if (asset.get("name") or "").lower() == "sha256sums":
            return asset.get("browser_download_url")
    return None


def _sha256_from_sums(text: str, filename: str) -> str:
    """Pull ``filename``'s hash out of a SHA256SUMS body (``<hex>  <filename>`` lines).

    Raises when the file is not listed. It used to return None there and the caller carried
    on unverified, which meant the checksum only protected downloads that had volunteered to
    be protected: any name absent from SHA256SUMS skipped the check entirely.
    """
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*").lower() == filename.lower():
            return parts[0]
    raise RuntimeError(
        f"The release's SHA256SUMS does not list {filename}, so the download cannot be "
        "verified. Nothing was installed."
    )


def _expected_sha256(filename: str) -> str:
    """Look up ``filename``'s SHA-256 in the latest release's SHA256SUMS asset.

    Every failure raises. A checksum that can be skipped is not a check, and this one guards
    an executable that gets launched.
    """
    repo = _repo()
    if not repo:
        raise RuntimeError("No update repository is configured, so nothing can be verified.")
    try:
        rel = gh.get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    except Exception as exc:  # noqa: BLE001 - reported to the UI as a refusal to install
        raise RuntimeError(f"Couldn't read the release to verify the download: {exc}") from exc

    url = _checksums_asset(rel)
    if not url:
        raise RuntimeError(
            "This release publishes no SHA256SUMS, so the download cannot be verified."
        )
    if not release_asset_allowed(url):
        # The checksums decide whether the installer runs, so they have to come from the same
        # pinned repo the installer does. A SHA256SUMS fetched from anywhere else could simply
        # list the hash of the attacker's own binary.
        raise RuntimeError(f"The release's SHA256SUMS is not published by {DEFAULT_APP_REPO}.")

    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            text = resp.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 - reported to the UI as a refusal to install
        raise RuntimeError(f"Couldn't download the release's SHA256SUMS: {exc}") from exc
    return _sha256_from_sums(text, filename)


def check_for_app_update() -> Dict[str, object]:
    checked_at = datetime.now(timezone.utc).isoformat()
    repo = _repo()
    base = {
        "configured": repo is not None,
        "installed": APP_VERSION,
        "latest": None,
        "update_available": False,
        "repo": repo,
        "release_notes": None,
        "release_url": None,
            "download_url": None,
            "installer_url": None,
        "published_at": None,
        "error": None,
        "checked_at": checked_at,
    }
    if repo is None:
        return base
    try:
        rel = gh.get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    except Exception as exc:
        base["error"] = f"Couldn't reach GitHub: {exc}"
        base["release_url"] = f"https://github.com/{repo}/releases"
        return base

    tag = (rel.get("tag_name") or "").strip()
    latest = tag[1:] if tag[:1].lower() == "v" else tag
    base.update(
        {
            "latest": latest or None,
            "update_available": gh.is_newer(latest, APP_VERSION),
            "release_notes": rel.get("body") or None,
            "release_url": rel.get("html_url") or f"https://github.com/{repo}/releases",
            "download_url": _installer_asset(rel) if is_frozen() else _wheel_asset(rel),
            "installer_url": _installer_asset(rel),
            "published_at": rel.get("published_at"),
        }
    )
    return base


# --- install -------------------------------------------------------------------------

def get_status() -> Dict[str, object]:
    with _lock:
        return dict(_state)


def _editable_install() -> bool:
    """True when the app is installed in editable/dev mode (``pip install -e``)."""
    try:
        text = metadata.distribution(APP_PACKAGE).read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return False
    except Exception:
        return False
    if not text:
        return False
    import json

    try:
        return bool(json.loads(text).get("dir_info", {}).get("editable"))
    except Exception:
        return False


def _packaged() -> bool:
    try:
        metadata.version(APP_PACKAGE)
        return True
    except metadata.PackageNotFoundError:
        return False


def start_app_update() -> Dict[str, object]:
    """Kick off the update in a daemon thread.

    Takes no URL. It used to take one from the request body, and the server downloaded and
    launched whatever it named: an unauthenticated local endpoint that ran an attacker-chosen
    executable, with no allowlist, no scheme restriction (urlopen honours ``file:`` and
    ``ftp:``) and a checksum that could be sidestepped by naming a file SHA256SUMS did not
    list. The asset is resolved here instead, and it must be a release of the repo this build
    was made from (``release_asset_prefix``) before anything is fetched.
    ``AppUpdateApplyRequest.download_url`` still exists so an already-installed frontend keeps
    working, but nothing reads it.
    """
    # Claim the slot before the network call below, not after. Resolving the asset here means
    # a GitHub round trip now sits between "is one already running" and "mark one running",
    # and two clicks inside that window would launch two installers.
    with _lock:
        if _state["state"] == "running":
            return dict(_state)
        _state.update(
            {
                "state": "running",
                "message": "Checking for the latest release...",
                "output": None,
                "old_version": APP_VERSION,
                "new_version": None,
                "restart_required": False,
            }
        )

    # The slot is claimed, so nothing below may escape as an exception. If it did, the state
    # would stay "running" for the life of the process and every later apply would return the
    # early "one is already running" answer, leaving the updater wedged with no way back short
    # of restarting the app. _fail moves the state to error, which frees the slot.
    try:
        return _resolve_and_start()
    except Exception as exc:  # noqa: BLE001 - a wedged updater is worse than an ugly message
        return _fail(f"Couldn't start the update: {exc}")


def _resolve_and_start() -> Dict[str, object]:
    """Resolve the release asset and hand it to the right installer path.

    Split out of ``start_app_update`` only so the slot claim there can wrap all of it in one
    try. Never call this directly: it assumes the slot is already claimed.
    """
    info = check_for_app_update()
    if info.get("error"):
        return _fail(str(info["error"]))
    if not info.get("configured"):
        return _fail("No update repository is configured, so there is nothing to install.")
    if not info.get("update_available"):
        # The frontend already gates on this, but the frontend is not the security boundary:
        # a same-origin POST straight to the route would otherwise re-download and launch the
        # CURRENT release's installer on a machine already running it. Repo-pinned and
        # checksum-verified, so this is not a code-execution hole, but an unauthenticated
        # local trigger for an installer launch is still not something to leave open.
        return _fail("This build is already up to date, so there is nothing to install.")
    download_url = info.get("download_url")
    if download_url and not release_asset_allowed(str(download_url)):
        return _fail(
            f"That release is not published by {DEFAULT_APP_REPO}, which is the repository "
            "this build installs updates from. Nothing was downloaded."
        )

    if is_frozen():
        if not download_url:
            return _fail("This release has no Windows Setup.exe attached yet.")
        with _lock:
            _state.update(
                {
                    "state": "running",
                    "message": "Downloading the installer...",
                    "output": None,
                    "old_version": APP_VERSION,
                    "new_version": None,
                    "restart_required": False,
                }
            )
        threading.Thread(
            target=_run_installer_update, args=(str(download_url),), daemon=True
        ).start()
        return get_status()

    if not download_url:
        return _fail("This release has no installable wheel attached yet.")
    if not _packaged():
        return _fail(
            "This copy isn't installed as a package, so it can't self-update. "
            "Update it the way it was installed (e.g. git pull), or use a packaged release."
        )
    if _editable_install():
        return _fail("You're on a development checkout. Update with git instead of pip.")

    with _lock:
        _state.update(
            {
                "state": "running",
                "message": "Downloading and installing the update…",
                "output": None,
                "old_version": APP_VERSION,
                "new_version": None,
                "restart_required": False,
            }
        )
    # The wheel path hands the URL to pip rather than downloading it here, so the guarantee
    # is narrower than the installer path's: the allowlist above plus pip's own TLS
    # verification, with no checksum. Named in SECURITY.md as the residual it is.
    threading.Thread(target=_run_install, args=(str(download_url),), daemon=True).start()
    return get_status()


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _fail(message: str) -> Dict[str, object]:
    with _lock:
        _state.update(
            {"state": "error", "message": message, "output": None,
             "old_version": APP_VERSION, "new_version": None, "restart_required": False}
        )
    return get_status()


def _installed_dist_version() -> Optional[str]:
    """Read the freshly-installed dist version from a child interpreter (this process's
    metadata cache is stale until restart)."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c",
             f"import importlib.metadata as m; print(m.version('{APP_PACKAGE}'))"],
            capture_output=True, text=True, timeout=30,
        )
        return proc.stdout.strip() or None
    except Exception:
        return None


def _run_install(download_url: str) -> None:
    cmd: List[str] = [
        sys.executable, "-m", "pip", "install", "--upgrade",
        "--upgrade-strategy", "only-if-needed", download_url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
        ok = proc.returncode == 0
        with _lock:
            _state.update(
                {
                    "state": "success" if ok else "error",
                    "message": (
                        "Update installed. Restart Omnivert to finish."
                        if ok
                        else "Update failed, see details below."
                    ),
                    "output": output[-8000:],
                    "new_version": _installed_dist_version() if ok else APP_VERSION,
                    "restart_required": ok,
                }
            )
    except subprocess.TimeoutExpired:
        with _lock:
            _state.update({"state": "error", "message": "Update timed out after 15 minutes.",
                           "output": None, "restart_required": False})
    except Exception as exc:  # noqa: BLE001 - reported to the UI
        with _lock:
            _state.update({"state": "error", "message": f"Update failed: {exc}",
                           "output": None, "restart_required": False})


def _run_installer_update(download_url: str) -> None:
    try:
        filename = Path(urlparse(download_url).path).name
        if not filename:
            raise RuntimeError("The release asset URL names no file.")
        expected = _expected_sha256(filename)
        installer_path = installer_update.download_installer(download_url, expected)
        installer_update.launch_installer(installer_path)
        with _lock:
            _state.update(
                {
                    "state": "success",
                    "message": (
                        "Installer launched. Close Omnivert if Windows does not "
                        "close it automatically."
                    ),
                    "output": str(installer_path),
                    "new_version": None,
                    "restart_required": True,
                }
            )
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI
        with _lock:
            _state.update(
                {
                    "state": "error",
                    "message": f"Installer update failed: {exc}",
                    "output": None,
                    "restart_required": False,
                }
            )
