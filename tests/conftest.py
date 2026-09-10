r"""Shared fixtures.

Every test that touches settings must be isolated from the real user profile: the settings
file lives under %LOCALAPPDATA%\Omnivert, and a test that wrote there would clobber the
developer's own saved API keys.
"""

from __future__ import annotations

import pytest

from omnivert import settings as settings_module


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Point settings storage at a temp dir and return the path it will use."""
    target = tmp_path / "Omnivert" / "settings.json"
    monkeypatch.setattr(settings_module, "settings_path", lambda: target)
    return target
