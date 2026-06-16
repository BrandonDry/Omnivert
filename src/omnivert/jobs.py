"""Batch bookkeeping + zip packaging for Omnivert.

Conversions done through the batch/folder endpoints are registered here under a short
id so the frontend can later download the whole set as a single archive (or a lone
``.md`` when only one item succeeded) via ``GET /api/download/{id}``.

The store is process-local and in-memory: this is a single-user desktop app, batches
are cheap (just the produced Markdown strings), and they should not outlive the running
window. A small LRU cap keeps memory bounded across a long session.
"""

from __future__ import annotations

import io
import re
import threading
import zipfile
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import quote
from uuid import uuid4

from .schemas import ConversionResult

# Keep at most this many recent batches; oldest are evicted first.
_MAX_BATCHES = 64
_BATCHES: "OrderedDict[str, List[ConversionResult]]" = OrderedDict()
# FastAPI runs the (sync) conversion routes in a threadpool, so two batches can be
# registered concurrently. Guard the store so the OrderedDict can't be corrupted.
_LOCK = threading.Lock()

_UNSAFE = re.compile(r'[\\/:*?"<>|]+')
_TRAILING_EXT = re.compile(r"\.[^./\\]+$")


def register(results: List[ConversionResult]) -> str:
    """Store ``results`` under a fresh id and return it."""
    batch_id = uuid4().hex[:12]
    with _LOCK:
        _BATCHES[batch_id] = results
        _BATCHES.move_to_end(batch_id)
        while len(_BATCHES) > _MAX_BATCHES:
            _BATCHES.popitem(last=False)
    return batch_id


def get(batch_id: str) -> Optional[List[ConversionResult]]:
    with _LOCK:
        return _BATCHES.get(batch_id)


def _md_arcname(label: str) -> str:
    """Turn a result's source label (filename or relative path) into a tidy ``.md``
    archive name, preserving any subfolder structure for folder batches."""
    name = (label or "converted").replace("\\", "/").strip("/")
    name = _TRAILING_EXT.sub("", name)  # drop the source extension
    # Sanitize each path segment but keep the separators.
    segments = [_UNSAFE.sub("_", seg).strip(" .") or "untitled" for seg in name.split("/")]
    cleaned = "/".join(s for s in segments if s) or "converted"
    return f"{cleaned}.md"


def _dedupe_name(name: str, used: set) -> str:
    if name not in used:
        used.add(name)
        return name
    stem, _, ext = name.rpartition(".")
    i = 2
    while True:
        candidate = f"{stem}-{i}.{ext}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        i += 1


def successful(results: List[ConversionResult]) -> List[ConversionResult]:
    return [r for r in results if r.ok and (r.markdown or "").strip()]


def single_markdown(results: List[ConversionResult]) -> Optional[ConversionResult]:
    """If exactly one item produced Markdown, return it (so callers can serve a plain
    ``.md`` instead of a one-entry zip)."""
    ok = successful(results)
    return ok[0] if len(ok) == 1 else None


def build_zip(results: List[ConversionResult]) -> bytes:
    """Pack every successful conversion's Markdown into a zip, plus a short report
    listing warnings and any failures so nothing is silently dropped."""
    buf = io.BytesIO()
    used: set = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for result in successful(results):
            arcname = _dedupe_name(_md_arcname(result.filename), used)
            zf.writestr(arcname, result.markdown or "")
        zf.writestr("_conversion-report.txt", _report(results))
    return buf.getvalue()


def _report(results: List[ConversionResult]) -> str:
    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: List[str] = [
        "Omnivert — batch conversion report",
        f"Generated: {stamp}",
        f"Total: {len(results)}   Succeeded: {len(ok)}   Failed: {len(failed)}",
        "",
    ]
    for r in results:
        status = "OK" if r.ok else f"FAILED ({r.error_kind or 'error'})"
        lines.append(f"- {r.filename}: {status}")
        if not r.ok and r.error:
            lines.append(f"    {r.error}")
        for w in r.warnings:
            lines.append(f"    warning: {w}")
    lines.append("")
    return "\n".join(lines)


def zip_filename() -> str:
    return f"omnivert-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"


def md_filename(result: ConversionResult) -> str:
    return _md_arcname(result.title or result.filename).rsplit("/", 1)[-1]


def content_disposition(filename: str) -> str:
    """Build a ``Content-Disposition`` header value that is safe for any filename.

    Starlette encodes response headers as latin-1, so a non-Latin-1 character in the
    name (em-dash, smart quote, CJK, …) would otherwise raise ``UnicodeEncodeError`` and
    500 the download. We emit an ASCII ``filename="..."`` fallback (for the frontend's
    regex and older agents) plus an RFC 5987 ``filename*=UTF-8''...`` with the real name.
    """
    # encode→"replace" turns non-ASCII into "?", which is itself an invalid filename
    # char; map it (and quotes) to "_" so the bare filename="..." stays a usable name.
    ascii_fallback = (
        filename.encode("ascii", "replace").decode("ascii").replace("?", "_").replace('"', "_")
    )
    if not ascii_fallback.strip("_ "):
        ascii_fallback = "download"
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"
