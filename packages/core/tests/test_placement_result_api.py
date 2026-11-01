"""Placement result API (issue #152): match, no match, repeat call, bad input, unknown learner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code
from test_english_bagrut_flow import _mini

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

PLACE = "path_english_bagrut5_00_placement"
ZERO = "path_english_bagrut5_01_zero"
H = {"X-MyRoad-Request": "1"}
URL = "/api/placement/result"


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_mini(PLACE, "מבדק רמה", []), _mini(ZERO, "מאפס", [PLACE])):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "p.db"))
    yield create_learner_app(store=store, seed=False, seed_content=True)
    store.close()


def _client(app) -> TestClient:
    c = TestClient(app)
    login_with_code(c, {"first_name": "Eli", "last_name": "R", "email": "p152@example.com", "next": "/"})
    return c


def _answers(wrong: int, right: int = 5) -> dict:
    return {"answers": [{"questionId": f"q{i}", "correct": i >= wrong} for i in range(wrong + right)]}


def test_match_returns_published_road_and_first_step(app):
    c = _client(app)
    r = c.post(URL, json=_answers(wrong=5), headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["band"] == 1 and body["gap"] == ZERO
    assert body["recommended_road_id"] == ZERO
    assert body["first_step_id"].startswith("blk_000")
    assert c.get(URL).json() == body


def test_no_match_is_200_with_null(app):
    c = _client(app)
    r = c.post(URL, json=_answers(wrong=0), headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["band"] == 5 and body["gap"] == "path_english_bagrut5_05_module_e"
    assert body["recommended_road_id"] is None and body["first_step_id"] is None


def test_repeat_call_is_deterministic_and_get_returns_last(app):
    c = _client(app)
    first = c.post(URL, json=_answers(wrong=1), headers=H).json()
    again = c.post(URL, json=_answers(wrong=1), headers=H).json()
    assert {k: v for k, v in first.items() if k != "completedAt"} == {
        k: v for k, v in again.items() if k != "completedAt"
    }
    assert first["band"] == 3
    last = c.post(URL, json=_answers(wrong=6), headers=H).json()
    assert c.get(URL).json() == last and last["band"] == 1


@pytest.mark.parametrize("payload", [{}, {"answers": []}, {"answers": [{"questionId": "q"}]}, {"answers": "x"}])
def test_invalid_input_is_422(app, payload):
    c = _client(app)
    assert c.post(URL, json=payload, headers=H).status_code == 422


def test_missing_csrf_header_is_403(app):
    c = _client(app)
    assert c.post(URL, json=_answers(wrong=0)).status_code == 403


def test_unknown_learner_is_401(app):
    c = TestClient(app)
    c.cookies.set("myroad_session", "not-a-session")
    r = c.post(URL, json=_answers(wrong=0), headers=H)
    assert r.status_code == 401 and r.json() == {"error": "unknown_learner"}
    assert c.get(URL).status_code == 401


def test_get_before_any_result_is_404(app):
    c = _client(app)
    assert c.get(URL).status_code == 404


def test_placement_routes_to_arabic_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Decision 0003: placementId + placement_route route the learner to the Arabic path."""
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    ar_place, ar_zero = "path_arabic_bagrut5_00_placement", "path_arabic_bagrut5_01_script"
    zero = _mini(ar_zero, "ערבית מאפס", [])
    zero["subject"] = "arabic"
    zero["placement_route"] = {"from_placement": ar_place, "band_min": 1, "band_max": 3}
    ar_doc = _mini(ar_place, "מבדק ערבית", [])
    ar_doc["subject"] = "arabic"
    for doc in (ar_doc, zero):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "p.db"))
    try:
        c = _client(create_learner_app(store=store, seed=False, seed_content=True))
        body = c.post(URL, json={**_answers(wrong=5), "placementId": ar_place}, headers=H).json()
        assert body["band"] == 1 and body["recommended_road_id"] == ar_zero and body["placement_id"] == ar_place
        assert c.get(URL, params={"placementId": ar_place}).json() == body
        high = c.post(URL, json={**_answers(wrong=0), "placementId": ar_place}, headers=H).json()
        assert high["band"] == 5 and high["recommended_road_id"] == ar_zero and high["routing_gap"] is True
        assert body["routing_gap"] is False
        s = c.post("/api/settings/steps", json={"audio": False}, headers=H).json()
        assert s == {"audio": False, "writing": False}
    finally:
        store.close()


def test_english_routing_reads_placement_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Content decides the road: moving road 03's placement_route to band 1 moves the result."""
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    time_road = _mini("path_english_bagrut5_03_time", "זמן וסיפור", [PLACE])
    time_road["placement_route"] = {"from_placement": PLACE, "band_min": 1, "band_max": 1}
    zero = _mini(ZERO, "מאפס", [PLACE])
    zero.pop("placement_route")
    for doc in (_mini(PLACE, "מבדק רמה", []), zero, time_road):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "p.db"))
    try:
        c = _client(create_learner_app(store=store, seed=False, seed_content=True))
        body = c.post(URL, json=_answers(wrong=5), headers=H).json()
        assert body["band"] == 1 and body["recommended_road_id"] == "path_english_bagrut5_03_time"
    finally:
        store.close()


def _write(tmp_path: Path, docs: list[dict]) -> None:
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in docs:
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _subject_doc(pid: str, subject: str, route: dict | None = None) -> dict:
    d = _mini(pid, pid, [])
    d["subject"] = subject
    if route:
        d["placement_route"] = route
    else:
        d.pop("placement_route", None)
    return d


def test_gap_fallback_stays_in_subject_and_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Arabic band 5, no route covers it: highest Arabic road with band_min <= 5, never English."""
    ar = "path_arabic_bagrut5_00_placement"
    r = lambda lo, hi: {"from_placement": ar, "band_min": lo, "band_max": hi}  # noqa: E731
    _write(tmp_path, [
        _subject_doc(ar, "arabic"),
        _subject_doc("path_arabic_bagrut5_01_script", "arabic", r(1, 3)),
        _subject_doc("path_arabic_bagrut5_02_words", "arabic", r(4, 4)),
        _subject_doc("path_arabic_bagrut5_03_late", "arabic", r(6, 8)),
        _mini(PLACE, "מבדק רמה", []), _mini(ZERO, "מאפס", [PLACE]),
    ])
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "p.db"))
    try:
        c = _client(create_learner_app(store=store, seed=False, seed_content=True))
        body = c.post(URL, json={**_answers(wrong=0), "placementId": ar}, headers=H).json()
        assert body["band"] == 5 and body["routing_gap"] is True
        assert body["recommended_road_id"] == "path_arabic_bagrut5_02_words"
        uid = store.get_learner_by_email("p152@example.com")["userId"]
        rows = store._conn.execute(
            "SELECT path_id, block_id FROM learner_events WHERE user_id = ? AND event_type = 'placement_gap'", (uid,)
        ).fetchall()
        assert [tuple(x) for x in rows] == [(ar, "band:5")]
        assert store.step_aggregates(uid) == []  # gap rows are not steps
        english = c.post(URL, json=_answers(wrong=0), headers=H).json()
        assert english["routing_gap"] is False and english["recommended_road_id"] is None  # unchanged
    finally:
        store.close()


def test_gap_with_no_roads_in_subject_goes_home_not_other_series(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from test_english_bagrut_flow import _finish_placement

    phys = "path_physics_bagrut_00_placement"
    _write(tmp_path, [_subject_doc(phys, "physics"), _mini(PLACE, "מבדק רמה", []), _mini(ZERO, "מאפס", [PLACE])])
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "p.db"))
    try:
        c = _client(create_learner_app(store=store, seed=False, seed_content=True))
        body = c.post(URL, json={**_answers(wrong=5), "placementId": phys}, headers=H).json()
        assert body["recommended_road_id"] is None and body["routing_gap"] is True
        assert _finish_placement(c, phys) == "/"
    finally:
        store.close()


def test_gap_with_no_roads_uses_own_subject_series_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from myroad_core.ui import placement_api

    monkeypatch.setitem(placement_api.SUBJECT_SERIES_PAGE, "physics", "/series/physics")
    phys = "path_physics_bagrut_00_placement"
    _write(tmp_path, [_subject_doc(phys, "physics")])
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "p.db"))
    try:
        create_learner_app(store=store, seed=False, seed_content=True)
        t = placement_api.placement_target(store, phys, 3)
        assert t == {"road": None, "routing_gap": True, "fallback_url": "/series/physics"}
    finally:
        store.close()
