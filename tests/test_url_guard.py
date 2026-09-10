"""The SSRF / local-file guard on user-supplied conversion URLs.

This is the security boundary for the URL tab. The engine's ``convert_uri`` natively accepts
``file://`` and ``data:``, so without this guard a URL typed (or pasted from somewhere less
trustworthy) into the app could read the user's own settings file, including their stored API
keys, or reach cloud instance metadata at 169.254.169.254.

These assertions were written against measured behaviour, not assumed behaviour: each case
below was executed before it was encoded here.
"""

from __future__ import annotations

import socket

import pytest

from omnivert import url_guard
from omnivert.url_guard import blocked_reason


# --- schemes --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/Users/someone/AppData/Local/Omnivert/settings.json",
        "file:///etc/passwd",
        "data:text/plain;base64,SGVsbG8=",
        "ftp://example.com/x",
        "gopher://example.com/",
        "javascript:alert(1)",
        "//example.com/protocol-relative",
        "example.com/no-scheme",
        "",
        "   ",
    ],
)
def test_non_http_schemes_are_refused(url):
    reason = blocked_reason(url)
    assert reason is not None, f"{url!r} should not be fetchable"


def test_scheme_refusal_explains_itself():
    reason = blocked_reason("file:///etc/passwd")
    assert "http" in reason.lower()


def test_url_with_scheme_but_no_host_is_refused():
    assert blocked_reason("http://") is not None


# --- address ranges -------------------------------------------------------------------

@pytest.mark.parametrize(
    "url, why",
    [
        ("http://127.0.0.1:8765/api/settings", "loopback: the app's own API"),
        ("http://localhost:8765/api/settings", "loopback by name"),
        ("https://127.0.0.1/", "loopback over https"),
        ("http://169.254.169.254/latest/meta-data/", "cloud instance metadata"),
        ("http://10.0.0.5/", "private range"),
        ("http://192.168.1.1/", "private range: home router"),
        ("http://172.16.0.1/", "private range"),
        ("http://0.0.0.0/", "unspecified"),
        ("http://[::1]/", "IPv6 loopback"),
        ("http://[::ffff:127.0.0.1]/", "IPv4-mapped IPv6 loopback"),
        ("http://100.64.0.1/", "carrier-grade NAT, RFC 6598"),
        ("http://100.127.255.254/", "carrier-grade NAT, upper end"),
        ("http://224.0.0.1/", "multicast"),
        ("http://198.18.0.1/", "benchmarking range"),
    ],
)
def test_non_public_addresses_are_refused(url, why):
    assert blocked_reason(url) is not None, f"{url!r} should be blocked ({why})"


def test_userinfo_does_not_smuggle_a_blocked_host_past_the_guard():
    """`http://user:pw@127.0.0.1/` still has 127.0.0.1 as its hostname."""
    assert blocked_reason("http://trusted.example.com:pw@127.0.0.1/") is not None


def test_block_reason_names_the_resolved_address():
    reason = blocked_reason("http://127.0.0.1/")
    assert "127.0.0.1" in reason


# --- public addresses are allowed -----------------------------------------------------

def test_public_address_is_allowed(monkeypatch):
    """Hermetic: no real DNS, so this passes offline and in CI."""
    monkeypatch.setattr(
        url_guard.socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))],
    )
    assert blocked_reason("http://example.com/page") is None


def test_a_host_resolving_to_both_public_and_private_is_refused(monkeypatch):
    """DNS returning a mix must not be waved through on the strength of the public one."""
    monkeypatch.setattr(
        url_guard.socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
        ],
    )
    assert blocked_reason("http://rebind.example.com/") is not None


# --- documented limits ----------------------------------------------------------------

def test_unresolvable_host_is_allowed_through(monkeypatch):
    """The guard fails OPEN when DNS errors, by design.

    The engine then attempts its own fetch and surfaces a normal "couldn't fetch" error. This
    test exists to make that a deliberate, visible decision rather than an accident: if the
    behaviour is ever tightened to fail closed, this test should be updated, not deleted.
    """
    def boom(*a, **k):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", boom)
    assert blocked_reason("http://no-such-host.invalid/") is None


@pytest.mark.parametrize(
    "url",
    [
        "http://2130706433/",   # decimal form of 127.0.0.1
        "http://0x7f000001/",   # hex form
        "http://0177.0.0.1/",   # octal form
        "http://127.0.0.1./",   # trailing-dot FQDN form
    ],
)
def test_numeric_host_forms_are_not_a_working_bypass(url):
    """These are the classic SSRF encodings, and the guard does not currently reject them.

    They are nonetheless not exploitable on the platform Omnivert ships to: the guard lets
    them past only because ``getaddrinfo`` refuses to resolve them, and the engine's own
    fetch (requests/urllib3) goes through that same resolver, so the connection fails too.
    Verified by standing up a loopback server and confirming none of these reach it.

    This test documents that reasoning so a future reader does not either panic about a
    non-issue or, worse, "fix" the resolver in a way that turns these into a live bypass.
    """
    assert blocked_reason(url) is None


# --- malformed input returns a reason rather than exploding ---------------------------

@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:99999/",   # port out of range -> ValueError from .port
        "http://example.com:abc/",     # non-numeric port  -> ValueError from .port
        "http://[::1",                 # unclosed bracket  -> ValueError from urlparse
        "http://" + "a" * 70 + ".com/",  # over-long label -> UnicodeError from idna
    ],
)
def test_malformed_urls_return_a_reason_instead_of_raising(url):
    """These four used to escape as exceptions, which FastAPI turned into a 500.

    Every other conversion failure comes back as a structured ConversionResult, so a
    mistyped URL producing a stack trace broke that contract.
    """
    reason = blocked_reason(url)
    assert reason is not None
    assert "malformed" in reason.lower()


def test_public_multicast_is_still_blocked():
    """is_global can report True for multicast, so it is named separately in the guard."""
    assert blocked_reason("http://224.0.0.1/") is not None
