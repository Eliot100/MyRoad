"""Pseudonymous product analytics (issue #208, docs/analytics-events.md, decision 0011).

Own SQLite table ``analytics_events``; no external analytics service. A learner is only ever
written as a random ``analytics_id`` (``analytics_ids`` maps it to the user id inside this DB,
so no server secret is needed and deleting the mapping row unlinks the events).

Switch: ``MYROAD_ANALYTICS`` ("1" on, "0" off). The app default is on; the test suite sets it
to "0" (tests/conftest.py) so only tests that ask for analytics write events.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from typing import Any, Iterable

from myroad_core.store_schema import _iso_now

ANALYTICS_ENV = "MYROAD_ANALYTICS"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analytics_ids (
  user_id TEXT PRIMARY KEY,
  analytics_id TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analytics_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  analytics_id TEXT NOT NULL,
  source TEXT NOT NULL,
  event_type TEXT NOT NULL,
  screen TEXT,
  props_json TEXT NOT NULL DEFAULT '{}',
  client_ts INTEGER,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analytics_events_aid ON analytics_events(analytics_id, event_id);
"""

# Client-sent types (POST /api/events). Anything else is rejected.
CLIENT_EVENT_TYPES = ("tap", "screen_view", "answer_submit")
# Server-emitted types (never accepted from the client).
SERVER_EVENT_TYPES = ("answer", "placement_answer", "placement_result", "solution_seen_continue")
EVENT_TYPES = CLIENT_EVENT_TYPES + SERVER_EVENT_TYPES

# Keys that must never appear anywhere in a payload, at any depth.
PII_KEYS = frozenset(
    {
        "email", "mail", "e_mail", "name", "first_name", "last_name", "firstname", "lastname",
        "full_name", "display_name", "displayname", "firstName", "lastName", "displayName",
        "ip", "ip_address", "ipaddress", "remote_addr", "x_forwarded_for", "user_agent",
        "useragent", "userAgent", "ua", "phone", "user_id", "userId", "learner_id",
    }
)
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6_RE = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}\b")
_UA_RE = re.compile(r"Mozilla/|AppleWebKit|Gecko/|Chrome/|Safari/", re.I)


class PiiError(ValueError):
    """A payload carried a PII key or value."""


def analytics_enabled() -> bool:
    return (os.environ.get(ANALYTICS_ENV) or "1").strip().lower() not in ("0", "false", "no", "off")


def find_pii(payload: Any, _path: str = "$") -> list[str]:
    """Paths in ``payload`` whose key is a PII key or whose string value looks like PII."""
    hits: list[str] = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            key = str(k)
            if key in PII_KEYS or key.lower().replace("-", "_") in PII_KEYS:
                hits.append(f"{_path}.{key}")
            hits.extend(find_pii(v, f"{_path}.{key}"))
    elif isinstance(payload, (list, tuple)):
        for i, v in enumerate(payload):
            hits.extend(find_pii(v, f"{_path}[{i}]"))
    elif isinstance(payload, str):
        if _EMAIL_RE.search(payload) or _IPV4_RE.search(payload) or _IPV6_RE.search(payload) or _UA_RE.search(payload):
            hits.append(_path)
    return hits


def assert_no_pii(payload: Any) -> None:
    hits = find_pii(payload)
    if hits:
        raise PiiError("pii in analytics payload: " + ", ".join(hits))


class AnalyticsMixin:
    """Mixin expecting self._conn (sqlite3 connection)."""

    def ensure_analytics_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def analytics_id_for(self, user_id: str) -> str:
        """Stable random pseudonym for a learner (created on first use)."""
        row = self._conn.execute("SELECT analytics_id FROM analytics_ids WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            return row[0]
        aid = "a_" + secrets.token_hex(12)
        self._conn.execute(
            "INSERT OR IGNORE INTO analytics_ids (user_id, analytics_id, created_at) VALUES (?,?,?)",
            (user_id, aid, _iso_now()),
        )
        self._conn.commit()
        row = self._conn.execute("SELECT analytics_id FROM analytics_ids WHERE user_id = ?", (user_id,)).fetchone()
        return row[0]

    def move_analytics_id(self, from_user_id: str, to_user_id: str) -> None:
        """Keep one pseudonym when a session's learner id changes (e.g. guest -> registered)."""
        if from_user_id == to_user_id:
            return
        has_to = self._conn.execute("SELECT 1 FROM analytics_ids WHERE user_id = ?", (to_user_id,)).fetchone()
        if not has_to:
            self._conn.execute("UPDATE analytics_ids SET user_id = ? WHERE user_id = ?", (to_user_id, from_user_id))
            self._conn.commit()

    def record_analytics_events(self, user_id: str, events: Iterable[dict[str, Any]], *, source: str) -> int:
        """Append events for ``user_id`` (stored under its analytics id). Returns rows written.

        Each event: ``{"type", "screen"?, "props"?, "ts"?}``. Raises ValueError on an unknown
        type and PiiError on any PII. No-op (0) when analytics is switched off.
        """
        if not analytics_enabled():
            return 0
        allowed = CLIENT_EVENT_TYPES if source == "client" else SERVER_EVENT_TYPES
        rows = []
        for ev in events:
            etype = ev.get("type")
            if etype not in allowed:
                raise ValueError(f"unknown analytics event: {etype}")
            props = ev.get("props") or {}
            assert_no_pii({"screen": ev.get("screen"), "props": props})
            rows.append((etype, ev.get("screen"), json.dumps(props, sort_keys=True), ev.get("ts")))
        if not rows:
            return 0
        aid = self.analytics_id_for(user_id)
        now = _iso_now()
        for t, s, p, ts in rows:
            self._conn.execute(
                "INSERT INTO analytics_events (analytics_id, source, event_type, screen, props_json, client_ts, "
                "created_at) VALUES (?,?,?,?,?,?,?)",
                (aid, source, t, s, p, ts, now),
            )
        self._conn.commit()
        return len(rows)

    def emit_server_event(self, user_id: str | None, event_type: str, **props: Any) -> None:
        """Best-effort server-side event; never raises into a request."""
        if not user_id or not analytics_enabled():
            return
        try:
            clean = {k: v for k, v in props.items() if v is not None}
            self.record_analytics_events(user_id, [{"type": event_type, "props": clean}], source="server")
        except Exception:  # pragma: no cover - analytics must not break learning
            pass

    def list_analytics_events(self, analytics_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM analytics_events"
        args: list[Any] = []
        if analytics_id:
            sql += " WHERE analytics_id = ?"
            args.append(analytics_id)
        sql += " ORDER BY event_id"
        out = []
        for r in self._conn.execute(sql, args).fetchall():
            out.append(
                {
                    "eventId": r["event_id"],
                    "analyticsId": r["analytics_id"],
                    "source": r["source"],
                    "type": r["event_type"],
                    "screen": r["screen"],
                    "props": json.loads(r["props_json"] or "{}"),
                    "ts": r["client_ts"],
                    "createdAt": r["created_at"],
                }
            )
        return out
