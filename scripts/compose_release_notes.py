"""Compose Omnivert release notes that surface the bundled conversion engine's changelog.

Frozen users act on the *app* update prompt, so the app release notes must explain what the
bundled engine actually changed — not just "Bundle conversion engine X". This reads the pinned
markitdown version from pyproject.toml, fetches that version's upstream release body from
GitHub, and writes a Markdown notes file. The release workflow uses it as the release body and
lets GitHub append the auto-generated commit notes below.

Standalone (stdlib only) so it can run at any point in the release job. Honors GITHUB_TOKEN to
avoid unauthenticated GitHub API rate limits on shared Actions runners.

The microsoft/markitdown monorepo tags releases like ``markitdown-0.1.6`` (not ``v0.1.6``), so
we match the version as a substring of the tag — same approach as
``omnivert.updates._github_notes``.

Usage: python scripts/compose_release_notes.py [output_path]
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASES_API = "https://api.github.com/repos/microsoft/markitdown/releases"
RELEASES_PAGE = "https://github.com/microsoft/markitdown/releases"

DISCLAIMER = (
    "> Omnivert is an independent project and is not affiliated with, or endorsed by, "
    "Microsoft. The bundled MarkItDown engine is © Microsoft Corporation (MIT)."
)


def _engine_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'markitdown\[[^\]]+\]==([^"]+)', text)
    if not match:
        raise SystemExit("Could not find pinned conversion engine version.")
    return match.group(1)


def _get_json(url: str):
    headers = {"User-Agent": "Omnivert-Release", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _upstream(version: str) -> tuple[str | None, str]:
    """Return (release_body, release_url) for the matching markitdown release."""
    try:
        releases = _get_json(RELEASES_API)
    except Exception:
        return None, RELEASES_PAGE
    if isinstance(releases, list):
        for rel in releases:
            if version in (rel.get("tag_name") or ""):
                return (rel.get("body") or None), (rel.get("html_url") or RELEASES_PAGE)
    return None, RELEASES_PAGE


def main() -> None:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "dist" / "release-notes.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    version = _engine_version()
    body, url = _upstream(version)

    lines = [
        "## Conversion engine",
        "",
        f"This release bundles **Microsoft MarkItDown `{version}`**.",
        "",
    ]
    if body:
        lines += ["### What's new in MarkItDown", "", body.strip(), ""]
    lines += [f"[MarkItDown `{version}` release notes]({url})", "", DISCLAIMER, ""]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote release notes for engine {version} -> {out_path}")


if __name__ == "__main__":
    main()
