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
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def blocked_reason(url: str) -> Optional[str]:
    """Return a human-readable reason the URL must not be fetched, or ``None`` if allowed."""
    parsed = urlparse((url or "").strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        shown = scheme or "no scheme"
        return (
            f"Only http and https URLs are allowed (got '{shown}'). Local files and other "
            "schemes are blocked for safety."
        )

    host = parsed.hostname
    if not host:
        return "That URL has no host."

    port = parsed.port or (443 if scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        # Unknown host — let the engine surface its normal "couldn't fetch" error.
        return None

    for info in infos:
        ip = info[4][0]
        if _ip_is_blocked(ip):
            return (
                f"That URL resolves to a non-public address ({ip}) and is blocked to prevent "
                "access to local or internal resources."
            )
    return None
