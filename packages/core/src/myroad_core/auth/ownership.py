"""Who may act on a path through /tools/* (Cyber security review of #46).

Rule:
- A logged-in user may act only on paths they authored
  (``paths.author_id`` == their user id).
- The agent credential may act only on paths the agent authored
  (``paths.author_id`` == ``MYROAD_AGENT_ID``) or on path ids explicitly
  listed in ``MYROAD_AGENT_ALLOWED_PATHS`` (comma-separated, server env).
- Anyone may create a new draft; they become its author.

``paths.author_id`` is set once when the path is created and no /tools op
can change it (unlike ``actors.authorId`` inside the document). A path the
principal may not touch is answered exactly like a missing one (404), so the
API does not reveal which path ids exist.
"""
from __future__ import annotations

import os
from typing import Any

from myroad_core.auth.principal import Principal

__all__ = ["AGENT_ALLOWED_PATHS_ENV", "may_act_on_path", "path_author"]

AGENT_ALLOWED_PATHS_ENV = "MYROAD_AGENT_ALLOWED_PATHS"


def path_author(store: Any, path_id: str) -> str | None:
    row = store._conn.execute("SELECT author_id FROM paths WHERE path_id = ?", (path_id,)).fetchone()
    return row[0] if row else None


def _agent_allowed_paths() -> set[str]:
    raw = os.environ.get(AGENT_ALLOWED_PATHS_ENV) or ""
    return {p.strip() for p in raw.split(",") if p.strip()}


def may_act_on_path(store: Any, principal: Principal, path_id: str) -> bool:
    author = path_author(store, path_id)
    if author is None:
        return False
    if author == principal.actor_id:
        return True
    return principal.kind == "agent" and path_id in _agent_allowed_paths()
