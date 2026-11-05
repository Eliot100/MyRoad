"""Engagement v1 (#192): session model, weekly active days, weekly goal, goal meter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from myroad_core import engagement
from myroad_core.engagement import engagement_for
from myroad_core.store import PathStore

U = "u_eng"
P = "path_english_bagrut5_03_time"
PLACE = "path_english_bagrut5_00_placement"


def _doc(n: int = 10, per_topic: int = 3, route: bool = True) -> dict:
    blocks = [{"blockId": f"b{i}", "title": f"Step {i}"} for i in range(n)]
    topics = []
    for t in range(0, n, per_topic):
        topics.append({"id": f"t{t}", "node_ids": [f"n{i}" for i in range(t, min(n, t + per_topic))]})
    doc = {
        "pathId": P, "titles": {"he": "זמן וסיפור", "en": "Time and story"}, "blocks": blocks,
        "topics": topics, "nodeToBlock": {f"n{i}": f"b{i}" for i in range(n)},
    }
    if route:
        doc["placementRoute"] = {"from_placement": PLACE, "band_min": 3, "band_max": 3}
    return doc


@pytest.fixture
def store(tmp_path: Path):
    s = PathStore(str(tmp_path / "e.db"))
    s.upsert_learner(U, "Eli")
    yield s
    s.close()


class Clock:
    def __init__(self, monkeypatch, iso: str):
        self.set(iso)
        monkeypatch.setattr(engagement, "_now", lambda: self.now)

    def set(self, iso: str) -> None:
        self.now = datetime.fromisoformat(iso).astimezone(timezone.utc)


def _event(store, block: str, kind: str = "answer", ok: bool | None = True, at: str = "2026-11-02T08:00:00+02:00",
           path: str = P) -> None:
    ts = datetime.fromisoformat(at).astimezone(timezone.utc).isoformat()
    store._conn.execute(
        "INSERT INTO learner_events (user_id, path_id, block_id, event_type, ok, duration_ms, created_at) "
        "VALUES (?,?,?,?,?,?,?)", (U, path, block, kind, None if ok is None else int(ok), None, ts))
    store._conn.commit()


def _progress(store, mastered, index=0):
    store.save_progress(U, P, version_id=None, node_index=index, mastered=set(mastered), correct_taps=0, incorrect_taps=0)


def test_empty_state(store, monkeypatch):
    Clock(monkeypatch, "2026-11-02T10:00:00+02:00")  # a Monday
    e = engagement_for(store, U, _doc(route=False), "he")
    assert set(e) == {"session", "week", "goal_meter", "gap_days", "warmup_suggested"}
    s = e["session"]
    assert s["no"] == 1 and s["size"] == 6 and s["done_count"] == 0 and s["right_first_time"] == 0
    assert [st["id"] for st in s["steps"]] == [f"b{i}" for i in range(6)]
    assert s["steps"][0] == {"id": "b0", "title": "Step 0", "done": False, "right_first_time": False}
    assert s["complete"] is False and s["can_do"] == []
    w = e["week"]
    assert w["start"] == "2026-11-01" and len(w["days"]) == 7 and w["active_count"] == 0
    assert w["goal"] == 3 and w["goal_set"] is False
    assert [d["today"] for d in w["days"]].index(True) == 1
    assert e["goal_meter"] == {"target_label": '5 יח"ל', "stage": 0, "stages_total": 4, "start_stage": None,
                               "from_placement": False}
    assert e["gap_days"] is None and e["warmup_suggested"] is False


def test_session_stable_across_reload_same_day(store, monkeypatch):
    clock = Clock(monkeypatch, "2026-11-02T08:00:00+02:00")
    first = engagement_for(store, U, _doc())["session"]
    _event(store, "b0", ok=False)
    _event(store, "b0", ok=True)
    _event(store, "b1", ok=True)
    _progress(store, {"b0", "b1"}, index=2)
    clock.set("2026-11-02T23:30:00+02:00")  # still the same local day (21:30 UTC)
    again = engagement_for(store, U, _doc())["session"]
    assert again["no"] == first["no"] == 1
    assert [s["id"] for s in again["steps"]] == [s["id"] for s in first["steps"]]
    assert again["done_count"] == 2 and again["right_first_time"] == 1
    assert again["steps"][0]["right_first_time"] is False and again["steps"][1]["right_first_time"] is True
    assert again["can_do"] == ["Step 1", "Step 0"]


def test_new_day_gives_new_session_from_position(store, monkeypatch):
    clock = Clock(monkeypatch, "2026-11-02T08:00:00+02:00")
    engagement_for(store, U, _doc())
    for b in ("b0", "b1", "b2"):
        _event(store, b)
    _progress(store, {"b0", "b1", "b2"}, index=3)
    clock.set("2026-11-03T00:10:00+02:00")  # 22:10 UTC on the 2nd, but the 3rd locally
    s = engagement_for(store, U, _doc())["session"]
    assert s["no"] == 2 and [st["id"] for st in s["steps"]] == ["b3", "b4", "b5", "b6", "b7", "b8"]


def test_next_session_and_complete(store, monkeypatch):
    Clock(monkeypatch, "2026-11-02T08:00:00+02:00")
    s = engagement_for(store, U, _doc(n=8))["session"]
    ids = [st["id"] for st in s["steps"]]
    for b in ids:
        _event(store, b, at="2026-11-02T08:05:00+02:00")
    _progress(store, set(ids), index=6)
    done = engagement_for(store, U, _doc(n=8))["session"]
    assert done["complete"] is True and done["done_count"] == 6 and len(done["can_do"]) == 2
    nxt = engagement_for(store, U, _doc(n=8), new_session=True)["session"]
    assert nxt["no"] == 2 and [st["id"] for st in nxt["steps"]] == ["b6", "b7"] and not nxt["complete"]
    assert engagement_for(store, U, _doc(n=8))["session"]["no"] == 2  # reload keeps the new one


def test_missed_days_never_reset(store, monkeypatch):
    clock = Clock(monkeypatch, "2026-11-02T08:00:00+02:00")
    _event(store, "b0", at="2026-11-02T08:00:00+02:00")
    _progress(store, {"b0"}, index=1)
    store.set_weekly_goal(U, 5)
    clock.set("2026-11-06T09:00:00+02:00")  # 4 days later, same week (he: Sun 1st .. Sat 7th)
    e = engagement_for(store, U, _doc())
    assert e["week"]["active_count"] == 1 and e["week"]["days"][1]["active"] is True
    assert e["week"]["goal"] == 5 and e["week"]["goal_set"] is True
    assert e["gap_days"] == 4 and e["warmup_suggested"] is True
    assert e["session"]["steps"][0]["id"] == "b1"  # position kept
    assert store.get_progress(U, P)["mastered"] == {"b0"} or set(store.get_progress(U, P)["mastered"]) == {"b0"}


def test_gap_two_days_no_warmup(store, monkeypatch):
    Clock(monkeypatch, "2026-11-04T09:00:00+02:00")
    _event(store, "b0", at="2026-11-02T08:00:00+02:00")
    e = engagement_for(store, U, _doc())
    assert e["gap_days"] == 2 and e["warmup_suggested"] is False


def test_week_rollover(store, monkeypatch):
    clock = Clock(monkeypatch, "2026-11-07T20:00:00+02:00")  # Saturday
    _event(store, "b0", at="2026-11-07T19:00:00+02:00")
    w = engagement_for(store, U, _doc(), "he")["week"]
    assert w["start"] == "2026-11-01" and w["active_count"] == 1 and w["days"][6]["today"]
    clock.set("2026-11-08T07:00:00+02:00")  # Sunday: new he week
    w = engagement_for(store, U, _doc(), "he")["week"]
    assert w["start"] == "2026-11-08" and w["active_count"] == 0 and w["days"][0]["today"]
    assert w["goal"] == 3
    # en week (Mon-Sun) still holds Saturday
    w_en = engagement_for(store, U, _doc(), "en")["week"]
    assert w_en["start"] == "2026-11-02" and w_en["active_count"] == 1


def test_locale_week_order(store, monkeypatch):
    Clock(monkeypatch, "2026-11-04T12:00:00+02:00")  # Wednesday
    he = engagement_for(store, U, _doc(), "he")["week"]
    ar = engagement_for(store, U, _doc(), "ar")["week"]
    en = engagement_for(store, U, _doc(), "en")["week"]
    assert [d["wd"] for d in he["days"]] == [0, 1, 2, 3, 4, 5, 6] == [d["wd"] for d in ar["days"]]
    assert [d["wd"] for d in en["days"]] == [1, 2, 3, 4, 5, 6, 0]
    assert he["start"] == "2026-11-01" and en["start"] == "2026-11-02"


def test_local_timezone_day_boundary(store, monkeypatch):
    Clock(monkeypatch, "2026-11-04T12:00:00+02:00")
    _event(store, "b0", at="2026-11-02T23:30:00+02:00")  # 21:30 UTC, local Monday
    days = engagement_for(store, U, _doc(), "he")["week"]["days"]
    assert [d["date"] for d in days if d["active"]] == ["2026-11-02"]


def test_goal_meter_stages_and_placement(store, monkeypatch):
    Clock(monkeypatch, "2026-11-02T08:00:00+02:00")
    _progress(store, {"b0", "b1", "b2", "b3"}, index=4)
    store.save_progress(U, PLACE, version_id=None, node_index=0, mastered=set(), correct_taps=5,
                        incorrect_taps=2, completed_at="2026-11-01T08:00:00+00:00")  # band 3
    gm = engagement_for(store, U, _doc())["goal_meter"]
    assert gm == {"target_label": '5 יח"ל', "stage": 1, "stages_total": 4, "start_stage": 1, "from_placement": True}
    store.save_progress(U, PLACE, version_id=None, node_index=0, mastered=set(), correct_taps=5,
                        incorrect_taps=0, completed_at="2026-11-01T08:00:00+00:00")  # band 5: past this road
    assert engagement_for(store, U, _doc())["goal_meter"]["start_stage"] == 4


def test_target_label_falls_back_to_title(store, monkeypatch):
    Clock(monkeypatch, "2026-11-02T08:00:00+02:00")
    doc = {**_doc(route=False), "pathId": "path_grade3_math_add20"}
    assert engagement_for(store, U, doc, "en")["goal_meter"]["target_label"] == "Time and story"


def test_weekly_goal_store_validation(store):
    assert store.get_weekly_goal(U) == {"goal": 3, "goal_set": False}
    assert store.set_weekly_goal(U, 2) == {"goal": 2, "goal_set": True}
    with pytest.raises(ValueError):
        store.set_weekly_goal(U, 4)


def test_weekly_goal_migration_on_old_db(tmp_path: Path):
    import sqlite3
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE learners (user_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, locale TEXT NOT NULL "
                 "DEFAULT 'he', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
    conn.execute("INSERT INTO learners VALUES ('old','Old','he','x','x')")
    conn.commit()
    conn.close()
    s = PathStore(str(db))
    try:
        assert s.get_weekly_goal("old") == {"goal": 3, "goal_set": False}
        assert s.set_weekly_goal("old", 5)["goal"] == 5
    finally:
        s.close()


# --- HTTP ---------------------------------------------------------------------------------

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from auth_helpers import login_with_code  # noqa: E402
from test_english_bagrut_flow import _mini  # noqa: E402

from myroad_core.ui.app import create_learner_app  # noqa: E402

ZERO = "path_english_bagrut5_01_zero"
H = {"X-MyRoad-Request": "1"}


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_mini(PLACE, "מבדק רמה", []), _mini(ZERO, "מאפס", [PLACE])):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    s = PathStore(str(tmp_path / "p.db"))
    yield create_learner_app(store=s, seed=False, seed_content=True)
    s.close()


def _client(app) -> TestClient:
    c = TestClient(app)
    login_with_code(c, {"first_name": "Eli", "last_name": "R", "email": "e192@example.com", "next": "/"})
    return c


def _shape(e: dict) -> None:
    assert set(e) == {"session", "week", "goal_meter", "gap_days", "warmup_suggested"}
    assert set(e["session"]) == {"no", "steps", "size", "done_count", "right_first_time", "complete", "can_do", "can_do_ids"}
    for st in e["session"]["steps"]:
        assert set(st) == {"id", "title", "done", "right_first_time"}
        assert isinstance(st["id"], str) and isinstance(st["title"], str)
    assert set(e["week"]) == {"start", "days", "active_count", "goal", "goal_set"}
    for d in e["week"]["days"]:
        assert set(d) == {"date", "wd", "active", "today"}
    assert set(e["goal_meter"]) == {"target_label", "stage", "stages_total", "start_stage", "from_placement"}


def test_engagement_endpoint_shape_and_stability(app):
    c = _client(app)
    url = f"/api/path/{ZERO}/engagement"
    assert c.get(url).status_code == 403
    r = c.get(url, headers=H)
    assert r.status_code == 200
    e = r.json()
    _shape(e)
    assert e["session"]["no"] == 1 and e["session"]["size"] == 4
    assert e["goal_meter"]["stages_total"] == 2 and e["goal_meter"]["target_label"] == '5 יח"ל'
    assert c.get(url, headers=H).json() == e
    nxt = c.post(f"/api/path/{ZERO}/session/next", headers=H)
    assert nxt.status_code == 200
    _shape(nxt.json())
    assert nxt.json()["session"]["no"] == 2
    assert c.post(f"/api/path/{ZERO}/session/next").status_code == 403
    assert c.get("/api/path/nope/engagement", headers=H).status_code == 404


def test_engagement_requires_learner(app):
    c = TestClient(app)
    assert c.get(f"/api/path/{ZERO}/engagement", headers=H).status_code == 401
    assert c.get("/api/settings/weekly-goal", headers=H).status_code == 401
    assert c.post("/api/settings/weekly-goal", json={"goal": 3}, headers=H).status_code == 401


def test_weekly_goal_endpoint(app):
    c = _client(app)
    url = "/api/settings/weekly-goal"
    assert c.get(url, headers=H).json() == {"goal": 3, "goal_set": False}
    assert c.post(url, json={"goal": 5}).status_code == 403
    for bad in (1, 4, 6, "3x", None):
        assert c.post(url, json={"goal": bad}, headers=H).status_code == 422
    assert c.post(url, json={}, headers=H).status_code == 422
    assert c.post(url, json={"goal": 2}, headers=H).json() == {"goal": 2, "goal_set": True}
    assert c.get(url, headers=H).json() == {"goal": 2, "goal_set": True}
    assert c.get(f"/api/path/{ZERO}/engagement", headers=H).json()["week"]["goal"] == 2


def test_engagement_in_map_and_play_context(app):
    c = _client(app)
    seen = []
    from starlette.templating import Jinja2Templates
    orig = Jinja2Templates.TemplateResponse

    def spy(self, request, name, context=None, *a, **kw):
        seen.append((name, (context or {}).get("engagement")))
        return orig(self, request, name, context, *a, **kw)

    import unittest.mock as m
    with m.patch.object(Jinja2Templates, "TemplateResponse", spy):
        assert c.get(f"/play/{ZERO}?view=map").status_code == 200
        assert c.get(f"/play/{ZERO}?view=learn").status_code == 200
    by = dict(seen)
    for name in ("road_map.html", "play.html"):  # bagrut5 map is design D
        assert by.get(name) is not None, seen
        _shape(by[name])
