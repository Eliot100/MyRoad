"""Same-origin check for state-changing browser form POSTs (CSRF defence).

The session cookie is SameSite=Lax, which already stops most cross-site form
posts. This adds a server-side check on top: a POST/PUT/PATCH/DELETE to the UI
must carry an ``Origin`` (or, if a browser left it out, a ``Referer``) whose
origin is this site or one listed in ``MYROAD_ALLOWED_ORIGINS``. A request with
neither header, or with ``Origin: null``, is refused.

"This site" is ``<scheme>://<Host header>`` as the app sees it. Behind a TLS
proxy, run uvicorn with ``--proxy-headers`` (and ``--forwarded-allow-ips`` set
to the proxy address) so the scheme is ``https``, or list the public origin in
``MYROAD_ALLOWED_ORIGINS``.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

from starlette.requests import Request

ALLOWED_ORIGINS_ENV = "MYROAD_ALLOWED_ORIGINS"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _origin_of(url: str) -> str | None:
    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


def allowed_origins(request: Request) -> set[str]:
    own = f"{request.url.scheme}://{(request.headers.get('host') or request.url.netloc).lower()}"
    extra = {
        o for o in (_origin_of(x) for x in os.environ.get(ALLOWED_ORIGINS_ENV, "").split(",") if x.strip()) if o
    }
    return {own.lower(), *extra}


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
