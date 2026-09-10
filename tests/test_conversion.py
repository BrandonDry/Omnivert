"""Conversion service: engine caching, and the invariant that keeps it correct.

The engine is cached per thread so a folder batch stops paying ~36 ms of construction per
file. That optimisation is only safe while the cache signature covers every setting
``_construct`` reads: miss one, and changing it in Settings would silently reuse a stale
engine. ``test_engine_config_keys_cover_every_setting_construct_reads`` is what makes that
a mechanical check rather than a promise.
"""

from __future__ import annotations

import inspect
import re
import threading

import pytest

from omnivert import settings as settings_module
from omnivert.conversion import (
    _ENGINE_CONFIG_KEYS,
    _ENGINE_OPTION_FIELDS,
    _engine_cache,
    ConversionService,
    service,
)
from omnivert.schemas import ConvertOptions


def test_engine_config_keys_cover_every_setting_construct_reads():
    source = inspect.getsource(ConversionService._construct)
    read_keys = set(re.findall(r"""cfg\.get\(\s*["'](\w+)["']""", source))
    read_keys |= set(re.findall(r"""cfg\[\s*["'](\w+)["']\s*\]""", source))

    missing = read_keys - set(_ENGINE_CONFIG_KEYS)
    assert not missing, (
        "_construct reads settings that the cache signature ignores, so changing them in "
        f"Settings would reuse a stale engine: {sorted(missing)}"
    )


def test_engine_option_fields_cover_every_option_construct_reads():
    """The cfg half of this invariant is not the whole invariant.

    ``_construct`` reads ConvertOptions fields as well as settings, and an earlier version
    of this module only scanned ``cfg``. A review demonstrated the gap: adding a branch on
    ``opts.keep_data_uris`` to ``_construct`` left every test passing while the user
    toggling it would have been handed the previous engine.
    """
    source = inspect.getsource(ConversionService._construct)
    read_fields = set(re.findall(r"opts\.(\w+)", source))

    missing = read_fields - set(_ENGINE_OPTION_FIELDS)
    assert not missing, (
        "_construct reads ConvertOptions fields that the cache signature ignores, so "
        f"toggling them would reuse a stale engine: {sorted(missing)}"
    )


def test_engine_option_fields_are_real_convert_options():
    unknown = set(_ENGINE_OPTION_FIELDS) - set(ConvertOptions.model_fields)
    assert not unknown, f"_ENGINE_OPTION_FIELDS names fields that do not exist: {sorted(unknown)}"


def test_engine_config_keys_are_all_real_settings():
    unknown = set(_ENGINE_CONFIG_KEYS) - set(settings_module.DEFAULTS)
    assert not unknown, f"_ENGINE_CONFIG_KEYS names settings that do not exist: {sorted(unknown)}"


def test_engine_is_reused_for_identical_options(isolated_settings):
    opts = ConvertOptions()
    assert service._build(opts) is service._build(opts)


@pytest.mark.parametrize(
    "changed",
    [
        {"enable_plugins": True},
        {"describe_images": True},
        {"azure_backend": "docintel"},
    ],
)
def test_changing_an_option_rebuilds_the_engine(isolated_settings, changed):
    base = service._build(ConvertOptions())
    try:
        rebuilt = service._build(ConvertOptions(**changed))
    except RuntimeError:
        # describe_images / azure_backend legitimately refuse without configuration; the
        # point is that they did NOT silently hand back the cached engine.
        return
    assert rebuilt is not base


def test_changing_a_setting_rebuilds_the_engine(isolated_settings):
    opts = ConvertOptions()
    first = service._build(opts)
    settings_module.save({"style_map": "p[style-name='Title'] => h1:fresh"})
    assert service._build(opts) is not first


def test_convert_kwargs_exclude_construction_only_options():
    """keep_data_uris is a per-convert kwarg, so it must not be in the cache signature."""
    assert "keep_data_uris" not in _ENGINE_CONFIG_KEYS
    kwargs = ConversionService._convert_kwargs(ConvertOptions(keep_data_uris=True))
    assert kwargs == {"keep_data_uris": True}


def test_each_thread_gets_its_own_engine(isolated_settings):
    """Engines must not be shared across threads: they hold a requests.Session, which is
    not thread-safe, and FastAPI runs these sync routes in a threadpool."""
    opts = ConvertOptions()
    main_engine = service._build(opts)
    other: list = []

    thread = threading.Thread(target=lambda: other.append(service._build(opts)))
    thread.start()
    thread.join()

    assert other and other[0] is not main_engine


def test_signature_is_stable_and_does_not_leak_secrets(isolated_settings):
    settings_module.save({"claude_api_key": "sk-ant-should-not-appear"})
    cfg = settings_module.load()
    opts = ConvertOptions()

    sig = ConversionService._signature(cfg, opts)
    assert sig == ConversionService._signature(cfg, opts)
    assert "sk-ant-should-not-appear" not in sig
    assert len(sig) == 64  # sha256 hex


def test_changing_a_secret_still_changes_the_signature(isolated_settings):
    opts = ConvertOptions()
    cfg_a = dict(settings_module.DEFAULTS, claude_api_key="key-one")
    cfg_b = dict(settings_module.DEFAULTS, claude_api_key="key-two")
    assert ConversionService._signature(cfg_a, opts) != ConversionService._signature(cfg_b, opts)


# --- cloud backend file-type parsing -------------------------------------------------

def test_docintel_file_types_parse_with_aliases():
    parsed = ConversionService._docintel_file_types([".PDF", "jpg", "tif"])
    assert [p.value for p in parsed] == ["pdf", "jpeg", "tiff"]


def test_file_types_reject_unknown_values_with_a_helpful_message():
    with pytest.raises(RuntimeError) as excinfo:
        ConversionService._docintel_file_types(["not-a-real-type"])
    message = str(excinfo.value)
    assert "Document Intelligence" in message
    assert "pdf" in message  # lists the valid values


def test_empty_file_type_list_means_no_restriction():
    assert ConversionService._docintel_file_types([]) is None
    assert ConversionService._docintel_file_types(["", "  "]) is None


# --- engine release -------------------------------------------------------------------

def test_batch_reuses_one_engine_then_releases_it(isolated_settings):
    """Caching without releasing would trade a speed problem for a memory one.

    A threadpool thread lives as long as the process, so an engine left in its thread-local
    is pinned forever. Each is ~7.8 MB (magika builds its own ONNX InferenceSession per
    instance) and anyio runs up to 40 workers.
    """
    opts = ConvertOptions()
    with service.batch():
        inside = service._build(opts)
        assert service._build(opts) is inside, "engine should be reused within a batch"

    assert getattr(_engine_cache, "entry", None) is None, "engine was not released"

    with service.batch():
        assert service._build(opts) is not inside, "a released engine must not come back"


def test_batch_releases_even_when_the_body_raises(isolated_settings):
    opts = ConvertOptions()
    with pytest.raises(ValueError):
        with service.batch():
            service._build(opts)
            raise ValueError("conversion blew up")
    assert getattr(_engine_cache, "entry", None) is None


def test_every_conversion_route_releases_its_engine():
    """Any /api/convert route that forgets service.batch() reintroduces the leak."""
    import ast

    from omnivert import main

    tree = ast.parse(inspect.getsource(main))
    checked = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        routes = [
            d.args[0].value
            for d in node.decorator_list
            if isinstance(d, ast.Call)
            and d.args
            and isinstance(d.args[0], ast.Constant)
            and isinstance(d.args[0].value, str)
            and d.args[0].value.startswith("/api/convert/")
        ]
        if not routes:
            continue
        checked.append(routes[0])
        body = ast.dump(node)
        assert "batch" in body, f"route {routes[0]} does not wrap its work in service.batch()"

    assert len(checked) >= 5, f"expected to find every convert route, found {checked}"
