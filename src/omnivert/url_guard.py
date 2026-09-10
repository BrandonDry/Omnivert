"""SSRF / local-file guard for user-supplied conversion URLs.

The conversion engine's ``convert_uri`` accepts ``file://``, ``data:`` and ``http(s)://``.
The URL input is user-facing, so we restrict it to public ``http(s)`` targets and refuse
hosts that resolve to loopback / private / link-local / reserved ranges — cloud metadata
(169.254.169.254), LAN services, and the app's own files (``file:///…/settings.json``).

This is best-effort, matched to a single-user desktop tool: DNS is resolved once here, so a
determined DNS-rebinding attacker could still race the engine's own resolution. Full
protection would require fetching with a pinned IP, which isn't warranted at this scope.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


def _ip_is_blocked(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    # ``is_global`` is the broad test and is the one to trust: it already excludes private,
    # loopback, link-local, reserved, unspecified AND carrier-grade NAT (100.64.0.0/10),
    # which the previous hand-listed properties missed. Multicast still has to be named
    # separately because some Python versions report a multicast address as global.
    return not addr.is_global or addr.is_multicast


_MALFORMED = "That URL is malformed and cannot be fetched."


def blocked_reason(url: str) -> Optional[str]:
    """Return a human-readable reason the URL must not be fetched, or ``None`` if allowed."""
    # urlparse and .port both raise on inputs a user can easily type: an unclosed IPv6
    # bracket ("http://[::1"), a port that is not a number or is out of range
    # ("http://x:99999/"). Those escaped as a 500 instead of the structured error every
    # other conversion failure returns, so parsing is guarded end to end.
    try:
        parsed = urlparse((url or "").strip())
        scheme = (parsed.scheme or "").lower()
    except ValueError:
        return _MALFORMED
    if scheme not in _ALLOWED_SCHEMES:
        shown = scheme or "no scheme"
        return (
            f"Only http and https URLs are allowed (got '{shown}'). Local files and other "
            "schemes are blocked for safety."
        )

    host = parsed.hostname
    if not host:
        return "That URL has no host."

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError:
        return _MALFORMED

    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        # Unknown host: let the engine surface its normal "couldn't fetch" error. This is a
        # deliberate fail-open, and it is only safe while the engine resolves through the
        # same getaddrinfo we just used. See test_url_guard.py for the reasoning, and note
        # it does NOT hold when an HTTP proxy is configured, because the proxy resolves the
        # name instead of this process.
        return None
    except (UnicodeError, ValueError):
        # An over-long or otherwise un-encodable hostname trips the idna codec.
        return _MALFORMED

    for info in infos:
        ip = info[4][0]
        if _ip_is_blocked(ip):
            return (
                f"That URL resolves to a non-public address ({ip}) and is blocked to prevent "
                "access to local or internal resources."
            )
    return None
