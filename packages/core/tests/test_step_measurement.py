"""Issue #25: per-step measurement (learner_events): time, attempts, mastery."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from myroad_core import learner_progress as lp
from myroad_core.store import PathStore

OLD_SCHEMA = """
CREATE TABLE learners (user_id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
  locale TEXT NOT NULL DEFAULT 'he', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE learner_progress (user_id TEXT NOT NULL, path_id TEXT NOT NULL, version_id TEXT,
  node_index INTEGER NOT NULL DEFAULT 0, mastered_json TEXT NOT NULL DEFAULT '[]',
  correct_taps INTEGER NOT NULL DEFAULT 0, incorrect_taps INTEGER NOT NULL DEFAULT 0,
  started_at TEXT, updated_at TEXT NOT NULL, completed_at TEXT, PRIMARY KEY (user_id, path_id));
CREATE TABLE learner_attempts (attempt_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
  path_id TEXT NOT NULL, version_id TEXT, started_at TEXT NOT NULL, finished_at TEXT NOT NULL,
  duration_sec INTEGER NOT NULL DEFAULT 0, nodes_completed INTEGER NOT NULL DEFAULT 0,
  nodes_total INTEGER NOT NULL DEFAULT 0, correct_taps INTEGER NOT NULL DEFAULT 0,
  incorrect_taps INTEGER NOT NULL DEFAULT 0, mastery_pct REAL NOT NULL DEFAULT 0, message TEXT);
INSERT INTO learners VALUES ('u_old','Old','he','2025-01-01T00:00:00+00:00','2025-01-01T00:00:00+00:00');
INSERT INTO learner_attempts VALUES ('att_1','u_old','p','v','2025-01-01T00:00:00+00:00',
  '2025-01-01T00:05:00+00:00',300,3,3,3,0,100.0,'ok');
"""


def _old_db(tmp_path: Path) -> str:
    db = str(tmp_path / "old.db")
    conn = sqlite3.connect(db)
    conn.executescript(OLD_SCHEMA)
    conn.commit()
    conn.close()
    return db


def _tables(store: PathStore) -> set[str]:
    return {r[0] for r in store._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_old_db_migrates_without_data_loss_and_idempotently(tmp_path: Path) -> None:
    db = _old_db(tmp_path)
    store = PathStore(db)
    assert "learner_events" in _tables(store)
    assert store.latest_attempt("u_old", "p")["durationSec"] == 300
    assert store.get_learner("u_old")["displayName"] == "Old"
    store.record_step_event("u_old", "p", "b1", "step_view")
    store.ensure_learner_schema()  # second run: no error, no loss
    store.close()
    again = PathStore(db)  # reopen runs the migration again
    assert again.latest_attempt("u_old", "p")["attemptId"] == "att_1"
    assert again.step_aggregates("u_old")[0]["views"] == 1
    again.close()


def test_aggregates_attempts_time_and_last_result(store: PathStore, monkeypatch) -> None:
    clock = iter(
        [
            "2026-01-01T10:00:00+00:00",  # view b1
            "2026-01-01T10:00:20+00:00",  # wrong answer (20s)
            "2026-01-01T10:00:30+00:00",  # right answer (10s)
            "2026-01-01T10:00:30+00:00",  # mastery (0s)
            "2026-01-01T10:01:00+00:00",  # view b2
            "2026-01-01T13:00:00+00:00",  # answer after 3h: clamped
        ]
    )
    monkeypatch.setattr(lp, "_iso_now", lambda: next(clock))
    store.record_step_event("u", "p", "b1", "step_view")
    store.record_step_event("u", "p", "b1", "answer", ok=False)
    store.record_step_event("u", "p", "b1", "answer", ok=True)
    store.record_step_event("u", "p", "b1", "mastery", ok=True)
    store.record_step_event("u", "p", "b2", "step_view")
    store.record_step_event("u", "p", "b2", "answer", ok=False)
    rows = {r["blockId"]: r for r in store.step_aggregates("u", "p")}
    assert rows["b1"]["attempts"] == 2 and rows["b1"]["totalMs"] == 30_000
    assert rows["b1"]["lastResult"] is True and rows["b1"]["mastered"] is True
    assert rows["b2"]["totalMs"] == lp.MAX_STEP_DURATION_MS
    assert rows["b2"]["lastResult"] is False and rows["b2"]["mastered"] is False
    assert store.step_aggregates("someone_else") == []


def test_unknown_event_type_rejected(store: PathStore) -> None:
    with pytest.raises(ValueError):
        store.record_step_event("u", "p", "b", "ab_test")


def test_player_records_view_answer_and_mastery(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("jinja2")
    import json

    from myroad_core.ui.app import create_learner_app
    from test_step_player import PID, _at_practice, _path

    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_path(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "steps.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    try:
        c = _at_practice(app)
        c.get(f"/play/{PID}?view=learn")
        c.post(f"/play/{PID}/answer", data={"choice": "a"})  # wrong
        c.post(f"/play/{PID}/answer", data={"choice": "b"})  # right
        uid = store.get_session_user(c.cookies.get("myroad_session"))
        rows = store.step_aggregates(uid, PID)
        practice = [r for r in rows if r["attempts"]]
        assert len(practice) == 1
        p = practice[0]
        assert p["attempts"] == 2 and p["views"] >= 1
        assert p["lastResult"] is True and p["mastered"] is True and p["totalMs"] >= 0
        assert any(r["mastered"] and r["attempts"] == 0 for r in rows)  # learn step via ack
        kinds = {r[0] for r in store._conn.execute("SELECT event_type FROM learner_events")}
        assert kinds == {"step_view", "answer", "mastery"}
    finally:
        store.close()
