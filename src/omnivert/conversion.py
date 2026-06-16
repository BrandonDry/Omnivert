"""ConversionService — the single place that builds conversion engine instances and runs
conversions, capturing warnings and mapping exceptions to friendly, structured errors.
"""

from __future__ import annotations

import io
import os
import warnings
from typing import Any, Dict, List, Tuple

from markitdown import MarkItDown as Engine, StreamInfo

from . import settings as settings_module
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


class ConversionService:
    """Builds configured conversion engine instances and performs conversions."""

    def _build(self, opts: ConvertOptions) -> Engine:
        cfg = settings_module.load()
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
    def _cu_file_types(raw_types: List[str]):
        """Parse Settings' string file-type list into the engine's CU enum values."""
        from markitdown.converters import ContentUnderstandingFileType

        aliases = {"jpg": "jpeg", "jpe": "jpeg", "tif": "tiff"}
        parsed = []
        for raw in raw_types:
            value = str(raw).strip().lower().lstrip(".")
            if not value:
                continue
            value = aliases.get(value, value)
            try:
                parsed.append(ContentUnderstandingFileType(value))
            except ValueError as exc:
                valid = ", ".join(item.value for item in ContentUnderstandingFileType)
                raise RuntimeError(
                    f"Unsupported Content Understanding file type '{raw}'. "
                    f"Use one of: {valid}."
                ) from exc
        return parsed or None

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
