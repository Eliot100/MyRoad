"""Resolve who is calling: a logged-in user (session cookie) or the agent.

The actor always comes from here, never from the request body.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from myroad_core.auth.agent_credential import agent_actor_id, agent_credential_matches
from myroad_core.auth.sessions import SESSION_COOKIE

__all__ = ["Principal", "resolve_principal"]


@dataclass(frozen=True)
class Principal:
    actor_id: str
    kind: Literal["user", "agent"]
    agent_id: str | None = None


def _bearer(headers: Any) -> str | None:
    raw = headers.get("authorization") or ""
    scheme, _, value = raw.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return value.strip() or None


def resolve_principal(request: Any, store: Any) -> Principal | None:
    """Return the authenticated principal, or None (caller answers 401).

    - ``Authorization: Bearer`` must match the agent credential. A wrong bearer
      is refused outright (no fallback to the cookie).
    - Otherwise the ``myroad_session`` cookie must name a live session of an
      existing user.
    """
    if request.headers.get("authorization"):
        presented = _bearer(request.headers)
        if presented and agent_credential_matches(presented):
            agent = agent_actor_id()
            return Principal(actor_id=agent, kind="agent", agent_id=agent)
        return None
    user_id = store.get_session_user(request.cookies.get(SESSION_COOKIE))
    if not user_id or not store.get_learner(user_id):
        return None
    return Principal(actor_id=user_id, kind="user", agent_id=None)
