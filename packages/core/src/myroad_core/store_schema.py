"""Schema and connection helpers for PathStore."""
from __future__ import annotations

import hashlib
import json
import sqlite3
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


class SqliteConnMixin:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
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
