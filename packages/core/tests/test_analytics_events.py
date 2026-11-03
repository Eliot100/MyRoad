"""Pseudonymous analytics (#208): POST /api/events, server-side answer events, no PII."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code
from test_english_bagrut_flow import _mini

from myroad_core.analytics import PiiError, assert_no_pii, find_pii
from myroad_core.store import PathStore
from myroad_core.ui import events_api
from myroad_core.ui.app import create_learner_app

PLACE = "path_english_bagrut5_00_placement"
ZERO = "path_english_bagrut5_01_zero"
EMAIL = "ev208@example.com"
H = {"X-MyRoad-Request": "1"}


def _placement(items: int) -> dict:
    doc = _mini(PLACE, "מבדק רמה", [])
    prac = next(n for n in doc["nodes"] if n["type"] == "practice")
    doc["nodes"] = [dict(prac, id=f"p{i}", title=f"שאלה {i}") for i in range(items)]
    doc["topics"] = [dict(doc["topics"][0], node_ids=[f"p{i}" for i in range(items)])]
    return doc


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MYROAD_ANALYTICS", "1")
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_placement(2), _mini(ZERO, "מאפס", [PLACE])):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "e.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    c = TestClient(app)
    login_with_code(c, {"first_name": "Dana", "last_name": "Levi", "email": EMAIL, "next": "/"})
    yield c, store
    store.close()


def _batch(*events):
    return {"events": list(events)}


TAP = {"type": "tap", "screen": "/play/x", "ts": 1, "props": {"target": "btn-next"}}


def _all_payload_text(store) -> str:
    rows = store._conn.execute("SELECT * FROM analytics_events").fetchall()
    return json.dumps([dict(r) for r in rows], ensure_ascii=False)


def test_client_batch_stored_under_pseudonym(env):
    c, store = env
    r = c.post("/api/events", json=_batch(
        TAP,
        {"type": "screen_view", "screen": "/series/english-bagrut5", "props": {"from_screen": "/", "ms": 1200}},
        {"type": "answer_submit", "screen": "/play/p", "props": {"path_id": PLACE, "latency_ms": 900}},
    ), headers=H)
    assert r.status_code == 204
    evs = store.list_analytics_events()
    assert [e["type"] for e in evs] == ["tap", "screen_view", "answer_submit"]
    uid = store.get_learner_by_email(EMAIL)["userId"]
    aid = store.analytics_id_for(uid)
    assert aid.startswith("a_") and aid != uid and uid not in aid
    assert {e["analyticsId"] for e in evs} == {aid}
    assert evs[1]["props"] == {"from_screen": "/", "ms": 1200}


def test_requires_header_and_session(env):
    c, _ = env
    assert c.post("/api/events", json=_batch(TAP)).status_code == 403
    anon = TestClient(c.app)
    assert anon.post("/api/events", json=_batch(TAP), headers=H).status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {"events": []},
        _batch({"type": "login", "props": {}}),
        _batch({"type": "answer", "props": {}}),  # server-only type
        _batch(dict(TAP, extra=1)),
        _batch({"type": "tap", "props": {"email": "a@b.co"}}),
        _batch({"type": "tap", "props": {"target": "dana@example.com"}}),
        _batch({"type": "tap", "props": {"target": "has space"}}),
        _batch(*[TAP] * 51),
    ],
)
def test_invalid_or_unknown_rejected(env, body):
    c, store = env
    assert c.post("/api/events", json=body, headers=H).status_code == 422
    assert store.list_analytics_events() == []


def test_size_and_rate_limits(env, monkeypatch):
    c, _ = env
    big = json.dumps(_batch(*[dict(TAP, props={"target": "x" * 160})] * 50)) + " " * 20000
    r = c.post("/api/events", content=big, headers={**H, "Content-Type": "application/json"})
    assert r.status_code == 413
    monkeypatch.setattr(events_api, "RATE_BATCHES", 3)
    codes = [c.post("/api/events", json=_batch(TAP), headers=H).status_code for _ in range(5)]
    assert codes[-1] == 429


def test_switch_off_stores_nothing(env, monkeypatch):
    c, store = env
    monkeypatch.setenv("MYROAD_ANALYTICS", "0")
    assert c.post("/api/events", json=_batch(TAP), headers=H).status_code == 204
    assert store.list_analytics_events() == []
    assert "/static/analytics.js" not in c.get("/").text
    monkeypatch.setenv("MYROAD_ANALYTICS", "1")
    assert "/static/analytics.js" in c.get("/").text


def test_server_emits_placement_and_play_answers(env):
    c, store = env
    c.post(f"/play/{PLACE}/start", data={"reset": "1"})
    c.post(f"/play/{PLACE}/answer", data={"choice": "b"}, follow_redirects=False)
    c.post(f"/play/{PLACE}/answer", data={"choice": "a"}, follow_redirects=False)
    c.post("/api/placement/result", json={"answers": [{"questionId": "q1", "correct": True}]}, headers=H)
    evs = [e for e in store.list_analytics_events() if e["source"] == "server"]
    types = [e["type"] for e in evs]
    assert types.count("placement_answer") == 3 and "placement_result" in types
    first = evs[0]["props"]
    assert first["path_id"] == PLACE and first["ok"] is False and "latency_ms" in first


def test_no_pii_in_any_stored_payload(env):
    """Scan every stored analytics row after a full flow: no email, name, IP or user agent."""
    c, store = env
    c.post("/api/events", json=_batch(TAP), headers={**H, "User-Agent": "Mozilla/5.0 Chrome/1"})
    c.post(f"/play/{PLACE}/start", data={"reset": "1"})
    c.post(f"/play/{PLACE}/answer", data={"choice": "a"}, follow_redirects=False)
    rows = store._conn.execute("SELECT * FROM analytics_events").fetchall()
    assert rows
    for r in rows:
        assert find_pii({"screen": r["screen"], "props": json.loads(r["props_json"])}) == []
    text = _all_payload_text(store)
    uid = store.get_learner_by_email(EMAIL)["userId"]
    for needle in (EMAIL, "Dana", "Levi", "testclient", "Mozilla", uid):
        assert needle not in text


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "x"},
        {"props": {"first_name": "x"}},
        {"props": {"userAgent": "x"}},
        {"props": {"ip": "x"}},
        {"props": {"note": "write to a@b.io"}},
        {"props": {"t": "10.0.0.1"}},
        {"props": [{"v": "Mozilla/5.0 (X11)"}]},
    ],
)
def test_pii_scanner_rejects(payload):
    with pytest.raises(PiiError):
        assert_no_pii(payload)


def test_pii_scanner_allows_clean():
    assert_no_pii({"screen": "/play/path_x", "props": {"target": "btn-next", "ms": 5, "block_id": "p1"}})


def test_server_types_not_accepted_from_store_client_path(store, monkeypatch):
    monkeypatch.setenv("MYROAD_ANALYTICS", "1")
    with pytest.raises(ValueError):
        store.record_analytics_events("u1", [{"type": "answer"}], source="client")
    assert store.record_analytics_events("u1", [{"type": "answer", "props": {"ok": True}}], source="server") == 1
