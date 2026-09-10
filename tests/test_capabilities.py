"""Capabilities reporting, and the two invariants nothing else enforces.

CLAUDE.md requires ``_OPTIONAL_DEPS`` and the ``copy_metadata`` list in
``packaging/app.spec`` to stay in sync, because a distribution missing from the spec reports
``version: None`` in the frozen build. That was a prose obligation with no mechanism, and it
had in fact drifted in both directions: the spec named Pillow and youtube-transcript-api
(neither pinned) while missing lxml, pandas, olefile and azure-identity (all pinned). This
test is the mechanism.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from omnivert.capabilities import _FORMAT_SPECS, _OPTIONAL_DEPS, get_capabilities

SPEC_PATH = Path(__file__).resolve().parents[1] / "packaging" / "app.spec"


def _spec_metadata_names() -> list[str]:
    """Pull the dist names out of app.spec's explicit copy_metadata loop."""
    text = SPEC_PATH.read_text(encoding="utf-8")
    match = re.search(r"for dist_name in \((.*?)\):", text, re.DOTALL)
    assert match, "app.spec no longer has a 'for dist_name in (...)' block"
    return list(ast.literal_eval(f"({match.group(1)})"))


def test_optional_deps_and_app_spec_stay_in_sync():
    declared = {name for name, _module, _gates in _OPTIONAL_DEPS}
    in_spec = set(_spec_metadata_names())

    assert declared == in_spec, (
        "capabilities._OPTIONAL_DEPS and packaging/app.spec's copy_metadata list disagree.\n"
        f"  only in capabilities.py: {sorted(declared - in_spec)}\n"
        f"  only in app.spec       : {sorted(in_spec - declared)}"
    )


def test_every_format_requirement_names_a_known_dependency():
    known = {name for name, _module, _gates in _OPTIONAL_DEPS}
    for label, _exts, requires, _note in _FORMAT_SPECS:
        unknown = set(requires) - known
        assert not unknown, f"format {label!r} requires unknown distributions: {sorted(unknown)}"


def test_optional_deps_have_no_duplicates():
    names = [name for name, _module, _gates in _OPTIONAL_DEPS]
    assert len(names) == len(set(names))


def test_every_extension_is_dotted_or_a_url_scheme():
    for label, extensions, _requires, _note in _FORMAT_SPECS:
        assert extensions, f"format {label!r} lists no extensions"
        for ext in extensions:
            assert ext.startswith(".") or ext.endswith("://"), f"{label}: odd extension {ext!r}"


def test_capabilities_response_is_well_formed():
    caps = get_capabilities()
    assert caps.python_version
    assert len(caps.formats) == len(_FORMAT_SPECS)
    assert len(caps.dependencies) == len(_OPTIONAL_DEPS)
    assert all(d.gates for d in caps.dependencies), "every dependency should say what it gates"


@pytest.mark.parametrize(
    "label, extension",
    [
        ("Plain text", ".markdown"),
        ("Plain text", ".text"),
        ("JSON", ".jsonl"),
        ("XML / RSS / Atom", ".atom"),
    ],
)
def test_extensions_the_engine_accepts_are_advertised(label, extension):
    """These four are accepted by markitdown 0.1.7 but were absent from the old table."""
    spec = next(f for f in _FORMAT_SPECS if f[0] == label)
    assert extension in spec[1]


def test_no_youtube_capability_is_advertised():
    """The pin does not install youtube-transcript-api, so nothing may claim YouTube support.

    The old UI showed a 'YouTube: No' badge that could never turn Yes in a frozen build.
    """
    caps = get_capabilities()
    assert not hasattr(caps, "youtube_available")
    blob = " ".join(f.label + " " + (f.note or "") for f in caps.formats).lower()
    assert "youtube" not in blob


# --- what must NOT be frozen into the shipped executable ------------------------------
#
# The 0.1.5 build embedded 23 PyInstaller build-tool modules, all of pytest and _pytest, and
# ~340 pygments modules, pulled in because collect_submodules("webview") reaches pywebview's
# own PyInstaller hook package, which imports PyInstaller.utils.hooks. PyInstaller is
# GPL-2.0-or-later and its Bootloader Exception covers only the bootloader and loader, so
# shipping the rest inside an Apache-2.0 binary is a licence conflict, not untidiness. None of
# it runs either: a frozen app never invokes its own build tool.

_MUST_NOT_SHIP = {"PyInstaller", "pytest", "_pytest", "pygments", "altgraph", "pefile"}


def _spec_excludes() -> list[str]:
    text = SPEC_PATH.read_text(encoding="utf-8")
    match = re.search(r"_BUILD_ONLY = (\[.*?\])", text, re.DOTALL)
    assert match, "app.spec no longer defines _BUILD_ONLY"
    return list(ast.literal_eval(match.group(1)))


def test_build_tooling_is_excluded_from_the_freeze():
    missing = _MUST_NOT_SHIP - set(_spec_excludes())
    assert not missing, (
        f"app.spec no longer excludes {sorted(missing)} from the frozen build. "
        "See the note above _BUILD_ONLY: these get pulled in through pywebview's "
        "PyInstaller hook and must not reach the shipped executable."
    )


def test_the_excludes_are_wired_into_analysis():
    """A list defined and not passed to Analysis excludes nothing."""
    text = SPEC_PATH.read_text(encoding="utf-8")
    assert "excludes=_BUILD_ONLY" in text, "_BUILD_ONLY is defined but not passed to Analysis"


def test_pywebviews_own_server_is_not_excluded():
    """bottle is pywebview's real HTTP server, not build tooling. Excluding it would break
    the desktop window in a way no unit test here would catch."""
    assert "bottle" not in _spec_excludes()
