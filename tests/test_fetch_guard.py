"""The session the conversion engine fetches URLs through.

``blocked_reason`` decides whether a URL may be fetched; ``test_url_guard.py`` covers that.
This file covers the other half, which is whether the decision is ever actually applied.
It was not: the engine builds its own ``requests.Session`` and calls
``session.get(uri, stream=True)`` on it, so the guard saw the URL the user typed and the
engine then followed a 302 anywhere it was pointed, with no deadline.

The servers here are real sockets on loopback. A test that stubs the fetch cannot tell a
per-hop check from a check-once-up-front one, which is exactly the distinction that was
wrong.
"""

from __future__ import annotations

import http.server
import io
import threading

import pytest
import requests

from omnivert import url_guard


# --- loopback test servers -------------------------------------------------------------

def _start(handler_cls) -> http.server.HTTPServer:
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _url(server: http.server.HTTPServer, path: str) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}{path}"


class _Quiet(http.server.BaseHTTPRequestHandler):
    """BaseHTTPRequestHandler logs every request to stderr, which drowns pytest output."""

    def log_message(self, *args):
        pass


@pytest.fixture
def victim():
    """Stands in for the loopback services the guard exists to keep the engine away from.

    Records what reached it, so a test can assert on the request that was never made rather
    than only on the exception that was raised.
    """
    hits: list[str] = []

    class Handler(_Quiet):
        def do_GET(self):
            hits.append(self.path)
            body = b"body-from-the-target"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = _start(Handler)
    server.hits = hits  # type: ignore[attr-defined]
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def redirector():
    """Factory for a server that answers every request with 302 to a given Location."""
    started: list[http.server.HTTPServer] = []

    def make(location: str) -> http.server.HTTPServer:
        class Handler(_Quiet):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", location)
                self.send_header("Content-Length", "0")
                self.end_headers()

        server = _start(Handler)
        started.append(server)
        return server

    yield make
    for server in started:
        server.shutdown()
        server.server_close()


@pytest.fixture
def allow_everything(monkeypatch):
    """Neutralise the policy so a test can exercise the plumbing around it."""
    monkeypatch.setattr(url_guard, "blocked_reason", lambda url: None)


# --- the redirect hole ------------------------------------------------------------------

def test_a_plain_session_follows_a_redirect_onto_loopback(victim, redirector):
    """Pins the behaviour the guarded session exists to stop.

    This is the shape of the reproduction: a server the user asked for answers
    ``302 Location: http://127.0.0.1:<port>/...`` and stock requests fetches it without
    asking anyone. If this ever stops holding, the fix below is guarding something that no
    longer happens and the comments around it are stale.
    """
    target = _url(victim, "/api/settings")
    hop = redirector(target)

    response = requests.Session().get(_url(hop, "/start"), timeout=10)

    assert response.text == "body-from-the-target"
    assert victim.hits == ["/api/settings"]


def test_a_redirect_to_a_blocked_target_is_refused_mid_chain(monkeypatch, victim, redirector):
    """The guard has to run on every hop, not only on the URL the user typed.

    ``blocked_reason`` is stubbed here to allow the first hop and refuse the second. With the
    real policy the first hop is refused too (both servers are on loopback), and the test
    could then pass against a guard that checks once up front, which is the bug. What the
    real policy decides is ``test_url_guard.py``'s subject; what this asserts is that the
    decision is consulted again after the server has had its say, and that the chain stops
    before the second request leaves.
    """
    target = _url(victim, "/api/settings")
    hop = redirector(target)
    monkeypatch.setattr(
        url_guard,
        "blocked_reason",
        lambda url: "blocked by the test policy" if "/api/settings" in url else None,
    )

    with pytest.raises(url_guard.BlockedUrlError):
        url_guard.guarded_session().get(_url(hop, "/start"))

    assert victim.hits == [], "the redirect target was fetched anyway"


def test_the_real_policy_refuses_a_loopback_url(victim):
    """The same adapter, running the shipped policy rather than a stub."""
    session = url_guard.guarded_session()

    with pytest.raises(url_guard.BlockedUrlError):
        session.get(_url(victim, "/api/settings"))

    assert victim.hits == []


def test_an_allowed_redirect_is_still_followed(allow_everything, victim, redirector):
    """Refusing every redirect would be a cheaper fix and a worse one.

    Plenty of ordinary pages are one 301 away (http to https, a trailing slash, a shortener),
    so the guard has to keep walking chains it does not object to.
    """
    hop = redirector(_url(victim, "/page"))

    response = url_guard.guarded_session().get(_url(hop, "/start"))

    assert response.text == "body-from-the-target"
    assert victim.hits == ["/page"]


def test_a_redirect_loop_is_bounded(allow_everything):
    """A chain has to end even when every hop is allowed.

    requests defaults to 30 hops, which is 30 sequential fetches held on the one anyio worker
    thread the conversion is running on.
    """
    hits: list[str] = []

    class Handler(_Quiet):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/again")
            self.send_header("Content-Length", "0")
            self.end_headers()

    server = _start(Handler)
    try:
        with pytest.raises(requests.TooManyRedirects):
            url_guard.guarded_session().get(_url(server, "/start"))
    finally:
        server.shutdown()
        server.server_close()

    # Asserted against a literal, not against MAX_REDIRECTS. Comparing to the constant the
    # fix sets made this pass with `session.max_redirects = MAX_REDIRECTS` deleted entirely,
    # because it then just restated requests' own default of 30.
    assert url_guard.MAX_REDIRECTS < requests.Session().max_redirects, (
        "the point of this setting is to be tighter than requests own default"
    )
    assert len(hits) <= 11, f"followed {len(hits)} hops, expected the chain to stop at 10"


# --- timeouts ----------------------------------------------------------------------------

def test_every_fetch_carries_a_timeout(monkeypatch, allow_everything):
    """``convert_uri`` passes no timeout, so the session has to supply one.

    Without it a server that accepts the connection and then says nothing holds a threadpool
    worker for as long as it likes, and the UI is served by the same process.
    """
    seen: dict = {}

    def spy(self, request, **kwargs):
        seen.update(kwargs)
        response = requests.Response()
        response.status_code = 204
        response.url = request.url
        response.raw = io.BytesIO(b"")
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", spy)
    url_guard.guarded_session().get("http://example.test/")

    # Asserted on the shape, not only on equality with the constant: comparing only to
    # FETCH_TIMEOUT let `FETCH_TIMEOUT = (None, None)` pass a test named "carries a timeout".
    connect, read = seen["timeout"]
    assert isinstance(connect, (int, float)) and connect > 0, f"no connect timeout: {connect!r}"
    assert isinstance(read, (int, float)) and read > 0, f"no read timeout: {read!r}"
    assert seen["timeout"] == url_guard.FETCH_TIMEOUT


def test_an_explicit_timeout_is_not_overridden(monkeypatch, allow_everything):
    """The default is a floor for callers that pass nothing, not a policy imposed on them."""
    seen: dict = {}

    def spy(self, request, **kwargs):
        seen.update(kwargs)
        response = requests.Response()
        response.status_code = 204
        response.url = request.url
        response.raw = io.BytesIO(b"")
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", spy)
    url_guard.guarded_session().get("http://example.test/", timeout=3)

    assert seen["timeout"] == 3


# --- session construction ----------------------------------------------------------------

def test_the_guarded_adapter_is_mounted_for_both_schemes():
    session = url_guard.guarded_session()
    for probe in ("http://example.test/", "https://example.test/"):
        assert isinstance(session.get_adapter(probe), url_guard._GuardedAdapter)


def test_the_session_keeps_the_engines_accept_header():
    """Passing our own session replaces the one MarkItDown builds, headers included.

    That session asks servers for a Markdown rendering of the page when they offer one, so
    dropping or mistyping the header would quietly degrade every URL conversion rather than
    break it, which is the kind of regression nothing notices.

    Compared against the engine's own session rather than a substring, because
    ``_ENGINE_ACCEPT`` is a hand-copy of a string in markitdown and this repo auto-bumps the
    engine (``.github/workflows/engine-update.yml``). The pipeline that would cause the drift
    is exactly the one a substring assertion cannot catch.
    """
    from markitdown import MarkItDown

    engines_own = MarkItDown()._requests_session.headers["Accept"]
    assert url_guard.guarded_session().headers["Accept"] == engines_own
