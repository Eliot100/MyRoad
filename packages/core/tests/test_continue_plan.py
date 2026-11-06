"""Continue tile, 1/3/7 reviews, placement plan, demo seed, and the install manifest."""
from __future__ import annotations

import importlib.util
import json
import struct
from datetime import date, timedelta
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app
from myroad_core.ui.continue_plan import choose_tile, plan_from_wrong
from myroad_core.ui.db_path import DEFAULT_UI_DB
from myroad_core.ui.pwa import MANIFEST

PID = "path_test_continue"
PLACE = "path_math_continue_00_placement"
_CORE = Path(__file__).resolve().parents[1]


def _load_seed():
    path = _CORE / "scripts" / "seed_demo.py"
    spec = importlib.util.spec_from_file_location("seed_demo", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_choose_tile_prefers_due_then_lowest_mistake_then_next() -> None:
    order = ["a", "b", "c"]
    levels = {"a": 2, "b": 1, "c": 3}
    assert choose_tile(order, levels, set(), set(), ["gone", "c"]) == "c"
    assert choose_tile(order, levels, mastered=set(), wrong={"a", "b"}, due=[]) == "b"
    assert choose_tile(order, levels, mastered={"b"}, wrong={"a", "b"}, due=[]) == "a"
    assert choose_tile(order, levels, mastered={"a"}, wrong=set(), due=[]) == "b"
    assert choose_tile(order, levels, mastered=set(order), wrong=set(), due=[]) is None


def test_plan_from_wrong_bands() -> None:
    assert plan_from_wrong(4)["startingLevel"] == 1 and plan_from_wrong(9)["weeklyGoal"] == 2
    assert plan_from_wrong(1)["startingLevel"] == 2 and plan_from_wrong(3)["weeklyTiles"] == 20
    assert plan_from_wrong(0) == {
        "startingLevel": 3, "weeklyTiles": 30, "weeklyMinutes": 100, "weeklyGoal": 5,
    }


def test_reviews_advance_1_3_7_and_a_miss_resets(tmp_path: Path) -> None:
    store = PathStore(str(tmp_path / "r.db"))
    try:
        store.upsert_learner("u", "A")
        start = date(2026, 1, 1)
        store.note_review("u", "p", "b", ok=True, today=start)
        assert _review(store) == (0, start + timedelta(days=1))
        store.note_review("u", "p", "b", ok=True, today=start)  # before the due day
        assert _review(store) == (0, start + timedelta(days=1))
        day = start + timedelta(days=1)
        store.note_review("u", "p", "b", ok=True, today=day)
        assert _review(store) == (1, day + timedelta(days=3))
        day = day + timedelta(days=3)
        store.note_review("u", "p", "b", ok=True, today=day)
        assert _review(store) == (2, day + timedelta(days=7))
        day = day + timedelta(days=7)
        store.note_review("u", "p", "b", ok=True, today=day)
        assert _review(store) is None
        store.note_review("u", "p", "b", ok=False, today=start)
        assert _review(store) == (0, start + timedelta(days=1))
        assert store.due_reviews("u", "p", today=start + timedelta(days=1)) == ["b"]
        assert store.due_reviews("u", "p", today=start) == []
    finally:
        store.close()


def _review(store: PathStore):
    row = store._conn.execute("SELECT stage, due_on FROM learner_reviews").fetchone()
    if not row:
        return None
    return int(row[0]), date.fromisoformat(row[1])


def test_placement_plan_does_not_clobber_an_existing_goal(tmp_path: Path) -> None:
    from myroad_core.ui.continue_plan import apply_placement_plan

    store = PathStore(str(tmp_path / "p.db"))
    try:
        store.upsert_learner("u", "A")
        store.save_placement_detail("u", "place", {"band": 3, "summary": "kept"})
        store.set_road_plan("u", weekly_tiles=8, weekly_minutes=15, goal_date="2026-12-01")
        store.set_weekly_goal("u", 2)
        plan = apply_placement_plan(store, "u", "place", 6)
        assert plan["startingLevel"] == 1
        assert store.get_road_plan("u") == {"weeklyTiles": 8, "weeklyMinutes": 15, "goalDate": "2026-12-01"}
        assert store.get_weekly_goal("u") == {"goal": 2, "goal_set": True}
        detail = store.get_placement_detail("u", "place")
        assert detail["startingLevel"] == 1 and detail["summary"] == "kept" and detail["band"] == 3

        store2 = PathStore(str(tmp_path / "q.db"))
        store2.upsert_learner("u", "A")
        store2.set_road_plan("u", goal_date="2026-12-20")
        apply_placement_plan(store2, "u", "place", 0)
        assert store2.get_road_plan("u") == {"weeklyTiles": 30, "weeklyMinutes": 100, "goalDate": "2026-12-20"}
        assert store2.get_weekly_goal("u")["goal"] == 5
        store2.close()
    finally:
        store.close()


def _docs() -> dict[str, dict]:
    practice = {
        "id": "p1", "type": "practice", "title": "רמה 1",
        "body_he": "LEVEL1 question",
        "choices": [{"id": "a", "label": "כן"}, {"id": "b", "label": "לא"}],
        "correct": "a", "feedback_ok": "נכון.", "feedback_try": "עוד ניסיון.",
    }
    other = {
        "id": "p2", "type": "practice", "title": "רמה 2",
        "body_he": "LEVEL2 question",
        "choices": [{"id": "a", "label": "1"}, {"id": "b", "label": "2"}],
        "correct": "a", "feedback_ok": "נכון.", "feedback_try": "עוד ניסיון.",
    }
    road = {
        "id": PID, "subject": "math", "group_ids": ["adult"], "emoji": "א", "estimated_minutes": 10,
        "titles": {"he": "המשך", "en": "Continue", "ar": "متابعة"},
        "blurbs": {"he": "בדיקת המשך.", "en": "Continue check.", "ar": "فحص المتابعة."},
        "topics": [
            {"id": "t1", "level": 1, "titles": {"he": "נמוך", "en": "Low", "ar": "منخفض"}, "node_ids": ["p1"]},
            {"id": "t2", "level": 2, "titles": {"he": "גבוה", "en": "High", "ar": "عال"}, "node_ids": ["p2"]},
        ],
        "nodes": [practice, other],
    }
    place = {
        "id": PLACE, "subject": "math", "group_ids": ["adult"], "emoji": "א", "estimated_minutes": 5,
        "titles": {"he": "מבדק", "en": "Placement", "ar": "تحديد"},
        "blurbs": {"he": "מבדק קצר.", "en": "A short placement.", "ar": "تحديد قصير."},
        "topics": [{"id": "tp", "titles": {"he": "מבדק", "en": "Placement", "ar": "تحديد"}, "node_ids": ["q1"]}],
        "nodes": [{
            "id": "q1", "type": "practice", "title": "שאלה",
            "body_he": "PLACE question",
            "choices": [{"id": "a", "label": "נכון"}, {"id": "b", "label": "לא"}],
            "correct": "b", "feedback_ok": "נכון.", "feedback_try": "עוד ניסיון.",
        }],
    }
    return {PID: road, PLACE: place}


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for pid, doc in _docs().items():
        (content / f"{pid}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "c.db"))
    application = create_learner_app(store=store, seed=False, seed_content=True)
    yield application
    store.close()


def _uid(app, client: TestClient) -> str:
    return app.state.store.get_session_user(client.cookies.get("myroad_session"))


def test_continue_opens_a_due_review_ahead_of_a_new_tile(app) -> None:
    client = TestClient(app)
    login(client, "cont@example.com", first_name="Noa", last_name="Levi")
    uid = _uid(app, client)
    store = app.state.store
    store.note_review(uid, PID, "blk_001_practice", ok=True, today=date(2026, 1, 1))
    store._conn.execute(
        "UPDATE learner_reviews SET due_on = ? WHERE block_id = ?",
        ("2026-01-02", "blk_001_practice"),
    )
    store._conn.commit()
    page = client.get(f"/play/{PID}/continue", follow_redirects=True).text
    assert "LEVEL2 question" in page
    road = client.get(f"/road/{PID}").text
    assert f'href="/play/{PID}/continue"' in road
    anon = TestClient(app)
    assert f'href="/play/{PID}?view=learn"' in anon.get(f"/road/{PID}").text
    assert f'href="/play/{PID}/continue"' not in anon.get(f"/road/{PID}").text


def test_continue_opens_the_lowest_unmastered_mistake(app) -> None:
    client = TestClient(app)
    login(client, "miss@example.com", first_name="Noa", last_name="Levi")
    uid = _uid(app, client)
    store = app.state.store
    store.record_step_event(uid, PID, "blk_001_practice", "answer", ok=False)
    page = client.get(f"/play/{PID}/continue", follow_redirects=True).text
    assert "LEVEL2 question" in page


def test_a_fresh_correct_answer_is_due_tomorrow_so_continue_stays_on_the_next_tile(app) -> None:
    client = TestClient(app)
    login(client, "next@example.com", first_name="Noa", last_name="Levi")
    client.post(f"/play/{PID}/start")
    client.post(f"/play/{PID}/answer", data={"choice": "a"})
    uid = _uid(app, client)
    assert app.state.store.due_reviews(uid, PID) == []
    page = client.get(f"/play/{PID}/continue", follow_redirects=True).text
    assert "LEVEL2 question" in page


def test_finishing_a_placement_sets_level_and_weekly_goal(app) -> None:
    client = TestClient(app)
    login(client, "place@example.com", first_name="Noa", last_name="Levi")
    client.post(f"/play/{PLACE}/start")
    client.post(f"/play/{PLACE}/answer", data={"choice": "a"})  # wrong, the correct id is b
    client.post(f"/play/{PLACE}/answer", data={"choice": "b"})
    uid = _uid(app, client)
    store = app.state.store
    assert store.get_weekly_goal(uid) == {"goal": 3, "goal_set": True}
    assert store.get_road_plan(uid)["weeklyTiles"] == 20
    assert store.get_placement_detail(uid, PLACE)["startingLevel"] == 2


def test_manifest_and_icons_and_hidden_install_button(tmp_path: Path) -> None:
    store = PathStore(str(tmp_path / "m.db"))
    try:
        with TestClient(create_learner_app(store=store, seed=False, seed_content=False)) as client:
            body = client.get("/manifest.webmanifest")
            assert body.status_code == 200
            assert "manifest" in body.headers["content-type"]
            data = body.json()
            assert data["name"] == "MyRoad" and data["start_url"] == "/"
            assert data["display"] == "standalone" and data["dir"] == "rtl" and data["lang"] == "he"
            assert data["theme_color"] == MANIFEST["theme_color"] == "#171614"
            assert data["background_color"] == "#F3EFE6"
            for icon in data["icons"]:
                raw = client.get(icon["src"])
                assert raw.status_code == 200 and raw.content[:8] == b"\x89PNG\r\n\x1a\n"
                width, height = struct.unpack(">II", raw.content[16:24])
                assert f"{width}x{height}" == icon["sizes"]
            sw = client.get("/sw.js").text
            assert "/static/icons/icon-192.png" not in sw
            html = client.get("/login").text
            assert 'rel="manifest" href="/manifest.webmanifest"' in html
            assert 'id="pwa-install"' in html and "hidden" in html
            js = client.get("/static/sw-register.js").text
            assert "beforeinstallprompt" in js and 'getElementById("pwa-install")' in js
            assert 'navigator.serviceWorker.register("/sw.js", { scope: "/" })' in js
    finally:
        store.close()


def test_seed_demo_is_a_new_file_and_refuses_real_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed = _load_seed()
    with pytest.raises(SystemExit):
        seed.write_demo(DEFAULT_UI_DB)
    content = tmp_path / "MyRoad-content" / "adult"
    content.mkdir(parents=True)
    with pytest.raises(SystemExit):
        seed.write_demo(content / "demo.db")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "extra"))
    (tmp_path / "extra").mkdir()
    with pytest.raises(SystemExit):
        seed.write_demo(tmp_path / "extra" / "demo.db")
    out = tmp_path / "fresh" / "demo.db"
    assert seed.main(["--out", str(out)]) == 0
    assert out.is_file()
    store = PathStore(str(out))
    try:
        row = store._conn.execute("SELECT is_demo, display_name FROM learners WHERE user_id = 'demo'").fetchone()
        assert row[0] == 1 and row[1] == "הדגמה"
        assert store.get_road_plan("demo")["weeklyTiles"] == 12
    finally:
        store.close()
    with pytest.raises(SystemExit):
        seed.write_demo(out)
