"""The two header guards in front of every route.

The API is unauthenticated by design: it is a companion to one desktop window, running as the
same user. That makes "who is asking" a question answered entirely by request headers, so
these tests drive a real Uvicorn instance on a loopback port rather than calling the
middleware functions. Registration and ordering are part of what is being asserted: a guard
defined but not installed, or installed after the routes it protects, passes a unit test of
the function and protects nothing.

The finding these were written against was reproduced as an HTTP status, so they assert on
HTTP statuses.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from unittest import mock
import requests
import uvicorn

from fastapi.testclient import TestClient

from omnivert import app_updates
from omnivert import main
from omnivert import settings as settings_module


@pytest.fixture(scope="module", autouse=True)
def isolated_settings_for_this_module(tmp_path_factory):
    """Point settings storage at a temp dir for every test here.

    The routes under test read the settings file and one of them writes it, and the server
    below runs in this same process. Without this, breaking a guard to check that a test
    really fails would write an attacker-shaped value into the developer's own settings.
    """
    target = tmp_path_factory.mktemp("settings") / "Omnivert" / "settings.json"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(settings_module, "settings_path", lambda: target)
        yield target


@pytest.fixture(scope="module")
def api():
    """A real backend on an ephemeral loopback port, with the app's full middleware stack."""
    config = uvicorn.Config(
        main.app, host="127.0.0.1", port=0, log_level="warning", access_log=False
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 20
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started, "the test backend never finished starting"

    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)


EVIL = "https://evil.example"

# Both guards answer 403, so a bare status assertion cannot say which one refused. Every
# cross-site test below checks the reason too, otherwise a reordering that let the Host guard
# swallow these requests first would leave the suite green while the cross-origin guard was
# doing nothing.
CROSS_SITE_DETAIL = "This local API only accepts requests from the Omnivert window."
BAD_HOST_DETAIL = "This local API only accepts loopback requests."


def _refused_cross_site(response) -> bool:
    return response.status_code == 403 and response.json()["detail"] == CROSS_SITE_DETAIL


def _convert_file(api: str, **headers):
    """POST a file conversion, the shape the cross-site hole was reproduced with.

    multipart/form-data is CORS-safelisted, so a browser sends this cross-origin with no
    preflight for the server to refuse.
    """
    return requests.post(
        f"{api}/api/convert/file",
        files={"files": ("note.txt", b"hello", "text/plain")},
        data={"options": "{}"},
        headers=headers,
        timeout=30,
    )


# --- cross-site requests are refused -----------------------------------------------------

def test_a_cross_site_conversion_is_refused(api):
    """Reproduced as HTTP 200 before this guard existed, options and all.

    Reading the response was never the point: the attacker's chosen options are what run.
    describe_images spends the user's Claude key, azure_backend spends their Azure keys, and
    enable_plugins loads whatever plugins are installed on the machine.
    """
    response = _convert_file(api, Origin=EVIL, **{"Sec-Fetch-Site": "cross-site"})

    assert _refused_cross_site(response)


def test_an_origin_alone_is_enough_to_refuse(api):
    """A browser too old for Sec-Fetch-Site still sends Origin on every non-GET request.

    Origin on POST predates Sec-Fetch-Site by years, so the header that survives is the one
    covering the requests with side effects.
    """
    response = _convert_file(api, Origin=EVIL)

    assert _refused_cross_site(response)


def test_sec_fetch_site_alone_is_enough_to_refuse(api):
    """And the other way round: script cannot set Sec-Fetch-Site, so it is worth trusting
    even when no Origin accompanies it."""
    response = _convert_file(api, **{"Sec-Fetch-Site": "cross-site"})

    assert _refused_cross_site(response)


def test_same_site_is_not_treated_as_same_origin(api):
    """http://localhost:<some other port> is same-site with this API and is not this app.

    Anything else listening on loopback would otherwise be able to drive it.
    """
    response = _convert_file(api, **{"Sec-Fetch-Site": "same-site"})

    assert _refused_cross_site(response)


def test_a_null_origin_is_refused(api):
    """Sandboxed iframes, file:// pages and cross-origin redirects all send Origin: null."""
    response = _convert_file(api, Origin="null", **{"Sec-Fetch-Site": "cross-site"})

    assert _refused_cross_site(response)


def test_an_origin_with_userinfo_is_not_this_app(api):
    """urlparse reads http://evil.example@127.0.0.1:<port> as hostname 127.0.0.1.

    No browser serialises an Origin with userinfo, so anything sending one is not a browser
    and must not be handed the app's own trust by an accident of URL parsing.
    """
    port = api.rsplit(":", 1)[1]
    response = _convert_file(api, Origin=f"http://evil.example@127.0.0.1:{port}")

    assert _refused_cross_site(response)


def test_another_loopback_port_is_not_this_app():
    """The precise case _origin_is_own's port comparison exists for.

    Asserted against the function rather than over HTTP, because it cannot be shown over HTTP
    from this test session: unfrozen, the dev allowance deliberately accepts every loopback
    origin, so a live request from http://localhost:3000 is allowed here and would be refused
    in a frozen build. _origin_is_own is the half that ships, and it is the half that has to
    tell one loopback port from another.
    """
    assert main._origin_is_own("http://localhost:8765", "127.0.0.1:8765")
    assert not main._origin_is_own("http://localhost:3000", "127.0.0.1:8765")
    assert not main._origin_is_own("http://localhost", "127.0.0.1:8765")
    assert not main._origin_is_own("https://127.0.0.1:8765", "127.0.0.1:8765")
    assert not main._origin_is_own("http://evil.example:8765", "127.0.0.1:8765")


def test_a_loopback_name_the_server_does_not_bind_still_counts_as_the_app():
    """Pinned as a known, accepted looseness rather than left to be rediscovered.

    Uvicorn binds 127.0.0.1 only, yet an Origin of http://[::1]:<same port> is accepted,
    because the guard compares the Host header's port rather than the socket's. Reaching it
    needs something already listening on [::1] at this app's port, which needs local code
    execution, and a browser would still label such a page cross-site. Tightening it means
    threading the bound port through to the middleware.
    """
    assert main._origin_is_own("http://[::1]:8765", "127.0.0.1:8765")


@pytest.mark.parametrize("route", ["/api/pick-folder", "/api/pick-files"])
def test_the_native_pickers_are_not_reachable_cross_site(api, route):
    """These open a native dialog over whatever the user is doing. Refusing in the middleware
    means the route never ran, rather than running and failing for some unrelated reason."""
    response = requests.post(
        f"{api}{route}", headers={"Origin": EVIL, "Sec-Fetch-Site": "cross-site"}, timeout=30
    )

    assert _refused_cross_site(response)


def test_settings_are_not_writable_cross_site(api):
    """A JSON body needs a preflight this app never answers, so this was already refused.
    Pinned anyway: the guard should not be the only thing standing between a website and the
    user's stored API keys, and a future content-type relaxation would be caught here."""
    response = requests.put(
        f"{api}/api/settings",
        json={"claude_api_key": "attacker-controlled"},
        headers={"Origin": EVIL, "Sec-Fetch-Site": "cross-site"},
        timeout=30,
    )

    assert _refused_cross_site(response)


def test_the_update_apply_route_ignores_a_body_supplied_url(monkeypatch):
    """The body used to choose what the server downloaded and launched.

    This asserts on the observable SIDE EFFECT, not on the status envelope. An earlier
    version checked only that the response was a normal update status and that the body did
    not echo "evil.example", and a security review proved it passed with the hole fully
    reintroduced: "running" is exactly what a successful hijack returns, and the response
    never echoed the URL either way. The only honest question is what reached the installer.
    """
    handed_to_installer = []
    monkeypatch.setattr(
        app_updates, "_run_installer_update", lambda url: handed_to_installer.append(url)
    )
    # Force the frozen branch: unfrozen, this short-circuits at the editable-install check
    # long before any URL is read, which is another way the old test could not fail.
    monkeypatch.setattr(app_updates, "is_frozen", lambda: True)
    monkeypatch.setattr(
        app_updates,
        "check_for_app_update",
        lambda: {
            "configured": True,
            "error": None,
            "update_available": True,
            "download_url": (
                f"https://github.com/{app_updates.DEFAULT_APP_REPO}"
                "/releases/download/v9.9.9/Omnivert-Setup-9.9.9.exe"
            ),
        },
    )

    with TestClient(main.app, base_url="http://127.0.0.1:8765") as client:
        response = client.post(
            "/api/app/updates/apply",
            json={"download_url": "https://evil.example/payload.exe"},
            headers={"Origin": "http://127.0.0.1:8765", "Sec-Fetch-Site": "same-origin"},
        )

    assert response.status_code == 200
    # The frozen path hands off to a daemon thread; wait for it rather than sleeping blind.
    deadline = time.monotonic() + 10
    while not handed_to_installer and time.monotonic() < deadline:
        time.sleep(0.02)
    assert handed_to_installer, "the frozen update path never ran, so this proved nothing"
    assert all("evil.example" not in url for url in handed_to_installer), (
        f"the body chose what was installed: {handed_to_installer}"
    )
    assert all(
        url.startswith(f"https://github.com/{app_updates.DEFAULT_APP_REPO}/releases/download/")
        for url in handed_to_installer
    )

    with app_updates._lock:
        app_updates._state.update(
            {"state": "idle", "message": None, "output": None, "restart_required": False}
        )


# --- the app's own traffic still works ---------------------------------------------------

def test_the_window_can_convert(api):
    """The desktop window loads this exact origin, so its fetches carry it back."""
    response = _convert_file(api, Origin=api, **{"Sec-Fetch-Site": "same-origin"})

    assert response.status_code == 200


def test_a_loopback_alias_on_the_same_port_counts_as_the_app(api):
    """The window may be addressed as localhost while Host arrives as 127.0.0.1.

    Only this app answers on this port, so matching by loopback name and port rather than by
    exact string costs nothing an attacker could take.
    """
    port = api.rsplit(":", 1)[1]
    response = _convert_file(
        api, Origin=f"http://localhost:{port}", **{"Sec-Fetch-Site": "same-origin"}
    )

    assert response.status_code == 200


def test_a_top_level_navigation_is_allowed(api):
    """Sec-Fetch-Site: none is the address bar, a bookmark, or the window opening its own URL.
    The static frontend is served this way."""
    response = requests.get(
        f"{api}/api/health", headers={"Sec-Fetch-Site": "none"}, timeout=30
    )

    assert response.status_code == 200


def test_a_client_that_sends_neither_header_is_allowed(api):
    """The deliberate fail-open, pinned so it stays deliberate.

    curl, the update checker and this test suite send neither header. Allowing them leaves a
    cross-site GET from a browser predating Sec-Fetch-Site, which can only reach responses it
    was already unable to read; every state-changing shape carries an Origin. If this is ever
    tightened to fail closed, this test should be rewritten, not deleted.
    """
    response = requests.get(f"{api}/api/health", timeout=30)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "port",
    ["5173", "5174", "4321"],
    ids=["default-port", "port-taken-so-vite-moved", "explicitly-configured"],
)
def test_the_vite_proxy_works_on_any_port_without_the_dev_allowance(api, port):
    """``npm run dev`` proxies /api here and must keep working, on whatever port Vite got.

    Vite ships strictPort false, so it silently moves to 5174 when 5173 is taken. That was
    once the argument for allowing ANY loopback origin, and a security review showed the
    argument does not hold: `frontend/vite.config.ts` proxies /api, and Vite's changeOrigin
    defaults to false, so the backend sees Host AND Origin as the same Vite origin and
    `_origin_is_own` matches on its own. Port drift is handled there, not by the allowance.

    This test pins that, with the dev allowance forced OFF, so the day someone widens
    `_is_dev_origin` again to "fix" port drift, it is visible that port drift was never the
    thing it fixed.
    """
    origin = f"http://localhost:{port}"
    with mock.patch.object(main, "_DEV_MODE", False):
        response = requests.post(
            f"{api}/api/convert/file",
            files={"files": ("x.txt", b"data", "text/plain")},
            data={"options": "{}"},
            headers={"Host": f"localhost:{port}", "Origin": origin,
                     "Sec-Fetch-Site": "same-origin"},
            timeout=30,
        )

    assert response.status_code == 200


def test_the_dev_allowance_does_not_extend_past_loopback(api):
    """Wide enough for any dev port, not wide enough to be a hole. A `--host` dev server
    reached through the machine's LAN address is refused: use localhost."""
    for origin in ("http://192.168.1.10:5173", "http://evil.example:5173", EVIL):
        assert not main._is_dev_origin(origin), origin
    assert _refused_cross_site(_convert_file(api, Origin="http://192.168.1.10:5173"))


def test_cors_is_deliberately_narrower_than_the_guard():
    """CORS grants the right to READ a response; the guard only decides whether a request
    runs. The documented dev setup proxies /api through Vite, so the browser sees same-origin
    and CORS is not involved there at all. No reason to widen a read grant to cover a port
    collision that only affects the guard."""
    cors = [m for m in main.app.user_middleware if "CORSMiddleware" in repr(m)]
    assert cors, "CORS middleware is expected in a non-frozen build"
    allowed = cors[0].kwargs["allow_origins"]

    assert allowed == list(main._DEV_CORS_ORIGINS)
    # The guard is now exactly as permissive as CORS, not wider. It used to allow any
    # loopback origin, which meant a page on ANY local port could drive the API while CORS
    # still refused it the response. Refusing the request outright is the stronger half, so
    # the two lists are deliberately the same one now.
    assert main._is_dev_origin("http://localhost:5173")
    assert not main._is_dev_origin("http://localhost:5174")
    assert not main._is_dev_origin("http://localhost:3000")


def test_the_dev_allowance_is_absent_from_a_frozen_build():
    """The one property a shipped build depends on, and the one no other test here can see.

    Every other test in this file runs unfrozen, where http://localhost:5173 is allowed. That
    allowance must not exist in the installed app. ``_DEV_MODE`` is read once at import, so
    checking it needs a fresh interpreter with ``sys.frozen`` set before ``omnivert.main`` is
    first imported, which is what PyInstaller does.
    """
    code = (
        "import sys; sys.frozen = True;"
        "from omnivert import main;"
        "print(main._DEV_MODE,"
        " any('CORSMiddleware' in repr(m) for m in main.app.user_middleware))"
    )
    # Point the child at the source tree this session actually loaded. Without it the child
    # imports whatever ``omnivert`` is installed, which for an editable install is a
    # different checkout, and the test would then be reporting on the wrong code.
    src = str(Path(main.__file__).resolve().parents[1])
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "PYTHONPATH": src},
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split() == ["False", "False"], proc.stdout


# --- the DNS-rebinding guard -------------------------------------------------------------

def test_a_rebound_host_is_still_refused(api):
    """_guard_host's own case, pinned because _split_host_port is now shared with the
    cross-origin guard and a change there could quietly widen this one."""
    response = requests.get(
        f"{api}/api/health", headers={"Host": "attacker.example"}, timeout=30
    )

    assert response.status_code == 403
    assert response.json()["detail"] == BAD_HOST_DETAIL


@pytest.mark.parametrize(
    "host, allowed",
    [
        ("127.0.0.1:8765", True),
        ("localhost:8765", True),
        ("localhost", True),
        ("[::1]:8765", True),
        ("[::1]", True),
        ("attacker.example:8765", False),
        ("attacker.example", False),
    ],
)
def test_host_header_parsing(host, allowed):
    """Bracketed IPv6 does not split on the last colon the way host:port does."""
    hostname, _ = main._split_host_port(host)
    assert (hostname in main._ALLOWED_API_HOSTS) is allowed


def test_a_host_without_a_port_defaults_to_80():
    assert main._split_host_port("localhost") == ("localhost", 80)
    assert main._split_host_port("127.0.0.1:8765") == ("127.0.0.1", 8765)
    assert main._split_host_port("[::1]:8765") == ("::1", 8765)


# --- the interactive API docs ---------------------------------------------------------
#
# /docs and /redoc are HTML pages that load their JavaScript from cdn.jsdelivr.net. A frozen
# build serving them means the app pulls remote script into the origin its unauthenticated
# local API trusts. Both halves are pinned: off when frozen, on in dev.


def _docs_app(frozen: bool):
    """Rebuild the app module with sys.frozen set the way the test needs it."""
    import importlib

    with mock.patch.object(sys, "frozen", frozen, create=True):
        return importlib.reload(main)


def test_a_frozen_build_serves_no_api_docs():
    module = _docs_app(frozen=True)
    try:
        assert module._DEV_MODE is False
        client = TestClient(module.app, base_url="http://127.0.0.1:8765")
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404, f"{path} was served by a frozen build"
    finally:
        _docs_app(frozen=False)


def test_dev_keeps_the_api_docs():
    module = _docs_app(frozen=False)
    assert module._DEV_MODE is True
    client = TestClient(module.app, base_url="http://127.0.0.1:8765")
    assert client.get("/openapi.json").status_code == 200


def test_the_frontend_path_is_never_relative():
    """An unset _MEIPASS used to make this ``Path("web")``, resolved against the working
    directory, so a stray ``web`` folder beside the process became the served frontend."""
    with mock.patch.object(main.Path, "exists", lambda self: False):
        resolved = main._frontend_dist()
    assert resolved.is_absolute(), f"{resolved} is relative"


def test_a_refused_setting_is_a_422_not_a_500():
    client = TestClient(main.app, base_url="http://127.0.0.1:8765")
    response = client.put("/api/settings", json={"claude_base_url": "http://attacker.example/"})
    assert response.status_code == 422
    assert "https" in response.json()["detail"].lower()


def test_the_folder_walk_stops_at_the_limit(tmp_path):
    """The cap used to be applied AFTER walking the whole tree, so the walk was the hang it
    claimed to prevent. _list_folder now stops one past the limit."""
    for i in range(main.MAX_BATCH_FILES + 50):
        (tmp_path / f"f{i}.txt").write_text("x", encoding="utf-8")
    found = main._list_folder(tmp_path, recursive=True)
    assert len(found) == main.MAX_BATCH_FILES + 1, (
        f"walked {len(found)} files instead of stopping at {main.MAX_BATCH_FILES + 1}"
    )


def test_the_folder_route_reports_the_limit_without_claiming_a_total(tmp_path):
    for i in range(main.MAX_BATCH_FILES + 5):
        (tmp_path / f"f{i}.txt").write_text("x", encoding="utf-8")
    client = TestClient(main.app, base_url="http://127.0.0.1:8765")
    response = client.post(
        "/api/convert/folder", json={"path": str(tmp_path), "recursive": True, "options": {}}
    )
    assert response.status_code == 400
    assert "more than" in response.json()["detail"]
