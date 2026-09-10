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

_EXIFTOOL_NAMES = {"exiftool", "exiftool.exe"}
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
ENDPOINT_FIELDS = ("claude_base_url", "docintel_endpoint", "cu_endpoint")


class SettingsError(ValueError):
    """A settings value the app refuses to store. Surfaced to the caller as a 422."""


def validate_exiftool_path(value: Any) -> str:
    """Return a usable ``exiftool_path``, or raise ``SettingsError``. Empty means unset."""
    text = str(value or "").strip().strip('"')
    if not text:
        return ""
    path = Path(text)
    if text.startswith("\\\\") or text.startswith("//"):
        raise SettingsError(
            "The ExifTool path cannot be a network (UNC) path. Point it at a copy of "
            "ExifTool on this machine."
        )
    if not path.is_absolute():
        raise SettingsError("The ExifTool path must be a full path, for example C:\\Tools\\exiftool.exe.")
    if path.name.lower() not in _EXIFTOOL_NAMES:
        raise SettingsError(
            "That is not ExifTool. The path must end in exiftool.exe, because Omnivert runs "
            "this file as a program when it reads image metadata."
        )
    if not path.is_file():
        raise SettingsError(f"No file at {text}. Check the path, or leave it blank to skip ExifTool.")
    return text


def validate_endpoint(field: str, value: Any) -> str:
    """Return a usable endpoint URL, or raise ``SettingsError``. Empty means unset."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = urlparse(text)
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


def validate(incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Return ``incoming`` with the non-inert fields checked. Raises ``SettingsError``.

    Applied on write rather than on read: ``load`` must keep returning whatever is on disk so
    a settings file written by an older build still opens. ``conversion._construct`` re-checks
    at the point of use, so a legacy value stored before these checks existed is refused there
    instead of being handed to the engine.
    """
    checked = dict(incoming)
    if "exiftool_path" in checked:
        checked["exiftool_path"] = validate_exiftool_path(checked["exiftool_path"])
    for field in ENDPOINT_FIELDS:
        if field in checked:
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
    incoming = validate(incoming)
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
