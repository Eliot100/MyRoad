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
from myroad_core.auth.origin import ALLOWED_ORIGINS_ENV, same_origin_ok
from myroad_core.auth.ownership import AGENT_ALLOWED_PATHS_ENV, may_act_on_path, path_author
from myroad_core.auth.principal import Principal, resolve_principal
from myroad_core.auth.sessions import (
    DEV_INSECURE_COOKIES_ENV,
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    SessionMixin,
    cookie_secure,
)

__all__ = [
    "AGENT_ALLOWED_PATHS_ENV",
    "ALLOWED_ORIGINS_ENV",
    "AGENT_ID_ENV",
    "AGENT_TOKEN_ENV",
    "DEFAULT_AGENT_ID",
    "DEV_INSECURE_COOKIES_ENV",
    "Principal",
    "SESSION_COOKIE",
    "SESSION_TTL_SECONDS",
    "SessionMixin",
    "agent_access_enabled",
    "agent_actor_id",
    "agent_credential_matches",
    "cookie_secure",
    "may_act_on_path",
    "path_author",
    "resolve_principal",
    "same_origin_ok",
]
