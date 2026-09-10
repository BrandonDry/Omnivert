"""SSRF / local-file guard for user-supplied conversion URLs.

The conversion engine's ``convert_uri`` accepts ``file://``, ``data:`` and ``http(s)://``.
The URL input is user-facing, so we restrict it to public ``http(s)`` targets and refuse
hosts that resolve to loopback / private / link-local / reserved ranges: cloud metadata
(169.254.169.254), LAN services, and the app's own files (``file:///…/settings.json``).

Two halves live here. ``blocked_reason`` is the policy: given a URL, may it be fetched.
``guarded_session`` is the enforcement: a ``requests.Session`` that applies that policy to
every hop of a redirect chain and puts a timeout on every fetch. The engine has to be handed
that session (``ConversionService._construct``), because the one it builds for itself
follows redirects anywhere, forever, with no deadline.

This is best-effort, matched to a single-user desktop tool. Three limits are known and
accepted rather than overlooked:

* DNS is resolved once per hop here and again by urllib3 when it connects, so a determined
  rebinding attacker can still race the two. Fetching with a pinned IP is the real fix and
  is not warranted at this scope.
* An unresolvable host fails OPEN (see the gaierror branch below). That is only safe while
  the engine resolves through the same resolver we just used, which is why the numeric host
  encodings ``test_url_guard.py`` documents are not exploitable on Windows: its resolver
  refuses them. glibc resolves several of them, so on Linux those become a live loopback
  bypass. Omnivert ships to Windows only, but ``pyproject.toml`` merely classifies the OS, it
  does not stop an install elsewhere.
* Nothing caps the size of an allowed response. The destination and the deadline are bounded;
  the volume is not, so a permitted URL can still return a body large enough to hurt.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

_ALLOWED_SCHEMES = {"http", "https"}

# Connect and read timeouts, in seconds, for every fetch the engine makes on our behalf.
# ``MarkItDown.convert_uri`` calls ``session.get(uri, stream=True)`` with no timeout at all,
# so a server that accepts the connection and then says nothing holds the anyio worker thread
# the conversion is running on for as long as it likes. anyio runs 40 of those, and the UI is
# served by the same process, so enough of them stop the app answering its own window.
FETCH_TIMEOUT = (10, 60)

# Redirect hops we are willing to walk. requests defaults to 30, which is 30 fetches on one
# thread and 30 chances for a chain to wander somewhere the user never asked to go. Ten
# because ordinary chains are longer than they look: a shortener, then http to https, then
# the canonical host, then a locale, then the page.
MAX_REDIRECTS = 10

# The Accept header MarkItDown sets on the session it builds for itself. Passing our own
# session replaces that one, so it has to be reproduced here: without it servers that offer
# a Markdown rendering of a page stop being asked for it, and every URL conversion quietly
# gets worse. Kept verbatim from markitdown._markitdown.MarkItDown.__init__.
_ENGINE_ACCEPT = "text/markdown, text/html;q=0.9, text/plain;q=0.8, */*;q=0.1"


class BlockedUrlError(Exception):
    """Raised mid-fetch when a redirect hop points at something the guard refuses.

    ``conversion._classify`` maps this to the same ``blocked_url`` error kind the up-front
    check produces, so the user sees one explanation whichever hop was refused.
    """


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


class _GuardedAdapter(HTTPAdapter):
    """Applies ``blocked_reason`` to every hop, and a timeout to every fetch.

    requests walks a redirect chain by calling the adapter once per hop, so this is the one
    place that sees all of them. Checking only the URL the user typed left the guard testing
    hop 1 of a chain the attacker chooses the rest of: a public URL passes, answers
    ``302 Location: http://127.0.0.1:<port>/api/settings``, and the engine fetches the app's
    own API on hop 2. Every target the guard exists to refuse was one redirect away.
    """

    def send(self, request, **kwargs):
        reason = blocked_reason(request.url)
        if reason:
            raise BlockedUrlError(reason)
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = FETCH_TIMEOUT
        return super().send(request, **kwargs)


def guarded_session() -> requests.Session:
    """Return the ``requests`` session the conversion engine must fetch URLs through."""
    session = requests.Session()
    session.headers.update({"Accept": _ENGINE_ACCEPT})
    session.max_redirects = MAX_REDIRECTS
    # One adapter per scheme, the way requests builds its own sessions. Each carries its own
    # connection pool, and a redirect that crosses schemes then swaps adapters rather than
    # reusing one pool for both.
    session.mount("http://", _GuardedAdapter())
    session.mount("https://", _GuardedAdapter())

    # ``trust_env`` is left at its default True, so HTTP_PROXY / HTTPS_PROXY still apply.
    # That is a deliberate trade, not an oversight. On a machine whose only route off the
    # network is a corporate proxy, ignoring it makes the URL tab fail on every site, which
    # is a worse outcome than the gap it leaves. Name the gap plainly: with a proxy set, the
    # PROXY resolves the hostname, not this process, so the DNS half of the check above
    # describes a lookup that never governs the connection. What survives is the half that
    # needs no DNS (http://127.0.0.1/, http://169.254.169.254/, http://10.0.0.5/ and every
    # other literal address are parsed, not resolved, and are still refused on every hop),
    # and the observation that a proxy's loopback and private ranges are the proxy's own, not
    # the user's machine, so proxied traffic reaches local services less easily rather than
    # more. A LAN host named by DNS, resolved differently by the proxy than by us, is the
    # case that gets through. SECURITY.md carries this for users.
    return session
