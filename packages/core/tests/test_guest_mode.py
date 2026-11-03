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
    assert store.get_progress(_uid(b), PLACE) is None
    assert b.get("/api/settings/steps").json() == {"audio": True, "writing": False}  # a1w0 default
    assert b.get("/api/placement/result").status_code == 404
    # B logging in must not pull A's data.
    login_with_code(b, {"first_name": "B", "last_name": "B", "email": "b210@example.com", "next": "/"})
    assert store.get_progress(_uid(b), PLACE) is None


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
    # No cookie on a POST: no guest is minted for a state change.
    assert fresh.post(f"/play/{PLACE}/answer", data={"choice": "a"}, follow_redirects=False).status_code == 303
    assert fresh.cookies.get("myroad_session") is None


def test_returning_learner_login_merges_guest_without_overwriting(app_store) -> None:
    app, store = app_store
    c = TestClient(app)
    login_with_code(c, {"first_name": "R", "last_name": "R", "email": "r210@example.com", "next": "/"})
    uid = _uid(c)
    c.post("/logout")
    c.cookies.clear()
    c.get("/")
    gid = _uid(c)
    assert store.is_guest(gid) and gid != uid
    c.post(f"/play/{PLACE}/start", data={"reset": "1"})
    _answer(c), _answer(c)
    login_with_code(c, {"email": "r210@example.com", "next": "/"})
    assert _uid(c) == uid and store.get_progress(uid, PLACE)["mastered"]
    assert store.get_learner(gid) is None
