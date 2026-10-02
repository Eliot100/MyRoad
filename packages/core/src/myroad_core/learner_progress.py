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
  first_name TEXT,
  last_name TEXT,
  email TEXT,
  locale TEXT NOT NULL DEFAULT 'he',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_learners_email
  ON learners(email) WHERE email IS NOT NULL AND email != '';
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
  needs_practice INTEGER NOT NULL DEFAULT 0,
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

_PROGRESS_EXTRA_COLUMNS = (
    ("needs_practice", "INTEGER NOT NULL DEFAULT 0"),
)

_LEARNER_EXTRA_COLUMNS = (
    ("first_name", "TEXT"),
    ("last_name", "TEXT"),
    ("email", "TEXT"),
)


class LearnerProgressMixin:
    """Mixin expecting self._conn (sqlite3 connection)."""

    def ensure_learner_schema(self) -> None:
        self._conn.executescript(_LEARNER_SCHEMA)
        # Lightweight migrations for columns added after first deploy
        existing = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(learner_progress)").fetchall()
        }
        for col, decl in _PROGRESS_EXTRA_COLUMNS:
            if col not in existing:
                self._conn.execute(f"ALTER TABLE learner_progress ADD COLUMN {col} {decl}")
        learner_cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(learners)").fetchall()
        }
        for col, decl in _LEARNER_EXTRA_COLUMNS:
            if col not in learner_cols:
                self._conn.execute(f"ALTER TABLE learners ADD COLUMN {col} {decl}")
        self._conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_learners_email "
            "ON learners(email) WHERE email IS NOT NULL AND email != ''"
        )
        self._conn.commit()

    @staticmethod
    def _normalize_email(email: str | None) -> str | None:
        if email is None:
            return None
        cleaned = str(email).strip().lower()
        return cleaned or None

    @staticmethod
    def _display_from_names(first_name: str | None, last_name: str | None, fallback: str = "Learner") -> str:
        parts = [((first_name or "").strip()), ((last_name or "").strip())]
        name = " ".join(p for p in parts if p).strip()
        return name or fallback

    def _row_to_learner(self, row) -> dict[str, Any]:
        first = row["first_name"] if "first_name" in row.keys() else None
        last = row["last_name"] if "last_name" in row.keys() else None
        email = row["email"] if "email" in row.keys() else None
        return {
            "userId": row["user_id"],
            "displayName": row["display_name"],
            "firstName": first or "",
            "lastName": last or "",
            "email": email or "",
            "locale": row["locale"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def upsert_learner(
        self,
        user_id: str,
        display_name: str,
        *,
        locale: str = "he",
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        now = _iso_now()
        row = self._conn.execute(
            "SELECT user_id FROM learners WHERE user_id = ?", (user_id,)
        ).fetchone()
        email_n = self._normalize_email(email)
        first = (first_name or "").strip() or None
        last = (last_name or "").strip() or None
        if first or last:
            name = self._display_from_names(first, last, fallback=(display_name or "").strip() or "Learner")
        else:
            name = (display_name or "").strip() or "Learner"
        if row:
            self._conn.execute(
                "UPDATE learners SET display_name = ?, first_name = COALESCE(?, first_name), "
                "last_name = COALESCE(?, last_name), email = COALESCE(?, email), "
                "locale = ?, updated_at = ? WHERE user_id = ?",
                (name, first, last, email_n, locale, now, user_id),
            )
        else:
            self._conn.execute(
                "INSERT INTO learners (user_id, display_name, first_name, last_name, email, locale, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (user_id, name, first, last, email_n, locale, now, now),
            )
        self._conn.commit()
        return self.get_learner(user_id)  # type: ignore[return-value]

    def get_learner(self, user_id: str | None) -> dict[str, Any] | None:
        if not user_id:
            return None
        row = self._conn.execute(
            "SELECT user_id, display_name, first_name, last_name, email, locale, created_at, updated_at "
            "FROM learners WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_learner(row)

    def get_learner_by_email(self, email: str | None) -> dict[str, Any] | None:
        email_n = self._normalize_email(email)
        if not email_n:
            return None
        row = self._conn.execute(
            "SELECT user_id, display_name, first_name, last_name, email, locale, created_at, updated_at "
            "FROM learners WHERE lower(email) = ?",
            (email_n,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_learner(row)

    def register_or_login(
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
        locale: str = "he",
    ) -> dict[str, Any]:
        """Identify by unique email: create user or return existing (refresh names).

        Raises ValueError on missing email / names. Email uniqueness is enforced by DB.
        """
        email_n = self._normalize_email(email)
        first = (first_name or "").strip()
        last = (last_name or "").strip()
        if not email_n:
            raise ValueError("email_required")
        if "@" not in email_n or "." not in email_n.split("@")[-1]:
            raise ValueError("email_invalid")
        if not first or not last:
            raise ValueError("name_required")
        existing = self.get_learner_by_email(email_n)
        if existing:
            return self.upsert_learner(
                existing["userId"],
                self._display_from_names(first, last),
                locale=locale,
                first_name=first,
                last_name=last,
                email=email_n,
            )
        new_id = f"usr_{uuid.uuid4().hex[:12]}"
        try:
            return self.upsert_learner(
                new_id,
                self._display_from_names(first, last),
                locale=locale,
                first_name=first,
                last_name=last,
                email=email_n,
            )
        except Exception as exc:
            # Unique race: another insert won
            again = self.get_learner_by_email(email_n)
            if again:
                return again
            raise ValueError("email_taken") from exc

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
        needs = 0
        try:
            needs = int(row["needs_practice"] or 0)
        except (KeyError, IndexError, TypeError):
            needs = 0
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
            "needsPractice": bool(needs),
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
        needs_practice: bool | None = None,
    ) -> dict[str, Any]:
        now = _iso_now()
        existing = self.get_progress(user_id, path_id)
        started = started_at or (existing or {}).get("startedAt") or now
        mastered_list = sorted(mastered) if isinstance(mastered, set) else list(mastered)
        if needs_practice is None:
            # Auto: incomplete mastery after start, or more wrong than right taps
            if completed_at:
                needs = incorrect_taps > max(0, correct_taps) or (
                    len(mastered_list) > 0 and incorrect_taps >= 2 and incorrect_taps >= correct_taps
                )
            else:
                needs = incorrect_taps >= 2 and incorrect_taps > correct_taps
            # preserve explicit prior flag if still in progress without new signal
            if existing and existing.get("needsPractice") and not completed_at:
                needs = True
        else:
            needs = bool(needs_practice)
        self._conn.execute(
            """
            INSERT INTO learner_progress (
              user_id, path_id, version_id, node_index, mastered_json,
              correct_taps, incorrect_taps, started_at, updated_at, completed_at, needs_practice
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id, path_id) DO UPDATE SET
              version_id = excluded.version_id,
              node_index = excluded.node_index,
              mastered_json = excluded.mastered_json,
              correct_taps = excluded.correct_taps,
              incorrect_taps = excluded.incorrect_taps,
              started_at = COALESCE(learner_progress.started_at, excluded.started_at),
              updated_at = excluded.updated_at,
              completed_at = excluded.completed_at,
              needs_practice = excluded.needs_practice
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
                1 if needs else 0,
            ),
        )
        self._conn.commit()
        return self.get_progress(user_id, path_id)  # type: ignore[return-value]

    def list_user_progress(self, user_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT path_id, node_index, mastered_json, started_at, completed_at, updated_at, "
            "correct_taps, incorrect_taps, needs_practice "
            "FROM learner_progress WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            mastered = json.loads(row["mastered_json"] or "[]")
            try:
                needs = bool(row["needs_practice"])
            except (KeyError, IndexError):
                needs = False
            completed = bool(row["completed_at"])
            started = bool(row["started_at"])
            if completed:
                status = "completed"
            elif started or len(mastered) > 0 or int(row["node_index"] or 0) > 0:
                status = "in_progress"
            else:
                status = "started"
            # Needs practice: explicit flag, or completed with weak accuracy, or in-progress with mistakes
            if not needs:
                c = int(row["correct_taps"] or 0)
                w = int(row["incorrect_taps"] or 0)
                if completed and w >= 2 and w >= c:
                    needs = True
                elif status == "in_progress" and w >= 2 and w > c:
                    needs = True
            out.append(
                {
                    "pathId": row["path_id"],
                    "nodeIndex": row["node_index"],
                    "masteredCount": len(mastered),
                    "startedAt": row["started_at"],
                    "completedAt": row["completed_at"],
                    "updatedAt": row["updated_at"],
                    "correctTaps": row["correct_taps"],
                    "incorrectTaps": row["incorrect_taps"],
                    "needsPractice": needs,
                    "progressStatus": status,
                }
            )
        return out

    def mark_needs_practice(self, user_id: str, path_id: str, flag: bool = True) -> dict[str, Any] | None:
        prog = self.get_progress(user_id, path_id)
        if not prog:
            return None
        return self.save_progress(
            user_id,
            path_id,
            version_id=prog.get("versionId"),
            node_index=int(prog.get("nodeIndex") or 0),
            mastered=prog.get("mastered") or set(),
            correct_taps=int(prog.get("correctTaps") or 0),
            incorrect_taps=int(prog.get("incorrectTaps") or 0),
            started_at=prog.get("startedAt"),
            completed_at=prog.get("completedAt"),
            needs_practice=flag,
        )

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
