"""Per-user learner identity, progress, and attempt metrics (SQLite)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from myroad_core.store_schema import _iso_now

_LEARNER_SCHEMA = """
CREATE TABLE IF NOT EXISTS learners (
  user_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  locale TEXT NOT NULL DEFAULT 'he',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learner_progress (
  user_id TEXT NOT NULL,
  path_id TEXT NOT NULL,
  version_id TEXT,
  node_index INTEGER NOT NULL DEFAULT 0,
  mastered_json TEXT NOT NULL DEFAULT '[]',
  correct_taps INTEGER NOT NULL DEFAULT 0,
  incorrect_taps INTEGER NOT NULL DEFAULT 0,
  started_at TEXT,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  PRIMARY KEY (user_id, path_id)
);
CREATE TABLE IF NOT EXISTS learner_attempts (
  attempt_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  path_id TEXT NOT NULL,
  version_id TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL,
  duration_sec INTEGER NOT NULL DEFAULT 0,
  nodes_completed INTEGER NOT NULL DEFAULT 0,
  nodes_total INTEGER NOT NULL DEFAULT 0,
  correct_taps INTEGER NOT NULL DEFAULT 0,
  incorrect_taps INTEGER NOT NULL DEFAULT 0,
  mastery_pct REAL NOT NULL DEFAULT 0,
  message TEXT
);
CREATE INDEX IF NOT EXISTS idx_progress_user ON learner_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON learner_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_path ON learner_attempts(path_id);
"""


class LearnerProgressMixin:
    """Mixin expecting self._conn (sqlite3 connection)."""

    def ensure_learner_schema(self) -> None:
        self._conn.executescript(_LEARNER_SCHEMA)
        self._conn.commit()

    def upsert_learner(
        self,
        user_id: str,
        display_name: str,
        *,
        locale: str = "he",
    ) -> dict[str, Any]:
        now = _iso_now()
        row = self._conn.execute(
            "SELECT user_id FROM learners WHERE user_id = ?", (user_id,)
        ).fetchone()
        name = (display_name or "").strip() or "Learner"
        if row:
            self._conn.execute(
                "UPDATE learners SET display_name = ?, locale = ?, updated_at = ? WHERE user_id = ?",
                (name, locale, now, user_id),
            )
        else:
            self._conn.execute(
                "INSERT INTO learners (user_id, display_name, locale, created_at, updated_at) VALUES (?,?,?,?,?)",
                (user_id, name, locale, now, now),
            )
        self._conn.commit()
        return self.get_learner(user_id)  # type: ignore[return-value]

    def get_learner(self, user_id: str | None) -> dict[str, Any] | None:
        if not user_id:
            return None
        row = self._conn.execute(
            "SELECT user_id, display_name, locale, created_at, updated_at FROM learners WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "userId": row["user_id"],
            "displayName": row["display_name"],
            "locale": row["locale"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def ensure_learner(self, user_id: str | None, display_name: str | None = None) -> dict[str, Any]:
        if user_id:
            existing = self.get_learner(user_id)
            if existing:
                return existing
        new_id = user_id or f"usr_{uuid.uuid4().hex[:12]}"
        return self.upsert_learner(new_id, display_name or "Learner")

    def get_progress(self, user_id: str, path_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM learner_progress WHERE user_id = ? AND path_id = ?",
            (user_id, path_id),
        ).fetchone()
        if not row:
            return None
        mastered = json.loads(row["mastered_json"] or "[]")
        return {
            "userId": row["user_id"],
            "pathId": row["path_id"],
            "versionId": row["version_id"],
            "nodeIndex": row["node_index"],
            "mastered": set(mastered),
            "correctTaps": row["correct_taps"],
            "incorrectTaps": row["incorrect_taps"],
            "startedAt": row["started_at"],
            "updatedAt": row["updated_at"],
            "completedAt": row["completed_at"],
        }

    def save_progress(
        self,
        user_id: str,
        path_id: str,
        *,
        version_id: str | None,
        node_index: int,
        mastered: set[str] | list[str],
        correct_taps: int,
        incorrect_taps: int,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> dict[str, Any]:
        now = _iso_now()
        existing = self.get_progress(user_id, path_id)
        started = started_at or (existing or {}).get("startedAt") or now
        mastered_list = sorted(mastered) if isinstance(mastered, set) else list(mastered)
        self._conn.execute(
            """
            INSERT INTO learner_progress (
              user_id, path_id, version_id, node_index, mastered_json,
              correct_taps, incorrect_taps, started_at, updated_at, completed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id, path_id) DO UPDATE SET
              version_id = excluded.version_id,
              node_index = excluded.node_index,
              mastered_json = excluded.mastered_json,
              correct_taps = excluded.correct_taps,
              incorrect_taps = excluded.incorrect_taps,
              started_at = COALESCE(learner_progress.started_at, excluded.started_at),
              updated_at = excluded.updated_at,
              completed_at = excluded.completed_at
            """,
            (
                user_id,
                path_id,
                version_id,
                node_index,
                json.dumps(mastered_list, ensure_ascii=False),
                correct_taps,
                incorrect_taps,
                started,
                now,
                completed_at,
            ),
        )
        self._conn.commit()
        return self.get_progress(user_id, path_id)  # type: ignore[return-value]

    def list_user_progress(self, user_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT path_id, node_index, mastered_json, completed_at, updated_at, correct_taps, incorrect_taps "
            "FROM learner_progress WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            mastered = json.loads(row["mastered_json"] or "[]")
            out.append(
                {
                    "pathId": row["path_id"],
                    "nodeIndex": row["node_index"],
                    "masteredCount": len(mastered),
                    "completedAt": row["completed_at"],
                    "updatedAt": row["updated_at"],
                    "correctTaps": row["correct_taps"],
                    "incorrectTaps": row["incorrect_taps"],
                }
            )
        return out

    def record_attempt(
        self,
        *,
        user_id: str,
        path_id: str,
        version_id: str | None,
        started_at: str,
        finished_at: str | None = None,
        duration_sec: int,
        nodes_completed: int,
        nodes_total: int,
        correct_taps: int,
        incorrect_taps: int,
        mastery_pct: float,
        message: str | None = None,
    ) -> dict[str, Any]:
        attempt_id = f"att_{uuid.uuid4().hex[:12]}"
        finished = finished_at or _iso_now()
        self._conn.execute(
            """
            INSERT INTO learner_attempts (
              attempt_id, user_id, path_id, version_id, started_at, finished_at,
              duration_sec, nodes_completed, nodes_total, correct_taps, incorrect_taps,
              mastery_pct, message
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                attempt_id,
                user_id,
                path_id,
                version_id,
                started_at,
                finished,
                max(0, int(duration_sec)),
                nodes_completed,
                nodes_total,
                correct_taps,
                incorrect_taps,
                float(mastery_pct),
                message,
            ),
        )
        self._conn.commit()
        return {
            "attemptId": attempt_id,
            "userId": user_id,
            "pathId": path_id,
            "versionId": version_id,
            "startedAt": started_at,
            "finishedAt": finished,
            "durationSec": max(0, int(duration_sec)),
            "nodesCompleted": nodes_completed,
            "nodesTotal": nodes_total,
            "correctTaps": correct_taps,
            "incorrectTaps": incorrect_taps,
            "masteryPct": float(mastery_pct),
            "message": message,
        }

    def latest_attempt(self, user_id: str, path_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM learner_attempts WHERE user_id = ? AND path_id = ? "
            "ORDER BY finished_at DESC LIMIT 1",
            (user_id, path_id),
        ).fetchone()
        if not row:
            return None
        return {
            "attemptId": row["attempt_id"],
            "userId": row["user_id"],
            "pathId": row["path_id"],
            "versionId": row["version_id"],
            "startedAt": row["started_at"],
            "finishedAt": row["finished_at"],
            "durationSec": row["duration_sec"],
            "nodesCompleted": row["nodes_completed"],
            "nodesTotal": row["nodes_total"],
            "correctTaps": row["correct_taps"],
            "incorrectTaps": row["incorrect_taps"],
            "masteryPct": row["mastery_pct"],
            "message": row["message"],
        }
