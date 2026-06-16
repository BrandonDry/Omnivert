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

from .build_info import DEFAULT_APP_REPO

# Default Claude model used for image captioning via the OpenAI-compatible endpoint.
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"
DEFAULT_CLAUDE_BASE_URL = "https://api.anthropic.com/v1/"

DEFAULTS: Dict[str, Any] = {
    # Azure Document Intelligence
    "docintel_endpoint": "",
    "docintel_key": "",
    "docintel_api_version": "",
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
