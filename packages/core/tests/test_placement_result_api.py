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
