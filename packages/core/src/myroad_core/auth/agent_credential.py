"""Server-side agent credential for the /tools/* API.

An external agent sends ``Authorization: Bearer <credential>``. The server
compares it in constant time with the ``MYROAD_AGENT_TOKEN`` env var. When that
env var is unset or empty, agent access is disabled and every bearer is refused.
The agent acts as ``MYROAD_AGENT_ID`` (default ``agent_service``); the caller
cannot choose its own actor id. The credential is never stored or logged.
"""
from __future__ import annotations

import hmac
import os

__all__ = [
    "AGENT_ID_ENV",
    "AGENT_TOKEN_ENV",
    "DEFAULT_AGENT_ID",
    "agent_access_enabled",
    "agent_actor_id",
    "agent_credential_matches",
]

AGENT_TOKEN_ENV = "MYROAD_AGENT_TOKEN"
AGENT_ID_ENV = "MYROAD_AGENT_ID"
DEFAULT_AGENT_ID = "agent_service"

# Very short configured values are treated as unset (misconfiguration guard).
_MIN_CREDENTIAL_LEN = 16


def _configured() -> str:
    value = (os.environ.get(AGENT_TOKEN_ENV) or "").strip()
    return value if len(value) >= _MIN_CREDENTIAL_LEN else ""


def agent_access_enabled() -> bool:
    return bool(_configured())


def agent_actor_id() -> str:
    return (os.environ.get(AGENT_ID_ENV) or "").strip() or DEFAULT_AGENT_ID


def agent_credential_matches(presented: str | None) -> bool:
    expected = _configured()
    if not expected or not presented:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))
