"""Ephemeral OpenAI-style API token format check.

The token is accepted only for the duration of a single server-side request.
It must never be written to DB, files, logs, cookies, HTML, or localStorage.
"""
from __future__ import annotations

import re
from typing import Any

# OpenAI-style secret keys and common "sk-..." / "sk-proj-..." shapes.
# Also accept a Bearer-looking opaque token of sufficient length.
_SK_RE = re.compile(r"^sk-[A-Za-z0-9_\-]{16,}$")
_BEARER_RE = re.compile(r"^[A-Za-z0-9_\-.]{32,}$")


def normalize_bearer_token(raw: str | None) -> str:
    """Strip optional 'Bearer ' prefix; return empty string if missing."""
    if raw is None:
        return ""
    text = str(raw).strip()
    if text.lower().startswith("bearer "):
        text = text[7:].strip()
    return text


def looks_like_agent_api_token(raw: str | None) -> bool:
    """True if the value has an OpenAI-style / Bearer API-key shape.

    Does **not** call external APIs by default (format/presence only).
    The raw value is never returned to callers beyond the bool.
    """
    token = normalize_bearer_token(raw)
    if not token:
        return False
    if _SK_RE.match(token):
        return True
    if token.startswith("sk-") and len(token) >= 20:
        return True
    if _BEARER_RE.match(token) and not token.isspace():
        return True
    return False


def verify_agent_token_ephemeral(raw: str | None) -> dict[str, Any]:
    """Check token format and discard the secret immediately.

    Returns a result dict that never includes the token value.
    """
    token = normalize_bearer_token(raw)
    # Keep only a non-secret fingerprint length for diagnostics
    length = len(token)
    ok = looks_like_agent_api_token(token)
    # Explicitly drop reference before return
    del token
    del raw
    return {
        "ok": ok,
        "reason": "ok" if ok else "invalid_or_missing",
        "checkedLength": length,
        "persisted": False,
    }
