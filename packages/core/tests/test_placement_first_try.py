"""Placement band by first-try answers (#199): retries on one item never add wrong items."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code
from test_english_bagrut_flow import _mini

from myroad_core.content.english_bagrut import placement_band
from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

PLACE = "path_english_bagrut5_00_placement"
ZERO = "path_english_bagrut5_01_zero"
EMAIL = "p199@example.com"
H = {"X-MyRoad-Request": "1"}
URL = "/api/placement/result"


def _placement(items: int) -> dict:
    doc = _mini(PLACE, "מבדק רמה", [])
    prac = next(n for n in doc["nodes"] if n["type"] == "practice")
    doc["nodes"] = [dict(prac, id=f"p{i}", title=f"שאלה {i}") for i in range(items)]
    doc["topics"] = [dict(doc["topics"][0], node_ids=[f"p{i}" for i in range(items)])]
    return doc


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_placement(3), _mini(ZERO, "מאפס", [PLACE])):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "p.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    c = TestClient(app)
    login_with_code(c, {"first_name": "Eli", "last_name": "R", "email": EMAIL, "next": "/"})
    yield c, store
    store.close()


def _play(c: TestClient, wrong_taps: list[int]) -> None:
    """Answer each item: ``wrong_taps[i]`` wrong picks, then the right one."""
    c.post(f"/play/{PLACE}/start", data={"reset": "1"})
    for n in wrong_taps:
        for _ in range(n):
            c.post(f"/play/{PLACE}/answer", data={"choice": "b"}, follow_redirects=False)
        c.post(f"/play/{PLACE}/answer", data={"choice": "a"}, follow_redirects=False)


def _progress(c, store):
    uid = store.get_learner_by_email(EMAIL)["userId"]
    return uid, store.get_progress(uid, PLACE)


def test_first_try_right_is_band_5(env):
    c, store = env
    _play(c, [0, 0, 0])
    _uid, prog = _progress(c, store)
    assert prog["completedAt"] and prog["incorrectTaps"] == 0 and placement_band(prog) == 5
    assert c.get(URL).json()["band"] == 5


def test_first_try_right_stays_right_when_re_answered_wrong(env):
    c, store = env
    _play(c, [0, 0, 0])
    uid, _ = _progress(c, store)
    blocks = [a["blockId"] for a in store.step_aggregates(uid, PLACE)]
    c.post(f"/play/{PLACE}/start", data={"node": blocks[0]})
    c.post(f"/play/{PLACE}/answer", data={"choice": "b"}, follow_redirects=False)
    _uid, prog = _progress(c, store)
    assert prog["incorrectTaps"] == 0 and placement_band(prog) == 5


def test_first_try_wrong_then_right_is_one_wrong(env):
    c, store = env
    _play(c, [1, 0, 0])
    _uid, prog = _progress(c, store)
    assert prog["incorrectTaps"] == 1 and placement_band(prog) == 4


def test_repeated_wrong_taps_on_one_item_count_once(env):
    c, store = env
    _play(c, [6, 0, 0])
    _uid, prog = _progress(c, store)
    assert prog["incorrectTaps"] == 1 and placement_band(prog) == 4
    assert not prog["needsPractice"]


def test_three_first_try_misses_stay_three_and_not_fifteen(env):
    c, store = env
    _play(c, [5, 5, 5])
    uid, prog = _progress(c, store)
    assert prog["incorrectTaps"] == 3
    body = c.get(URL).json()
    # Fifteen taps must not move the level. The stored level is the first try: 0 of 3.
    assert body["band"] == 1 and body["incorrect"] == 3
    assert store.get_placement_detail(uid, PLACE)["startingLevel"] == 1


def test_store_counts_first_answer_per_item(env):
    _c, store = env
    for block, oks in {"a": [False, False, True], "b": [True, False], "c": [False], "d": [True]}.items():
        for ok in oks:
            store.record_step_event("u1", "x_placement", block, "answer", ok=ok)
    assert store.first_try_wrong_count("u1", "x_placement") == 2
    assert store.first_try_wrong_count("u1", "x_placement", since="9999") == 0


def test_api_uses_first_answer_per_question(env):
    c, _store = env
    answers = []
    for q in ("q0", "q1", "q2"):
        answers += [{"questionId": q, "correct": False}] * 5 + [{"questionId": q, "correct": True}]
    answers += [{"questionId": "q3", "correct": True}, {"questionId": "q3", "correct": False}]
    body = c.post(URL, json={"answers": answers}, headers=H).json()
    assert body["band"] == 2 and body["incorrect"] == 3 and body["correct"] == 1
    assert c.get(URL).json() == body
    four = [{"questionId": f"w{i}", "correct": False} for i in range(4)]
    assert c.post(URL, json={"answers": four}, headers=H).json()["band"] == 1
