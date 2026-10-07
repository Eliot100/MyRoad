"""Server-side auth: login sessions, agent credential, request principal.

Nothing here stores a raw session id, credential, or provider key.
"""
from myroad_core.auth.agent_credential import (
    AGENT_ID_ENV,
    AGENT_TOKEN_ENV,
    DEFAULT_AGENT_ID,
    agent_access_enabled,
    agent_actor_id,
    agent_credential_matches,
)
from myroad_core.auth.principal import Principal, resolve_principal
from myroad_core.auth.sessions import SESSION_COOKIE, SESSION_TTL_SECONDS, SessionMixin

__all__ = [
    "AGENT_ID_ENV",
    "AGENT_TOKEN_ENV",
    "DEFAULT_AGENT_ID",
    "Principal",
    "SESSION_COOKIE",
    "SESSION_TTL_SECONDS",
    "SessionMixin",
    "agent_access_enabled",
    "agent_actor_id",
    "agent_credential_matches",
    "resolve_principal",
]
