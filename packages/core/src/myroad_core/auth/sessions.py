"""Server-side login sessions (SQLite).

The browser holds an opaque random session id in an httponly cookie. The
database keeps only its SHA-256 digest, the user id, and the expiry, so a copy
of the DB cannot be replayed as a cookie. A session id is 256 random bits, so a
fast digest is enough (no salt or slow hash needed, unlike short login codes).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

__all__ = ["SESSION_COOKIE", "SESSION_TTL_SECONDS", "SessionMixin", "session_digest"]

SESSION_COOKIE = "myroad_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 days

_SESSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS auth_sessions (
  sid_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
"""


def session_digest(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SessionMixin:
    """Mixin expecting self._conn (sqlite3 connection)."""

    def ensure_session_schema(self) -> None:
        self._conn.executescript(_SESSION_SCHEMA)
        self._conn.commit()

    def create_session(self, user_id: str, *, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
        """Start a session for an existing user. Returns the raw id (cookie value) once."""
        if not user_id:
            raise ValueError("auth_required")
        session_id = secrets.token_urlsafe(32)
        now = _now()
        self._conn.execute(
            "INSERT INTO auth_sessions (sid_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
            (
                session_digest(session_id),
                user_id,
                now.isoformat(),
                (now + timedelta(seconds=ttl_seconds)).isoformat(),
            ),
        )
        self._conn.commit()
        return session_id

    def get_session_user(self, session_id: str | None) -> str | None:
        """User id for a live session id, or None (unknown, expired, or revoked)."""
        if not session_id or len(session_id) > 256:
            return None
        row = self._conn.execute(
            "SELECT user_id, expires_at, revoked_at FROM auth_sessions WHERE sid_hash = ?",
            (session_digest(session_id),),
        ).fetchone()
        if not row or row["revoked_at"]:
            return None
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            return None
        if expires <= _now():
            return None
        return row["user_id"]

    def revoke_session(self, session_id: str | None) -> None:
        if not session_id:
            return
        self._conn.execute(
            "UPDATE auth_sessions SET revoked_at = ? WHERE sid_hash = ? AND revoked_at IS NULL",
            (_now().isoformat(), session_digest(session_id)),
        )
        self._conn.commit()
