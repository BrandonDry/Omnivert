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
