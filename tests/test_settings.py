"""Settings storage, and the redaction that keeps API keys off the wire.

``GET /api/settings`` returns whatever ``redact`` produces, so a regression here leaks the
user's Claude and Azure keys to any client that can reach the local API. That made this the
first thing worth pinning down in tests.
"""

from __future__ import annotations

import json

from omnivert import settings as settings_module
from omnivert.settings import REDACTED, SECRET_FIELDS


def test_defaults_load_when_no_file_exists(isolated_settings):
    cfg = settings_module.load()
    assert cfg["claude_model"] == settings_module.DEFAULT_CLAUDE_MODEL
    assert cfg["docintel_file_types"] == []


def test_redact_replaces_every_secret_and_reports_presence(isolated_settings):
    settings_module.save({"claude_api_key": "sk-ant-real-secret", "cu_key": "azure-real-secret"})
    redacted = settings_module.redact(settings_module.load())

    for field in SECRET_FIELDS:
        assert redacted[field] in (REDACTED, ""), f"{field} was not redacted"
        assert f"has_{field}" in redacted

    assert redacted["has_claude_api_key"] is True
    assert redacted["has_cu_key"] is True
    assert redacted["has_docintel_key"] is False

    # The real values must not survive anywhere in the payload, under any key.
    blob = json.dumps(redacted)
    assert "sk-ant-real-secret" not in blob
    assert "azure-real-secret" not in blob


def test_saving_the_redaction_sentinel_keeps_the_stored_key(isolated_settings):
    """The UI submits back what it was given, so a redacted value must not wipe the key."""
    settings_module.save({"claude_api_key": "sk-ant-original"})
    settings_module.save({"claude_api_key": REDACTED, "claude_model": "claude-opus-5"})

    cfg = settings_module.load()
    assert cfg["claude_api_key"] == "sk-ant-original"
    assert cfg["claude_model"] == "claude-opus-5"


def test_blank_secret_also_keeps_the_stored_key(isolated_settings):
    settings_module.save({"docintel_key": "azure-original"})
    settings_module.save({"docintel_key": ""})
    assert settings_module.load()["docintel_key"] == "azure-original"


def test_unknown_keys_are_ignored(isolated_settings):
    settings_module.save({"not_a_real_setting": "x", "theme": "dark"})
    cfg = settings_module.load()
    assert "not_a_real_setting" not in cfg
    assert cfg["theme"] == "dark"


def test_corrupt_settings_file_falls_back_to_defaults(isolated_settings):
    isolated_settings.parent.mkdir(parents=True, exist_ok=True)
    isolated_settings.write_text("{ this is not json", encoding="utf-8")
    assert settings_module.load()["theme"] == "system"


def test_file_types_round_trip_as_lists(isolated_settings):
    settings_module.save({"docintel_file_types": [".pdf", "PNG"], "cu_file_types": [".docx"]})
    cfg = settings_module.load()
    assert cfg["docintel_file_types"] == [".pdf", "PNG"]
    assert cfg["cu_file_types"] == [".docx"]
