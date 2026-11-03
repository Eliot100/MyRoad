"""Guest mode (#210): practise before sign-up, offer sign-up once, keep progress on sign-up."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code
from test_english_bagrut_flow import PLACE, ZERO, _mini

from myroad_core.auth.principal import resolve_principal
from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

H = {"X-MyRoad-Request": "1"}


@pytest.fixture
def app_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_mini(PLACE, "מבדק רמה", []), _mini(ZERO, "מאפס", [PLACE])):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "g.db"))
    yield create_learner_app(store=store, seed=False, seed_content=True), store
    store.close()


def _uid(c) -> str | None:
    return c.app.state.store.get_session_user(c.cookies.get("myroad_session"))


def _guest(app) -> TestClient:
    c = TestClient(app)
    c.cookies.set("myroad_locale", "en")
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 200, r.headers.get("location")
    assert c.cookies.get("myroad_session") is None  # lazy: a page view creates nothing
    c.post(f"/play/{PLACE}/start", data={"reset": "1"})  # first POST -> guest
    return c


def _answer(c, choice="a"):
    return c.post(f"/play/{PLACE}/answer", data={"choice": choice}, follow_redirects=False)


def test_guest_practises_offer_once_then_signup_keeps_everything(app_store) -> None:
    app, store = app_store
    c = _guest(app)
    gid = _uid(c)
    assert store.is_guest(gid)
    guest = store.get_learner(gid)
    assert not guest["email"] and not guest.get("firstName") and not guest.get("lastName")  # no PII
    assert c.cookies.get("myroad_locale") == "en" and guest["locale"] == "en"
    # One-tap preference stored on the guest.
    assert c.post("/api/settings/steps", json={"audio": False, "writing": True}, headers=H).json() == {
        "audio": False, "writing": True}
    assert c.get(f"/play/{PLACE}").status_code == 200
    c.post(f"/play/{PLACE}/start", data={"reset": "1"})
    assert "x-offer-registration" not in _answer(c).headers  # learn step: not a passed step
    first_pass = _answer(c)
    assert first_pass.headers.get("x-offer-registration") == "true"
    assert c.get("/api/guest").json() == {"is_guest": True, "offer_registration": True}
    assert "x-offer-registration" not in _answer(c).headers  # once only
    c.post("/api/guest/offer/dismiss")
    assert c.get("/api/guest").json()["offer_registration"] is False
    before = store.get_progress(gid, PLACE)
    assert before and before["mastered"]
    # Register by email code: the account gets the guest's progress and preference.
    login_with_code(c, {"first_name": "Gal", "last_name": "G", "email": "g210@example.com", "next": "/"})
    uid = _uid(c)
    assert uid and not store.is_guest(uid)
    after = store.get_progress(uid, PLACE)
    assert after["mastered"] == before["mastered"] and after["nodeIndex"] == before["nodeIndex"]
    assert store.get_step_settings(uid) == {"audio": False, "writing": True}
    assert store.get_learner(gid) is None and store.get_progress(gid, PLACE) is None  # no duplicate
    assert c.get("/api/guest").json() == {"is_guest": False, "offer_registration": False}
    assert c.get("/settings", follow_redirects=False).status_code == 200


def test_guest_data_not_visible_to_another_guest(app_store) -> None:
    app, store = app_store
    a, b = _guest(app), _guest(app)
    assert _uid(a) != _uid(b)
    a.post(f"/play/{PLACE}/start", data={"reset": "1"})
    _answer(a), _answer(a)
    a.post("/api/settings/steps", json={"writing": True}, headers=H)
    assert store.get_progress(_uid(a), PLACE)
    assert not (store.get_progress(_uid(b), PLACE) or {}).get("mastered")
    assert b.get("/api/settings/steps").json() == {"audio": True, "writing": False}  # a1w0 default
    assert b.get("/api/placement/result").status_code == 404
    # B logging in must not pull A's data.
    login_with_code(b, {"first_name": "B", "last_name": "B", "email": "b210@example.com", "next": "/"})
    assert not (store.get_progress(_uid(b), PLACE) or {}).get("mastered")


def test_guest_cannot_reach_author_settings_or_tools(app_store) -> None:
    app, store = app_store
    c = _guest(app)
    for path in ("/author", "/settings", "/add-path"):
        r = c.get(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/login?next="), path
    req = SimpleNamespace(headers={}, cookies={"myroad_session": c.cookies.get("myroad_session")})
    assert resolve_principal(req, store) is None
    fresh = TestClient(app)
    assert fresh.get("/author", follow_redirects=False).status_code == 303
    assert fresh.post("/settings", data={}, follow_redirects=False).status_code == 303
    assert fresh.cookies.get("myroad_session") is None  # no guest for account routes


def test_returning_learner_login_merges_guest_without_overwriting(app_store) -> None:
    app, store = app_store
    c = TestClient(app)
    login_with_code(c, {"first_name": "R", "last_name": "R", "email": "r210@example.com", "next": "/"})
    uid = _uid(c)
    c.post("/logout")
    c.cookies.clear()
    c.get("/")
    c.post(f"/play/{PLACE}/start", data={"reset": "1"})
    gid = _uid(c)
    assert store.is_guest(gid) and gid != uid
    c.post(f"/play/{PLACE}/start", data={"reset": "1"})
    _answer(c), _answer(c)
    login_with_code(c, {"email": "r210@example.com", "next": "/"})
    assert _uid(c) == uid and store.get_progress(uid, PLACE)["mastered"]
    assert store.get_learner(gid) is None


def _row_counts(store) -> dict[str, int]:
    # `events` is the tool audit trail; reads by the fixed POC learner actor log there for every
    # visitor (pre-existing, no visitor id). Every learner/guest/session table must stay unchanged.
    tables = [r[0] for r in store._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
              if r[0] != "events"]
    return {t: store._conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


def test_crawler_100_gets_writes_nothing(app_store) -> None:
    app, store = app_store
    before = _row_counts(store)
    for i in range(100):
        c = TestClient(app)  # cookieless every time, like a crawler
        path = ("/", f"/play/{PLACE}", f"/play/{ZERO}", f"/play/{PLACE}?view=learn")[i % 4]
        assert c.get(path, follow_redirects=False).status_code == 200, path
    assert _row_counts(store) == before


def test_guest_creation_rate_limited_per_ip(app_store) -> None:
    from myroad_core.ui.guest_limit import GuestLimiter

    app, store = app_store
    app.state.guest_limiter.__init__(max_per_window=3)
    codes = []
    for _ in range(5):
        c = TestClient(app)
        codes.append(c.post(f"/play/{PLACE}/start", data={"reset": "1"}, follow_redirects=False).status_code)
    assert 429 not in codes[:3] and codes[3:] == [429, 429]
    assert sum(1 for r in store._conn.execute("SELECT user_id FROM learners") if store.is_guest(r[0])) == 3
    t = [0.0]
    lim = GuestLimiter(max_per_window=1, window=10, clock=lambda: t[0])
    assert lim.allow("ip") and not lim.allow("ip") and lim.allow("other")
    t[0] = 11
    assert lim.allow("ip")  # window slid


def test_offer_flag_persists_in_db_across_app_instances(app_store, tmp_path) -> None:
    app, store = app_store
    c = _guest(app)
    gid = _uid(c)
    _answer(c), _answer(c)
    assert store.get_guest_offer(gid) == "offered"
    c.post("/api/guest/offer/dismiss")
    # A second worker on the same DB sees the same state.
    other = PathStore(str(tmp_path / "g.db"))
    try:
        assert other.get_guest_offer(gid) == "dismissed"
    finally:
        other.close()
    assert "x-offer-registration" not in _answer(c).headers


def test_cleanup_deletes_idle_guests_and_rows_idempotently(app_store) -> None:
    from datetime import datetime, timedelta, timezone

    from myroad_core.guest_cleanup import main as cleanup_main

    app, store = app_store
    old, fresh = _guest(app), _guest(app)
    _answer(old), _answer(old)
    oid, fid = _uid(old), _uid(fresh)
    acct = TestClient(app)
    login_with_code(acct, {"first_name": "K", "last_name": "K", "email": "k241@example.com", "next": "/"})
    later = datetime.now(timezone.utc) + timedelta(days=31)
    # Run the job "31 days from now": the old guest is idle past 30 days, the fresh one was active a day ago.
    stamp = (later - timedelta(days=1)).isoformat()
    store._conn.execute("UPDATE learners SET updated_at = ? WHERE user_id = ?", (stamp, fid))
    store._conn.commit()
    assert store.purge_stale_guests(now=later) == 1
    counts = {t: store._conn.execute(f"SELECT COUNT(*) FROM {t} WHERE user_id = ?", (oid,)).fetchone()[0]
              for t in ("learners", "learner_progress", "learner_events", "learner_attempts",
                        "learner_sessions", "placement_details", "auth_sessions")}
    assert set(counts.values()) == {0}, counts
    assert store.get_learner(fid) and store.get_learner_by_email("k241@example.com")
    assert store.purge_stale_guests(now=later) == 0  # idempotent
    assert old.get("/api/guest").json()["is_guest"] is False  # old cookie is dead
    assert cleanup_main(["--db", app.state.db_path]) == 0
