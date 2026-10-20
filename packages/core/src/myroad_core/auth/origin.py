"""Same-origin check for state-changing browser form POSTs (CSRF defence).

The session cookie is SameSite=Lax, which already stops most cross-site form
posts. This adds a server-side check on top: a POST/PUT/PATCH/DELETE to the UI
must carry an ``Origin`` (or, if a browser left it out, a ``Referer``) whose
origin is this site or one listed in ``MYROAD_ALLOWED_ORIGINS``. A request with
neither header, or with ``Origin: null``, is refused.

"This site" is ``<scheme>://<Host header>`` as the app sees it. Origins are
compared normalised: scheme and host lower-case, and the default port dropped
(``:80`` for http, ``:443`` for https), so ``https://myroad.example:443`` and
``https://myroad.example`` are the same origin (#53). Other ports must match.

Behind a TLS-terminating proxy the app sees plain ``http``; see the README
section "TLS proxy" for the setup: forward ``Host`` unchanged and set
``X-Forwarded-Proto``, run uvicorn with ``--proxy-headers
--forwarded-allow-ips=<proxy address>`` (never ``*``), or list the public origin
in ``MYROAD_ALLOWED_ORIGINS``.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

from starlette.requests import Request

ALLOWED_ORIGINS_ENV = "MYROAD_ALLOWED_ORIGINS"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


DEFAULT_PORTS = {"http": 80, "https": 443}


def _origin_of(url: str) -> str | None:
    """``scheme://host[:port]`` normalised (lower-case, default port dropped), or None."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port  # ValueError for a bad port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if not scheme or not host or parts.username is not None or parts.password is not None:
        return None
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    if port is None or DEFAULT_PORTS.get(scheme) == port:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def allowed_origins(request: Request) -> set[str]:
    host = request.headers.get("host") or request.url.netloc
    own = _origin_of(f"{request.url.scheme}://{host}")
    extra = {
        o for o in (_origin_of(x) for x in os.environ.get(ALLOWED_ORIGINS_ENV, "").split(",") if x.strip()) if o
    }
    return {*({own} if own else set()), *extra}


def same_origin_ok(request: Request) -> bool:
    """True for safe methods, or when Origin/Referer names an allowed origin."""
    if request.method.upper() not in UNSAFE_METHODS:
        return True
    origin = request.headers.get("origin")
    if origin is not None:
        candidate = _origin_of(origin) if origin.strip().lower() != "null" else None
    else:
        referer = request.headers.get("referer")
        candidate = _origin_of(referer) if referer else None
    return candidate is not None and candidate in allowed_origins(request)
