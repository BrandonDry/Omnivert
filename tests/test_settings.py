"""Settings storage, and the redaction that keeps API keys off the wire.

``GET /api/settings`` returns whatever ``redact`` produces, so a regression here leaks the
user's Claude and Azure keys to any client that can reach the local API. That made this the
first thing worth pinning down in tests.
"""

from __future__ import annotations

import json

import pytest

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


# --- the settings that are not merely configuration ---------------------------------
#
# exiftool_path becomes subprocess.run([it, "-ver"]) inside the engine, and the three
# endpoints decide which server receives the matching API key. The API that writes them has
# no authentication, so a request could turn either into something worse than a bad
# conversion. Reproduced before these checks existed: writing exiftool_path and then
# converting any image ran a batch file as the logged-in user.


def test_exiftool_path_must_actually_be_exiftool(isolated_settings, tmp_path):
    payload = tmp_path / "payload.exe"
    payload.write_bytes(b"MZ")
    with pytest.raises(settings_module.SettingsError) as exc:
        settings_module.save({"exiftool_path": str(payload)})
    assert "exiftool" in str(exc.value).lower()
    assert settings_module.load()["exiftool_path"] == "", "the refused value was still stored"


def test_a_real_exiftool_path_is_accepted(isolated_settings, tmp_path):
    tool = tmp_path / "exiftool.exe"
    tool.write_bytes(b"MZ")
    settings_module.save({"exiftool_path": str(tool)})
    assert settings_module.load()["exiftool_path"] == str(tool)


def test_exiftool_path_may_not_live_on_a_network_share(isolated_settings):
    with pytest.raises(settings_module.SettingsError) as exc:
        settings_module.save({"exiftool_path": r"\\attacker\share\exiftool.exe"})
    assert "network" in str(exc.value).lower()


def test_a_missing_exiftool_is_refused_rather_than_stored(isolated_settings, tmp_path):
    with pytest.raises(settings_module.SettingsError):
        settings_module.save({"exiftool_path": str(tmp_path / "nope" / "exiftool.exe")})


def test_clearing_exiftool_path_is_allowed(isolated_settings, tmp_path):
    tool = tmp_path / "exiftool.exe"
    tool.write_bytes(b"MZ")
    settings_module.save({"exiftool_path": str(tool)})
    settings_module.save({"exiftool_path": ""})
    assert settings_module.load()["exiftool_path"] == ""


@pytest.mark.parametrize("field", settings_module.ENDPOINT_FIELDS)
def test_an_endpoint_may_not_be_plain_http_on_another_host(isolated_settings, field):
    """This is the shape that exfiltrated a real key in review: repoint, then convert."""
    with pytest.raises(settings_module.SettingsError) as exc:
        settings_module.save({field: "http://attacker.example/v1/"})
    assert "https" in str(exc.value).lower()


@pytest.mark.parametrize("field", settings_module.ENDPOINT_FIELDS)
def test_an_https_endpoint_is_accepted(isolated_settings, field):
    settings_module.save({field: "https://example.invalid/v1/"})
    assert settings_module.load()[field] == "https://example.invalid/v1/"


def test_a_local_gateway_over_http_is_still_allowed(isolated_settings):
    """Running LiteLLM or similar on this machine is a legitimate setup, and plain http to
    loopback never leaves the box."""
    settings_module.save({"claude_base_url": "http://127.0.0.1:4000/v1/"})
    assert settings_module.load()["claude_base_url"] == "http://127.0.0.1:4000/v1/"


def test_an_endpoint_may_not_carry_credentials(isolated_settings):
    with pytest.raises(settings_module.SettingsError) as exc:
        settings_module.save({"claude_base_url": "https://user:pw@example.invalid/v1/"})
    assert "username" in str(exc.value).lower()


def test_a_refused_value_leaves_every_other_field_untouched(isolated_settings):
    settings_module.save({"theme": "dark"})
    with pytest.raises(settings_module.SettingsError):
        settings_module.save({"theme": "light", "claude_base_url": "ftp://example.invalid/"})
    assert settings_module.load()["theme"] == "dark", "a partial write got through"


def test_a_legacy_value_on_disk_still_loads(isolated_settings):
    """``load`` must not reject: a settings file written before these checks existed has to
    open, or the app is bricked for whoever wrote one. ``conversion._construct`` is what
    refuses it at the point of use."""
    isolated_settings.parent.mkdir(parents=True, exist_ok=True)
    isolated_settings.write_text(
        json.dumps({"exiftool_path": r"C:\evil\payload.exe", "theme": "dark"}), encoding="utf-8"
    )
    cfg = settings_module.load()
    assert cfg["exiftool_path"] == r"C:\evil\payload.exe"
    assert cfg["theme"] == "dark"
