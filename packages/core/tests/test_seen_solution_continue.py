"""#247: session.can_do_ids and the 'saw the full solution, continue' route."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

CSRF = {"X-MyRoad-Request": "1"}
from test_full_solution_session_end import HX, PID, _path, client  # noqa: F401  (fixture)


def _events(store, kind):
    return [e for e in store.list_analytics_events() if e["type"] == kind]


@pytest.fixture
def an(monkeypatch):
    monkeypatch.setenv("MYROAD_ANALYTICS", "1")


def test_can_do_ids_match_can_do(client) -> None:
    for _ in range(2):
        client.post(f"/play/{PID}/answer", data={"choice": "a"})
    s = client.get(f"/api/path/{PID}/engagement", headers=CSRF).json()["session"]
    can_do_by_title = {n["title"]: n["can_do"] for n in _path()["nodes"]}
    title_by_id = {st["id"]: st["title"] for st in s["steps"]}
    assert len(s["can_do_ids"]) == len(s["can_do"]) == 2
    assert [can_do_by_title[title_by_id[i]] for i in s["can_do_ids"]] == s["can_do"]


def test_without_wrong_answer_is_4xx_no_event_no_move(client, an) -> None:
    store = client.app.state.store
    before = client.get(f"/play/{PID}?view=learn").text
    r = client.post(f"/play/{PID}/seen_solution", follow_redirects=False)
    assert 400 <= r.status_code < 500
    assert _events(store, "solution_seen_continue") == []
    assert client.get(f"/play/{PID}?view=learn").text.count("1 + 1 = ?") == before.count("1 + 1 = ?") > 0


def test_after_wrong_logs_one_event_moves_on_not_mastered(client, an) -> None:
    store = client.app.state.store
    client.post(f"/play/{PID}/answer", data={"choice": "b"}, headers=HX)
    eng0 = client.get(f"/api/path/{PID}/engagement", headers=CSRF).json()["session"]
    card = client.post(f"/play/{PID}/seen_solution", headers=HX).text
    assert "2 + 1 = ?" in card
    assert len(_events(store, "solution_seen_continue")) == 1
    eng = client.get(f"/api/path/{PID}/engagement", headers=CSRF).json()["session"]
    assert eng["done_count"] == eng0["done_count"] == 0
    assert eng["right_first_time"] == 0
    # once only: a second call without a new wrong answer is refused
    assert client.post(f"/play/{PID}/seen_solution", headers=HX).status_code == 409
    assert len(_events(store, "solution_seen_continue")) == 1


def test_no_js_303_to_next_step(client) -> None:
    client.post(f"/play/{PID}/answer", data={"choice": "b"}, follow_redirects=False)
    r = client.post(f"/play/{PID}/seen_solution", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/play/{PID}?view=learn"
    assert "2 + 1 = ?" in client.get(r.headers["location"]).text
