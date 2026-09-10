"""Compose Omnivert release notes: this version's CHANGELOG section, then the bundled
conversion engine's changelog.

Frozen users act on the *app* update prompt, and the release body is what that prompt shows
them (``app_updates.check_for_app_update`` puts it in ``release_notes``, and the update dialog
renders it). So it has to say what OMNIVERT changed, in Omnivert's own words, before it says
what the engine changed. It did not: 0.1.5 shipped a draft whose only mention of the three
security fixes was a pull request title in GitHub's auto-generated list, which is not how a
user decides whether to take a security update. The CHANGELOG section is therefore read
straight out of ``CHANGELOG.md`` and put first.

The engine half then reads the pinned markitdown version from pyproject.toml, fetches that
version's upstream release body from GitHub, and appends it. The release workflow uses the
whole file as the release body and lets GitHub append the auto-generated commit notes below.

Standalone (stdlib only) so it can run at any point in the release job. Honors GITHUB_TOKEN to
avoid unauthenticated GitHub API rate limits on shared Actions runners.

The microsoft/markitdown monorepo tags releases like ``markitdown-0.1.6`` (not ``v0.1.6``), so
we match the version as a substring of the tag, the same approach as
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


def _app_version() -> str:
    text = (ROOT / "src" / "omnivert" / "app_version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__ = "([^"]+)"', text)
    if not match:
        raise SystemExit("Could not find the app version in app_version.py.")
    return match.group(1)


def _changelog_section(version: str) -> str | None:
    """Return the body of ``## [<version>] - <date>`` from CHANGELOG.md, or None.

    Deliberately not fatal when the section is missing: an automated engine bump tags a patch
    release whose CHANGELOG entry a human may not have written yet, and a release that fails
    to build over a missing heading is worse than one whose notes carry only the engine half.
    The engine section below always renders.
    """
    path = ROOT / "CHANGELOG.md"
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    for i, line in enumerate(lines):
        # Match the version exactly, so 0.1.5 never picks up 0.1.15's section.
        if re.match(rf"^## \[{re.escape(version)}\](\s|$)", line):
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## ["):
            end = j
            break
    section = "\n".join(lines[start:end]).strip()
    return section or None


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

    app_version = _app_version()
    version = _engine_version()
    body, url = _upstream(version)

    lines: list[str] = []

    changelog = _changelog_section(app_version)
    if changelog:
        lines += [
            f"## What's new in Omnivert {app_version}",
            "",
            changelog,
            "",
            "Full changelog: "
            f"https://github.com/BrandonDry/Omnivert/blob/v{app_version}/CHANGELOG.md",
            "",
            "---",
            "",
        ]
    else:
        print(f"WARNING: no CHANGELOG.md section for {app_version}; notes carry only the engine half.")

    lines += [
        "## Conversion engine",
        "",
        f"This release bundles **Microsoft MarkItDown `{version}`**.",
        "",
    ]
    if body:
        lines += ["### What's new in MarkItDown", "", body.strip(), ""]
    lines += [f"[MarkItDown `{version}` release notes]({url})", "", DISCLAIMER, ""]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"Wrote release notes for Omnivert {app_version} "
        f"(changelog section: {'yes' if changelog else 'MISSING'}) "
        f"and engine {version} -> {out_path}"
    )


if __name__ == "__main__":
    main()
