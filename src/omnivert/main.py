"""FastAPI app for Omnivert.

Exposes capability/plugin discovery, the three conversion entry points (file, URL, text),
and a redacted settings read/write. In production the built frontend (``frontend/dist``)
is mounted as static files; in dev the Vite server (5173) talks to this API via CORS.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import app_updates
from . import jobs
from . import settings as settings_module
from . import updates
from . import window_bridge
from .app_version import __version__ as APP_VERSION, git_commit
from .capabilities import get_capabilities
from .conversion import service
from .plugins import list_plugins
from .schemas import (
    AppUpdateApplyRequest,
    AppUpdateInfo,
    AppVersionInfo,
    BatchResult,
    CapabilitiesResponse,
    ConversionResult,
    ConvertOptions,
    FolderConvertRequest,
    NativeInfo,
    PathsConvertRequest,
    PickResult,
    PluginInfo,
    SaveMarkdownRequest,
    SaveResult,
    TextConvertRequest,
    UpdateApplyRequest,
    UpdateInfo,
    UpdateStatus,
    UrlConvertRequest,
)

# Guardrail: refuse absurdly large folder batches so a stray "C:\" pick can't hang.
MAX_BATCH_FILES = 1000
SKIPPED_BATCH_DIRS = {".git", ".venv", "__pycache__", "dist", "node_modules"}
# Refuse a single request body larger than this (memory guard for stray huge uploads).
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB

app = FastAPI(title="Omnivert", version=APP_VERSION)

# The backend is a localhost-only companion to the desktop window and has no auth: any
# loopback client is trusted, because the only intended client is the bundled UI running
# as the same user. Loopback names a request may legitimately carry as its Host header.
_ALLOWED_API_HOSTS = {"127.0.0.1", "localhost", "::1"}

_DEV_MODE = not getattr(sys, "frozen", False)

# Origins the Vite dev server may appear as. In dev the browser loads the UI from Vite and
# Vite proxies /api here (frontend/vite.config.ts), so a legitimate dev request arrives naming
# the dev server's origin rather than this one.
#
# Any loopback port, not just 5173: Vite ships with strictPort false, so it silently moves to
# 5174 when 5173 is taken, and `npm run dev -- --host` moves it too. Pinning one port would
# turn a port collision into a wall of 403s reading "only accepts requests from the Omnivert
# window", which is a security-shaped message for a problem that is not one. Running a dev
# server already means trusting what is listening on loopback, and a frozen build never
# reaches this at all. What is NOT covered: browsing a `--host` dev server through the
# machine's LAN address instead of localhost. Use localhost.

# The origins the CORS middleware answers for, which is a NARROWER list than the guard's
# pattern above, and deliberately so. CORS grants a page the right to READ responses; the
# guard only decides whether a request runs. The documented dev setup proxies /api through
# Vite, so the browser sees same-origin and CORS never comes into it: this list only serves a
# dev who bypasses the proxy, and there is no reason to widen a read grant to cover a port
# collision that only affects the guard.
_DEV_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def _is_dev_origin(origin: str) -> bool:
    """True only for the Vite dev server's own origins, and only outside a frozen build.

    This deliberately does NOT match any loopback origin. It used to, and a security review
    showed that was the hole rather than the guard: a page served on ANY local port could
    announce ``Sec-Fetch-Site: cross-site`` and still be let through, because a dev origin
    overrode the check below. Measured at the time: 200 for a hostile
    ``Origin: http://localhost:3000``. Scoping this to the two origins the CORS policy
    already grants means the cross-origin guard is exactly as permissive as CORS and no more.

    Note the documented dev workflow does not need this at all. ``frontend/vite.config.ts``
    proxies ``/api`` to the backend, and Vite's ``changeOrigin`` defaults to false, so the
    backend sees Host and Origin both as ``localhost:5173`` and ``_origin_is_own`` matches
    without any allowance. Verified by running the proxy shape with this function forced to
    return False: still 200. It survives only for a dev who bypasses the proxy and points a
    browser straight at port 8765.
    """
    return _DEV_MODE and origin in _DEV_CORS_ORIGINS

# Sec-Fetch-Site values that mean "this request did not come from another site". "none" is a
# user-initiated load: the address bar, a bookmark, or the desktop window opening its own
# URL. "same-site" is deliberately absent: on loopback it would admit any page served by any
# other local port, and the bundled UI never produces it.
_SAME_SITE_FETCH = {"same-origin", "none"}


def _split_host_port(host_header: str) -> Tuple[str, int]:
    """Split a Host header into a lowercase hostname and a port, defaulting to 80.

    Bracketed IPv6 needs its own branch: "[::1]:8765" does not split on the last colon the
    way "127.0.0.1:8765" does.
    """
    host = (host_header or "").strip()
    if host.startswith("["):  # bracketed IPv6, optionally with :port -> [::1]:8765
        hostname, _, rest = host[1:].partition("]")
        port_text = rest.lstrip(":")
    else:  # host[:port] -> drop the port if present
        hostname, _, port_text = host.rpartition(":")
        if not hostname:  # no colon at all, so rpartition put everything in port_text
            hostname, port_text = port_text, ""
    try:
        port = int(port_text) if port_text else 80
    except ValueError:
        port = 80
    return hostname.lower(), port


def _origin_is_own(origin: str, host_header: str) -> bool:
    """True when ``origin`` names this very server.

    Matched on loopback name plus port rather than by string equality, so a window that
    loaded http://localhost:<port> and a Host header of 127.0.0.1:<port> (or the reverse)
    still count as the same app. That relaxation grants nothing: only this app answers on
    that port, and anything that could take the port is already running as the user.
    """
    try:
        parsed = urlparse(origin)
        origin_port = parsed.port or 80
    except ValueError:  # a malformed port raises rather than parsing
        return False
    if parsed.scheme != "http":
        return False
    if "@" in parsed.netloc:
        # urlparse reads http://evil.example@127.0.0.1:8765 as hostname 127.0.0.1. No browser
        # serialises an Origin with userinfo in it, so anything that does is not a browser
        # and has no business being treated as this app's own window.
        return False
    if (parsed.hostname or "").lower() not in _ALLOWED_API_HOSTS:
        return False
    hostname, port = _split_host_port(host_header)
    return hostname in _ALLOWED_API_HOSTS and origin_port == port


def _refuse_cross_site() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": "This local API only accepts requests from the Omnivert window."},
    )


@app.middleware("http")
async def _guard_cross_origin(request: Request, call_next):
    """Reject requests a browser tells us came from another site.

    _guard_host closes DNS rebinding and nothing else. A page on any origin can still address
    http://127.0.0.1:<port> directly, and the Host header is then a loopback name the guard
    has to allow, because that is exactly how the app's own window talks to the API. The
    attacker cannot read the reply, but reading was never the point: multipart/form-data is
    CORS-safelisted, so the POST goes out with no preflight to refuse, and /api/convert/file
    runs with attacker-chosen options that spend the user's Claude key (describe_images) or
    Azure keys (azure_backend) and load installed plugins (enable_plugins), while
    /api/pick-files and /api/pick-folder pop native dialogs over their desktop. Verified: it
    returned 200 and did the work.

    Two headers say where a request came from, and either one on its own is enough to refuse.
    Sec-Fetch-Site is sent by Chromium 76+, Firefox 90+ and Safari 16.4+, and script cannot
    set it. Origin is sent on every cross-origin request and on every non-GET request, and has
    been since roughly 2016.

    A request carrying NEITHER is allowed through, which is a decision rather than an
    oversight: curl, the update checker and the test suite send neither, and no browser old
    enough to send neither on a cross-site POST is still in service, so the shape that has the
    side effects is covered by Origin alone even where Sec-Fetch-Site is missing. What the
    fail-open leaves is a cross-site GET from a pre-2019 browser, which can only reach
    responses it was already unable to read.
    """
    site = request.headers.get("sec-fetch-site", "").strip().lower()
    origin = request.headers.get("origin", "").strip()
    dev_origin = _is_dev_origin(origin)

    if site and site not in _SAME_SITE_FETCH and not dev_origin:
        return _refuse_cross_site()
    if origin and not dev_origin and not _origin_is_own(origin, request.headers.get("host", "")):
        return _refuse_cross_site()
    return await call_next(request)


@app.middleware("http")
async def _guard_host(request: Request, call_next):
    """Reject requests whose Host header isn't a loopback name.

    This is a DNS-rebinding guard. The server binds 127.0.0.1, but that alone doesn't stop
    a malicious website the user visits in their normal browser from rebinding its own
    hostname to 127.0.0.1 and POSTing to the unauthenticated local API, and because that
    makes the request look same-origin to the browser, CORS does not protect against it.
    A rebound request still carries the attacker's hostname in its Host header, so refusing
    non-loopback hosts closes THAT vector. It does not, and cannot, stop a page addressing
    http://127.0.0.1:<port> directly: the Host is then a loopback name and must be allowed,
    since that is how the bundled UI itself talks to the API. That case is _guard_cross_origin's
    job, above.

    The bundled UI always talks to http://127.0.0.1:<port>, and the Vite dev proxy forwards
    as localhost, so legitimate traffic is unaffected. Requests with no Host header (rare
    non-browser clients) are allowed through: a browser-based attacker cannot omit it."""
    host = request.headers.get("host", "").strip()
    if host:
        hostname, _ = _split_host_port(host)
        if hostname not in _ALLOWED_API_HOSTS:
            return JSONResponse(
                status_code=403,
                content={"detail": "This local API only accepts loopback requests."},
            )
    return await call_next(request)


@app.middleware("http")
async def _limit_request_size(request: Request, call_next):
    """Reject oversized request bodies up front (by Content-Length) so a stray multi-GB
    upload can't exhaust memory before the route reads it."""
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > MAX_UPLOAD_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Upload is too large (limit 500 MB)."},
                )
        except ValueError:
            pass
    return await call_next(request)


# CORS is only needed for the Vite dev server (5173) talking to this API cross-origin.
# In a frozen build the UI is served same-origin from "/", so CORS is unnecessary.
if _DEV_MODE:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_DEV_CORS_ORIGINS),
        allow_methods=["*"],
        allow_headers=["*"],
    )

def _frontend_dist() -> Path:
    package_web = Path(__file__).resolve().parent / "web"
    if package_web.exists():
        return package_web
    frozen_web = Path(getattr(sys, "_MEIPASS", "")) / "web"
    if frozen_web.exists():
        return frozen_web
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


FRONTEND_DIST = _frontend_dist()


# --- discovery -----------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    return get_capabilities()


@app.get("/api/plugins", response_model=List[PluginInfo])
def plugins() -> List[PluginInfo]:
    return list_plugins()


# --- conversion ----------------------------------------------------------------------

@app.post("/api/convert/file", response_model=BatchResult)
def convert_file(
    files: List[UploadFile] = File(...),
    options: str = Form("{}"),
) -> BatchResult:
    # Sync route: FastAPI runs it in a threadpool, so the CPU/IO-heavy engine
    # conversion below doesn't block the event loop (read uploads synchronously too).
    opts = _parse_options(options)
    results: List[ConversionResult] = []
    # service.batch() reuses one engine across the whole request and frees it afterwards.
    # Every conversion route needs it: see the note above _engine_cache in conversion.py.
    with service.batch():
        for upload in files:
            data = upload.file.read()
            results.append(service.convert_bytes(data, upload.filename or "upload", opts))
    return BatchResult(batch_id=jobs.register(results), results=results)


@app.post("/api/convert/folder", response_model=BatchResult)
def convert_folder(req: FolderConvertRequest) -> BatchResult:
    # CodeQL flags this as path-injection (py/path-injection). By design: this is a local
    # file converter, so reading the folder the user themselves selected (native picker or
    # a typed path) on their own machine is the feature, not a flaw, and there is no safe root
    # to confine to. The unauthenticated-local-API vector this could otherwise enable is
    # closed by the loopback Host guard above (_guard_host).
    root = Path(req.path.strip()).expanduser()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a folder: {req.path}")

    files = _list_folder(root, req.recursive)
    if not files:
        raise HTTPException(status_code=400, detail="No files found in that folder.")
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Folder has {len(files)} files (limit {MAX_BATCH_FILES}). "
            "Pick a narrower folder.",
        )

    with service.batch():
        results = [_convert_path(p, p.relative_to(root).as_posix(), req.options) for p in files]
    return BatchResult(batch_id=jobs.register(results), results=results)


@app.post("/api/convert/paths", response_model=BatchResult)
def convert_paths(req: PathsConvertRequest) -> BatchResult:
    if not req.paths:
        raise HTTPException(status_code=422, detail="No paths provided.")
    results: List[ConversionResult] = []
    with service.batch():
        for raw in req.paths:
            # By design / path-injection (see convert_folder): these paths are the local
            # files the user selected to convert; reading them is the feature. Guarded by
            # _guard_host.
            path = Path(raw).expanduser()
            if not path.is_file():
                results.append(
                    ConversionResult(
                        filename=path.name or raw,
                        ok=False,
                        error=f"File not found: {raw}",
                        error_kind="not_found",
                        remediation="The file may have moved or been deleted.",
                    )
                )
                continue
            results.append(_convert_path(path, path.name, req.options))
    return BatchResult(batch_id=jobs.register(results), results=results)


# --- download ------------------------------------------------------------------------

@app.get("/api/download/{batch_id}")
def download_batch(batch_id: str) -> Response:
    results = jobs.get(batch_id)
    if results is None:
        raise HTTPException(status_code=404, detail="That batch is no longer available.")

    single = jobs.single_markdown(results)
    if single is not None:
        return Response(
            content=(single.markdown or "").encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": jobs.content_disposition(jobs.md_filename(single))},
        )

    if not jobs.successful(results):
        raise HTTPException(status_code=400, detail="Nothing converted successfully to download.")

    archive = jobs.build_zip(results)
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": jobs.content_disposition(jobs.zip_filename())},
    )


@app.post("/api/save-markdown", response_model=SaveResult)
def save_markdown(req: SaveMarkdownRequest) -> SaveResult:
    try:
        path = window_bridge.save_file(
            req.filename,
            req.content.encode("utf-8"),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not save the file. Check permissions and available disk space.",
        ) from exc
    return SaveResult(path=path)


@app.post("/api/save-download/{batch_id}", response_model=SaveResult)
def save_download(batch_id: str) -> SaveResult:
    results = jobs.get(batch_id)
    if results is None:
        raise HTTPException(status_code=404, detail="That batch is no longer available.")

    single = jobs.single_markdown(results)
    if single is not None:
        filename = jobs.md_filename(single)
        data = (single.markdown or "").encode("utf-8")
    else:
        if not jobs.successful(results):
            raise HTTPException(status_code=400, detail="Nothing converted successfully to save.")
        filename = jobs.zip_filename()
        data = jobs.build_zip(results)

    try:
        path = window_bridge.save_file(filename, data)
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not save the file. Check permissions and available disk space.",
        ) from exc
    return SaveResult(path=path)


# --- native pickers ------------------------------------------------------------------

@app.get("/api/native", response_model=NativeInfo)
def native_info() -> NativeInfo:
    return NativeInfo(dialogs=window_bridge.available())


@app.post("/api/pick-folder", response_model=PickResult)
def pick_folder() -> PickResult:
    try:
        path = window_bridge.pick_folder()
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return PickResult(paths=[path] if path else [])


@app.post("/api/pick-files", response_model=PickResult)
def pick_files() -> PickResult:
    try:
        return PickResult(paths=window_bridge.pick_files())
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


# --- updates -------------------------------------------------------------------------

@app.get("/api/updates/check", response_model=UpdateInfo)
def updates_check() -> UpdateInfo:
    return UpdateInfo(**updates.check_for_updates())


@app.post("/api/updates/apply", response_model=UpdateStatus)
def updates_apply(req: UpdateApplyRequest) -> UpdateStatus:
    return UpdateStatus(**updates.start_update(req.version))


@app.get("/api/updates/status", response_model=UpdateStatus)
def updates_status() -> UpdateStatus:
    return UpdateStatus(**updates.get_status())


# --- app self-update (this app, from GitHub Releases) --------------------------------

@app.get("/api/app/version", response_model=AppVersionInfo)
def app_version() -> AppVersionInfo:
    return AppVersionInfo(
        version=APP_VERSION,
        commit=git_commit(),
        frozen=bool(getattr(sys, "frozen", False)),
    )


@app.get("/api/app/updates/check", response_model=AppUpdateInfo)
def app_updates_check() -> AppUpdateInfo:
    return AppUpdateInfo(**app_updates.check_for_app_update())


@app.post("/api/app/updates/apply", response_model=UpdateStatus)
def app_updates_apply(req: AppUpdateApplyRequest) -> UpdateStatus:
    # req is accepted and deliberately not read: start_app_update resolves the asset from the
    # configured repo itself. The body used to choose what this endpoint downloaded and ran.
    return UpdateStatus(**app_updates.start_app_update())


@app.get("/api/app/updates/status", response_model=UpdateStatus)
def app_updates_status() -> UpdateStatus:
    return UpdateStatus(**app_updates.get_status())


@app.post("/api/convert/url", response_model=ConversionResult)
def convert_url(req: UrlConvertRequest) -> ConversionResult:
    if not req.url.strip():
        raise HTTPException(status_code=422, detail="A URL is required.")
    with service.batch():
        return service.convert_url(req.url.strip(), req.options)


@app.post("/api/convert/text", response_model=ConversionResult)
def convert_text(req: TextConvertRequest) -> ConversionResult:
    with service.batch():
        return service.convert_text(req.content, req.extension, req.charset, req.options)


# --- settings ------------------------------------------------------------------------

@app.get("/api/settings")
def get_settings() -> dict:
    return settings_module.redact(settings_module.load())


@app.put("/api/settings")
def put_settings(incoming: dict) -> dict:
    saved = settings_module.save(incoming)
    return settings_module.redact(saved)


# --- helpers -------------------------------------------------------------------------

def _parse_options(raw: str) -> ConvertOptions:
    try:
        data = json.loads(raw) if raw else {}
        return ConvertOptions(**data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid options: {exc}") from exc


def _list_folder(root: Path, recursive: bool) -> List[Path]:
    """Return files under ``root`` while avoiding generated dependency/cache trees."""
    if not recursive:
        return sorted(p for p in root.iterdir() if p.is_file())

    files: List[Path] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIPPED_BATCH_DIRS]
        base = Path(current)
        for name in filenames:
            path = base / name
            if path.is_file():
                files.append(path)
    return sorted(files)


def _convert_path(path: Path, label: str, opts: ConvertOptions) -> ConversionResult:
    """Convert a local file path using the same byte-stream path as file uploads."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        return ConversionResult(
            filename=label,
            ok=False,
            error=str(exc),
            error_kind="read_failed",
            remediation="Check that the file still exists and is readable.",
        )
    return service.convert_bytes(data, label, opts)


# --- static frontend (production) ----------------------------------------------------
# Mounted last so /api/* routes take precedence.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
