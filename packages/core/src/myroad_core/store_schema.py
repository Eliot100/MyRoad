"""Schema and connection helpers for PathStore."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from myroad_core.errors import StoreError
from myroad_core.models import utc_now

__all__ = ["SqliteConnMixin", "_iso_now", "_digest", "_SCHEMA", "StoreError"]


def _iso_now() -> str:
    return utc_now().isoformat()


def _digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS paths (
  path_id TEXT PRIMARY KEY, name TEXT NOT NULL,
  created_at TEXT NOT NULL, author_id TEXT);
CREATE TABLE IF NOT EXISTS versions (
  version_id TEXT PRIMARY KEY,
  path_id TEXT NOT NULL REFERENCES paths(path_id),
  version_num INTEGER NOT NULL, status TEXT NOT NULL,
  document_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(path_id, version_num));
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
  actor_id TEXT NOT NULL, agent_id TEXT, correlation_id TEXT NOT NULL,
  path_id TEXT, version_id TEXT, payload_digest TEXT,
  timestamp TEXT NOT NULL, rbac_decision TEXT NOT NULL, detail_json TEXT);
CREATE INDEX IF NOT EXISTS idx_versions_path ON versions(path_id);
CREATE INDEX IF NOT EXISTS idx_events_path ON events(path_id);
CREATE INDEX IF NOT EXISTS idx_events_corr ON events(correlation_id);
"""


class _Result:
    """Materialized result of one statement (rows fetched while the lock is held)."""

    def __init__(self, cur: sqlite3.Cursor) -> None:
        self._rows = cur.fetchall() if cur.description else []
        self._pos = 0
        self.rowcount = cur.rowcount
        self.lastrowid = cur.lastrowid
        self.description = cur.description

    def fetchone(self) -> Any:
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return row

    def fetchall(self) -> list[Any]:
        rest = self._rows[self._pos:]
        self._pos = len(self._rows)
        return rest

    def __iter__(self):
        return iter(self.fetchall())


class LockedConnection:
    """Thread-safe wrapper around one shared sqlite3 connection.

    FastAPI runs sync endpoints in a thread pool and all of them share the
    store's connection. Every statement runs (and its rows are fetched) under
    one re-entrant lock, so threads never use the connection or a cursor at
    the same time. Multi-statement sequences that must be atomic hold
    ``lock`` themselves (it is re-entrant).
    """

    def __init__(self, raw: sqlite3.Connection) -> None:
        self._raw = raw
        self.lock = threading.RLock()

    @property
    def row_factory(self) -> Any:
        return self._raw.row_factory

    @row_factory.setter
    def row_factory(self, value: Any) -> None:
        self._raw.row_factory = value

    def execute(self, sql: str, params: Any = ()) -> _Result:
        with self.lock:
            return _Result(self._raw.execute(sql, params))

    def executescript(self, script: str) -> None:
        with self.lock:
            self._raw.executescript(script)

    def commit(self) -> None:
        with self.lock:
            self._raw.commit()

    def rollback(self) -> None:
        with self.lock:
            self._raw.rollback()

    def iterdump(self):
        with self.lock:
            return iter(list(self._raw.iterdump()))

    def close(self) -> None:
        with self.lock:
            self._raw.close()


class SqliteConnMixin:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._conn = LockedConnection(sqlite3.connect(self.db_path, check_same_thread=False))
        self._lock = self._conn.lock
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
