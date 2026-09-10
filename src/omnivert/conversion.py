"""ConversionService — the single place that builds conversion engine instances and runs
conversions, capturing warnings and mapping exceptions to friendly, structured errors.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import threading
import warnings
from typing import Any, Dict, List, Tuple

from markitdown import MarkItDown as Engine, StreamInfo

from . import settings as settings_module
from . import url_guard
from .claude_shim import build_llm_client
from .schemas import ConversionResult, ConvertOptions

# --- Exception types (import defensively; location/exports vary by version) ----------
try:  # pragma: no cover - import shimming
    from markitdown import (
        FileConversionException,
        MissingDependencyException,
        UnsupportedFormatException,
    )
except ImportError:  # fall back to the private module
    from markitdown._exceptions import (  # type: ignore
        FileConversionException,
        MissingDependencyException,
        UnsupportedFormatException,
    )


def _normalize_extension(ext: str | None) -> str | None:
    if not ext:
        return None
    ext = ext.strip()
    if not ext:
        return None
    return ext if ext.startswith(".") else f".{ext}"


def _ext_from_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    _, ext = os.path.splitext(filename)
    return ext or None


# Every settings key that ``_construct`` reads. The cache signature is computed from these,
# so a new engine-affecting setting MUST be added here or a stale engine will be reused
# after the user changes it. ``test_conversion.py`` pins this list against ``_construct``.
_ENGINE_CONFIG_KEYS = (
    "exiftool_path",
    "style_map",
    "claude_api_key",
    "claude_base_url",
    "claude_model",
    "llm_prompt",
    "docintel_endpoint",
    "docintel_key",
    "docintel_api_version",
    "docintel_file_types",
    "cu_endpoint",
    "cu_key",
    "cu_analyzer_id",
    "cu_file_types",
)

# Engine construction is not free: ``MarkItDown.__init__`` builds a ``magika.Magika()`` and
# registers ~20 converters, measured at ~36 ms per instance on the pinned engine. (The ONNX
# model itself is cached by magika at module level, so this is registration cost, not a model
# load per file. Measure before "optimising" further.) The old code built one engine per
# FILE, so a 1000-file folder batch spent ~36 s doing nothing but rebuilding it.
#
# Cache per *thread* rather than globally: FastAPI runs these sync routes in a threadpool, so
# a batch runs start-to-finish on one thread and hits the cache for every file after the
# first, while two concurrent requests land on different threads and never share an engine.
# That last part is the point: a shared engine would also share its ``requests.Session``,
# which is not thread-safe.
_engine_cache = threading.local()


class ConversionService:
    """Builds configured conversion engine instances and performs conversions."""

    @staticmethod
    def _signature(cfg: Dict[str, Any], opts: ConvertOptions) -> str:
        """Hash every input that affects how the engine is *constructed*.

        Per-call conversion kwargs (``keep_data_uris``) and the stream hints
        (extension/mimetype/charset) are deliberately excluded: they are passed at convert
        time and do not change the engine. Secrets are hashed rather than retained, so the
        cache key never holds an API key in plaintext.
        """
        material = json.dumps(
            {
                "enable_plugins": opts.enable_plugins,
                "describe_images": opts.describe_images,
                "azure_backend": opts.azure_backend,
                "cfg": {k: cfg.get(k) for k in _ENGINE_CONFIG_KEYS},
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _build(self, opts: ConvertOptions) -> Engine:
        cfg = settings_module.load()
        signature = self._signature(cfg, opts)
        cached = getattr(_engine_cache, "entry", None)
        if cached is not None and cached[0] == signature:
            return cached[1]
        engine = self._construct(cfg, opts)
        _engine_cache.entry = (signature, engine)
        return engine

    def _construct(self, cfg: Dict[str, Any], opts: ConvertOptions) -> Engine:
        kwargs: Dict[str, Any] = {}

        if cfg.get("exiftool_path"):
            kwargs["exiftool_path"] = cfg["exiftool_path"]
        if cfg.get("style_map"):
            kwargs["style_map"] = cfg["style_map"]

        # Claude image captioning
        if opts.describe_images:
            client = build_llm_client(cfg.get("claude_api_key", ""), cfg.get("claude_base_url"))
            kwargs["llm_client"] = client
            kwargs["llm_model"] = cfg.get("claude_model") or settings_module.DEFAULT_CLAUDE_MODEL
            if cfg.get("llm_prompt"):
                kwargs["llm_prompt"] = cfg["llm_prompt"]

        # Azure backends
        if opts.azure_backend == "docintel":
            endpoint = (cfg.get("docintel_endpoint") or "").strip()
            if not endpoint:
                raise RuntimeError(
                    "Azure Document Intelligence endpoint is not configured. "
                    "Add it in Settings or choose the local backend."
                )
            if not cfg.get("docintel_key") and not os.environ.get("AZURE_API_KEY"):
                raise RuntimeError(
                    "Azure Document Intelligence API key is not configured. "
                    "Add it in Settings or choose the local backend."
                )
            kwargs["docintel_endpoint"] = endpoint
            if cfg.get("docintel_api_version"):
                kwargs["docintel_api_version"] = cfg["docintel_api_version"]
            if cfg.get("docintel_file_types"):
                kwargs["docintel_file_types"] = self._docintel_file_types(
                    cfg["docintel_file_types"]
                )
            cred = self._azure_credential(cfg.get("docintel_key"))
            if cred is not None:
                kwargs["docintel_credential"] = cred
        elif opts.azure_backend == "cu":
            endpoint = (cfg.get("cu_endpoint") or "").strip()
            if not endpoint:
                raise RuntimeError(
                    "Azure Content Understanding endpoint is not configured. "
                    "Add it in Settings or choose the local backend."
                )
            if not cfg.get("cu_key") and not os.environ.get("AZURE_API_KEY"):
                raise RuntimeError(
                    "Azure Content Understanding API key is not configured. "
                    "Add it in Settings or choose the local backend."
                )
            kwargs["cu_endpoint"] = endpoint
            if cfg.get("cu_analyzer_id"):
                kwargs["cu_analyzer_id"] = cfg["cu_analyzer_id"]
            if cfg.get("cu_file_types"):
                kwargs["cu_file_types"] = self._cu_file_types(cfg["cu_file_types"])
            cred = self._azure_credential(cfg.get("cu_key"))
            if cred is not None:
                kwargs["cu_credential"] = cred

        return Engine(enable_plugins=opts.enable_plugins, **kwargs)

    @staticmethod
    def _azure_credential(key: str | None):
        if not key:
            return None
        from azure.core.credentials import AzureKeyCredential

        return AzureKeyCredential(key)

    @staticmethod
    def _parse_file_types(raw_types: List[str], enum_cls, label: str):
        """Parse Settings' string file-type list into one of the engine's file-type enums.

        Both cloud backends take the same shape of list, so they share this. Users type
        what they see on a file (".JPG", "tif"), not the engine's spelling, hence the
        strip/lower/de-dot and the alias map.
        """
        aliases = {"jpg": "jpeg", "jpe": "jpeg", "tif": "tiff", "htm": "html"}
        parsed = []
        for raw in raw_types:
            value = str(raw).strip().lower().lstrip(".")
            if not value:
                continue
            value = aliases.get(value, value)
            try:
                parsed.append(enum_cls(value))
            except ValueError as exc:
                valid = ", ".join(item.value for item in enum_cls)
                raise RuntimeError(
                    f"Unsupported {label} file type '{raw}'. Use one of: {valid}."
                ) from exc
        return parsed or None

    @classmethod
    def _cu_file_types(cls, raw_types: List[str]):
        from markitdown.converters import ContentUnderstandingFileType

        return cls._parse_file_types(
            raw_types, ContentUnderstandingFileType, "Content Understanding"
        )

    @classmethod
    def _docintel_file_types(cls, raw_types: List[str]):
        from markitdown.converters import DocumentIntelligenceFileType

        return cls._parse_file_types(
            raw_types, DocumentIntelligenceFileType, "Document Intelligence"
        )

    @staticmethod
    def _convert_kwargs(opts: ConvertOptions) -> Dict[str, Any]:
        ck: Dict[str, Any] = {}
        if opts.keep_data_uris:
            ck["keep_data_uris"] = True
        return ck

    # --- public conversion entry points ---------------------------------------------

    def convert_bytes(self, data: bytes, filename: str, opts: ConvertOptions) -> ConversionResult:
        def run(md: Engine):
            stream_info = StreamInfo(
                extension=_normalize_extension(opts.extension) or _ext_from_filename(filename),
                mimetype=opts.mimetype or None,
                charset=opts.charset or None,
                filename=filename or None,
            )
            return md.convert_stream(
                io.BytesIO(data), stream_info=stream_info, **self._convert_kwargs(opts)
            )

        return self._run_capturing(filename, opts, run)

    def convert_url(self, url: str, opts: ConvertOptions) -> ConversionResult:
        blocked = url_guard.blocked_reason(url)
        if blocked:
            return ConversionResult(
                filename=url,
                ok=False,
                error=blocked,
                error_kind="blocked_url",
                remediation="Use a public http(s) URL. Local files, internal addresses, and "
                "non-web schemes are blocked for safety.",
            )

        def run(md: Engine):
            return md.convert_uri(url, **self._convert_kwargs(opts))

        return self._run_capturing(url, opts, run)

    def convert_text(
        self, content: str, extension: str | None, charset: str | None, opts: ConvertOptions
    ) -> ConversionResult:
        cs = charset or "utf-8"
        try:
            data = content.encode(cs)
        except LookupError:
            cs = "utf-8"
            data = content.encode(cs)
        ext = _normalize_extension(extension) or ".txt"
        merged = opts.model_copy(update={"extension": ext, "charset": cs})
        return self.convert_bytes(data, f"pasted{ext}", merged)

    # --- shared machinery -------------------------------------------------------------

    def _run_capturing(self, label: str, opts: ConvertOptions, run) -> ConversionResult:
        try:
            md = self._build(opts)
        except RuntimeError as exc:  # e.g. captioning requested without a key
            return ConversionResult(
                filename=label, ok=False, error=str(exc),
                error_kind="configuration", remediation="Check Settings and try again.",
            )
        except Exception as exc:  # noqa: BLE001 - converter setup can fail before conversion
            kind, remediation = _classify(exc)
            if opts.azure_backend != "none" and kind == "error":
                kind = "azure_backend"
                remediation = (
                    "Check the selected Azure backend settings, API key, endpoint, "
                    "and network access."
                )
            return ConversionResult(
                filename=label,
                ok=False,
                error=str(exc) or exc.__class__.__name__,
                error_kind=kind,
                remediation=remediation,
            )

        warning_msgs: List[str] = []
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = run(md)
                warning_msgs = _dedupe([str(w.message) for w in caught])
        except Exception as exc:  # noqa: BLE001 - classified below
            kind, remediation = _classify(exc)
            return ConversionResult(
                filename=label, ok=False, error=str(exc) or exc.__class__.__name__,
                error_kind=kind, remediation=remediation,
            )

        return ConversionResult(
            filename=label,
            ok=True,
            markdown=result.markdown,
            title=getattr(result, "title", None),
            warnings=warning_msgs,
        )


def _dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _classify(exc: Exception) -> Tuple[str, str]:
    """Return (error_kind, remediation) for a conversion exception."""
    if isinstance(exc, UnsupportedFormatException):
        return (
            "unsupported_format",
            "No converter matched this input. Try setting an extension/MIME-type hint "
            "in Advanced options.",
        )
    if isinstance(exc, MissingDependencyException):
        msg = str(exc).lower()
        if "ffmpeg" in msg:
            remediation = "Install ffmpeg (e.g. `winget install Gyan.FFmpeg`) and relaunch."
        else:
            remediation = (
                "A required optional dependency is missing. Install the matching "
                "markitdown extra into the venv."
            )
        return ("missing_dependency", remediation)
    if isinstance(exc, FileConversionException):
        return ("conversion_failed", "The file matched a converter but could not be parsed. "
                "It may be corrupt or password-protected.")
    return ("error", "Unexpected error during conversion.")


# Singleton used by the API layer.
service = ConversionService()
