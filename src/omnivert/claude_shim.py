"""Wire the engine's image-captioning LLM hook to Claude.

The engine's image converter calls an OpenAI-style ``client.chat.completions.create``
with a data-URI image. Anthropic exposes an OpenAI-compatible endpoint, so we hand
the engine an ``openai.OpenAI`` client pointed at Anthropic's base URL.
"""

from __future__ import annotations

from typing import Any

from .settings import DEFAULT_CLAUDE_BASE_URL


def build_llm_client(api_key: str, base_url: str | None = None) -> Any:
    """Return an OpenAI-compatible client targeting Anthropic's API.

    Raises ``RuntimeError`` with a friendly message if the ``openai`` package is missing
    or no API key is configured.
    """
    if not api_key:
        raise RuntimeError("No Claude API key configured. Add one in Settings.")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - openai ships with markitdown[all]
        raise RuntimeError(
            "The 'openai' package is required for image captioning but is not installed."
        ) from exc
    return OpenAI(api_key=api_key, base_url=base_url or DEFAULT_CLAUDE_BASE_URL)
