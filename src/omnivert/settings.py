"""Local settings storage for Omnivert.

Settings (including API keys) live in a JSON file under the user's local app-data
directory. Keys are stored in plaintext locally but are always **redacted** before being
returned over the API (see ``redact``). Nothing here is ever logged.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from .build_info import DEFAULT_APP_REPO

# Default Claude model used for image captioning via the OpenAI-compatible endpoint.
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"
DEFAULT_CLAUDE_BASE_URL = "https://api.anthropic.com/v1/"

DEFAULTS: Dict[str, Any] = {
    # Azure Document Intelligence
    "docintel_endpoint": "",
    "docintel_key": "",
    "docintel_api_version": "",
    "docintel_file_types": [],  # comma list in UI -> list here; empty = auto/all
    # Azure Content Understanding
    "cu_endpoint": "",
    "cu_key": "",
    "cu_analyzer_id": "",
    "cu_file_types": [],  # comma list in UI -> list here; empty = auto/all
    # Claude (image captioning, via OpenAI-compatible client)
    "claude_api_key": "",
    "claude_model": DEFAULT_CLAUDE_MODEL,
    "claude_base_url": DEFAULT_CLAUDE_BASE_URL,
    "llm_prompt": "",
    # misc converter knobs
    "exiftool_path": "",
    "style_map": "",
    # UI defaults
    "default_keep_data_uris": False,
    "default_enable_plugins": False,
    "default_describe_images": False,
    "default_azure_backend": "none",
    "theme": "system",
    # App self-update (see app_updates.py). Repo is "owner/repo"; blank = not configured.
    "app_repo": DEFAULT_APP_REPO,
    "auto_check_updates": True,
    "skipped_app_version": "",
}

# Fields treated as secrets: redacted on read, and left unchanged on write if the
# incoming value is the redaction sentinel.
SECRET_FIELDS = ("docintel_key", "cu_key", "claude_api_key")
REDACTED = "__REDACTED__"

# --- the settings that are not merely configuration ----------------------------------
#
# Most of DEFAULTS is inert: a bad value produces a bad conversion. Four are not, because
# they decide what code runs and where a key goes, and the API that writes them has no
# authentication:
#
#   exiftool_path  is handed to the engine, which calls subprocess.run([it, "-ver"]). A
#                  request could name any program and the next image conversion ran it.
#                  Demonstrated with a batch file that wrote a marker as the logged-in user.
#   claude_base_url, docintel_endpoint, cu_endpoint  decide which server receives the
#                  matching API key. Redacting secrets on read does not help: repointing the
#                  URL makes the app hand the real key over on the next conversion.
#
# What the checks below buy, stated exactly. exiftool must now be a real local file actually
# named exiftool, so an attacker cannot simply name a payload, and a UNC path is refused so
# the binary cannot live on someone else's share. Endpoints must be https, or http only on
# loopback for a local gateway, so a key can no longer be sent in plaintext to an arbitrary
# host. What they do NOT buy: someone who can write settings can still point an endpoint at
# an https host they control, and could still plant a file named exiftool.exe somewhere
# writable. Narrowing is not closing. The per-session token in SECURITY.md is the fix, and
# these checks are what is worth doing without rewriting the trust model.

# The rule is "a file that looks like ExifTool", not one exact spelling. The official
# Windows download from exiftool.org is named ``exiftool(-k).exe``, users are told to rename
# it and plenty do not, and versioned builds carry a suffix. Requiring one literal name
# would refuse the most common real installation.
#
# Be honest about what this buys: it stops a request naming cmd.exe, powershell.exe or a
# dropped payload, which is the attack. It does not prove the file is genuinely ExifTool,
# because an attacker who can already write a file could name it exiftool-x.exe. Proving
# authorship is not something a path check can do; the per-session token is.
_EXIFTOOL_PREFIX = "exiftool"
_EXIFTOOL_SUFFIX = ".exe"
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
ENDPOINT_FIELDS = ("claude_base_url", "docintel_endpoint", "cu_endpoint")


class SettingsError(ValueError):
    """A settings value the app refuses to store. Surfaced to the caller as a 422."""


def validate_exiftool_path(value: Any) -> str:
    """Return a usable ``exiftool_path``, or raise ``SettingsError``. Empty means unset.

    Order matters here. Everything lexical happens before anything touches the filesystem,
    because a UNC path that reaches ``is_file()`` makes this process open an SMB or WebDAV
    connection to a host the caller named: an NTLM-hash-leak primitive, and a blocking call
    that hangs the request while it times out. Refusing it lexically means the network is
    never touched.

    The UNC test runs on the NORMALISED path, not the raw string. Windows folds ``/`` and
    ``\\`` together before classifying, so ``/\\host\\share\\exiftool.exe`` and
    ``\\/host/share/exiftool.exe`` are the same UNC path to the OS while starting with
    neither ``\\\\`` nor ``//``. A review demonstrated both, and demonstrated CreateProcess
    executing through the mixed spelling. ``os.path.abspath`` is purely lexical (it calls
    GetFullPathNameW and touches no filesystem), so normalising first is free.
    """
    text = str(value or "").strip().strip('"')
    if not text:
        return ""
    if not Path(text).is_absolute():
        # Checked on the raw value: abspath would resolve a relative path against the
        # working directory and make it look absolute.
        raise SettingsError(
            "The ExifTool path must be a full path, for example C:\\Tools\\exiftool.exe."
        )
    resolved = Path(os.path.abspath(text))
    if resolved.drive.startswith("\\\\") or resolved.drive.startswith("//"):
        raise SettingsError(
            "The ExifTool path cannot be a network path. Point it at a copy of ExifTool on "
            "this machine."
        )
    name = resolved.name.lower()
    if not (name.startswith(_EXIFTOOL_PREFIX) and name.endswith(_EXIFTOOL_SUFFIX)):
        raise SettingsError(
            "That does not look like ExifTool. The file name must start with 'exiftool' and "
            "end in '.exe' (the official download is exiftool(-k).exe), because Omnivert "
            "runs this file as a program when it reads image metadata."
        )
    if not resolved.is_file():
        raise SettingsError(
            f"No file at {resolved}. Check the path, or leave it blank to skip ExifTool."
        )
    return str(resolved)


def validate_endpoint(field: str, value: Any) -> str:
    """Return a usable endpoint URL, or raise ``SettingsError``. Empty means unset."""
    text = str(value or "").strip()
    if not text:
        return ""
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text):
        # urlsplit silently strips tabs and leading C0 controls, so "ht\ttps://..." parses
        # as https and stores clean. Refuse it rather than store something that reads as one
        # URL here and another to the HTTP client.
        raise SettingsError(f"{field} contains characters that are not allowed in a URL.")
    try:
        parsed = urlparse(text)
        parsed.port  # raises on a non-numeric or out-of-range port
    except ValueError as exc:
        raise SettingsError(f"{field} is not a valid URL.") from exc
    host = (parsed.hostname or "").lower()
    if not host:
        raise SettingsError(f"{field} needs a full URL including the host, for example https://example.com/v1/.")
    if "@" in parsed.netloc:
        raise SettingsError(f"{field} must not contain a username or password.")
    if parsed.scheme == "https":
        return text
    if parsed.scheme == "http" and host in _LOOPBACK_HOSTS:
        return text  # a gateway running on this machine
    raise SettingsError(
        f"{field} must be an https URL. Plain http is only accepted on this machine "
        "(localhost), because this address is where your API key is sent."
    )


def validate(incoming: Dict[str, Any], current: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return ``incoming`` with the non-inert fields checked. Raises ``SettingsError``.

    Applied on write rather than on read: ``load`` must keep returning whatever is on disk so
    a settings file written by an older build still opens. ``conversion._construct`` re-checks
    at the point of use, so a legacy value is refused there rather than reaching the engine.

    Only fields whose value actually CHANGED are checked, which is why ``current`` exists.
    The Settings dialog posts the entire draft on every save, so validating the whole payload
    meant one legacy ExifTool path made every save fail: a user could not change their theme
    or paste an API key until they noticed a toast about a field they had not touched. You
    still cannot SET a bad value, which is the part that matters; an existing one is inert,
    because the point-of-use checks refuse or drop it.
    """
    current = current or {}
    checked = dict(incoming)

    def changed(field: str) -> bool:
        return field in checked and checked[field] != current.get(field)

    if changed("exiftool_path"):
        checked["exiftool_path"] = validate_exiftool_path(checked["exiftool_path"])
    for field in ENDPOINT_FIELDS:
        if changed(field):
            checked[field] = validate_endpoint(field, checked[field])
    return checked


def settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "Omnivert" / "settings.json"


def load() -> Dict[str, Any]:
    """Return the full settings dict (with secrets), falling back to defaults."""
    data = deepcopy(DEFAULTS)
    path = settings_path()
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                for key in stored:
                    if key not in DEFAULTS:
                        continue
                    if key == "app_repo" and DEFAULT_APP_REPO and not stored[key]:
                        continue
                    data[key] = stored[key]
        except (json.JSONDecodeError, OSError):
            pass
    return data


def save(incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge ``incoming`` into stored settings and persist. Secret fields whose value
    is the redaction sentinel (or empty) are left at their current stored value so the
    UI can submit redacted values back without wiping the real key."""
    current = load()
    incoming = validate(incoming, current)
    for key, value in incoming.items():
        if key not in DEFAULTS:
            continue
        if key in SECRET_FIELDS and value in (REDACTED, None, ""):
            continue  # keep existing secret
        current[key] = value
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current


def redact(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy safe to send over the API: secrets replaced with a sentinel, plus
    ``has_<field>`` booleans so the UI can show whether a key is set."""
    out = deepcopy(data)
    for field in SECRET_FIELDS:
        has = bool(out.get(field))
        out[field] = REDACTED if has else ""
        out[f"has_{field}"] = has
    return out
