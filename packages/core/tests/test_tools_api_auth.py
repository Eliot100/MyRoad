"""Issue #40: /tools/* needs a session or the agent credential; actor never from the body."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from myroad_core.api import create_app
from myroad_core.auth import AGENT_ID_ENV, AGENT_TOKEN_ENV, SESSION_COOKIE
from myroad_core.auth.sessions import session_digest
from myroad_core.store import PathStore

AGENT_CRED = "test-agent-credential-0123456789abcdef"

TOOL_ROUTES = [
    "/tools/createDraft",
    "/tools/getPath",
    "/tools/getVersion",
    "/tools/addBlock",
    "/tools/editBlock",
    "/tools/addEdge",
    "/tools/reviseDraft",
    "/tools/validatePath",
    "/tools/recordFeedback",
    "/tools/requestPublish",
    "/tools/publish",
]


@pytest.fixture
def store(tmp_path) -> PathStore:
    s = PathStore(str(tmp_path / "api.db"))
    yield s
    s.close()


@pytest.fixture
def client(store: PathStore, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(AGENT_TOKEN_ENV, raising=False)
    monkeypatch.delenv(AGENT_ID_ENV, raising=False)
    with TestClient(create_app(store)) as c:
        c.headers["X-MyRoad-Request"] = "1"  # CSRF header for cookie-authenticated calls
        yield c


def _draft_body(**extra) -> dict:
    return {"correlationId": "corr_api_1", "name": "API path", "goal": "Learn", **extra}


def _user_session(store: PathStore, email: str = "api.user@example.com") -> tuple[str, str]:
    learner = store.register_or_login(email=email, first_name="Api", last_name="User")
    return learner["userId"], store.create_session(learner["userId"])


def test_tool_routes_list_matches_app(client: TestClient) -> None:
    registered = {r.path for r in client.app.routes if getattr(r, "path", "").startswith("/tools/")}
    assert registered == set(TOOL_ROUTES)


@pytest.mark.parametrize("route", TOOL_ROUTES + ["/tools/doesNotExist"])
def test_unauthenticated_is_401_on_every_tools_route(client: TestClient, route: str) -> None:
    r = client.post(route, json=_draft_body(actorId="user_attacker"))
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"
    assert r.json()["detail"]["code"] == "UNAUTHENTICATED"


def test_unauthenticated_does_not_write(client: TestClient, store: PathStore) -> None:
    client.post("/tools/createDraft", json=_draft_body(actorId="user_attacker"))
    assert store._conn.execute("SELECT COUNT(*) FROM paths").fetchone()[0] == 0
    assert store._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_health_stays_open(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


def test_agent_access_disabled_when_env_unset(client: TestClient) -> None:
    r = client.post(
        "/tools/createDraft", json=_draft_body(), headers={"Authorization": f"Bearer {AGENT_CRED}"}
    )
    assert r.status_code == 401


def test_empty_or_short_env_credential_does_not_enable_agent(client, monkeypatch) -> None:
    monkeypatch.setenv(AGENT_TOKEN_ENV, "")
    assert client.post("/tools/createDraft", json=_draft_body(),
                       headers={"Authorization": "Bearer "}).status_code == 401
    monkeypatch.setenv(AGENT_TOKEN_ENV, "short")
    assert client.post("/tools/createDraft", json=_draft_body(),
                       headers={"Authorization": "Bearer short"}).status_code == 401


def test_wrong_agent_credential_is_401(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv(AGENT_TOKEN_ENV, AGENT_CRED)
    for header in (f"Bearer {AGENT_CRED}x", "Bearer nope", f"Basic {AGENT_CRED}", AGENT_CRED):
        r = client.post("/tools/createDraft", json=_draft_body(), headers={"Authorization": header})
        assert r.status_code == 401, header


def test_agent_credential_actor_comes_from_server(client, store, monkeypatch) -> None:
    monkeypatch.setenv(AGENT_TOKEN_ENV, AGENT_CRED)
    monkeypatch.setenv(AGENT_ID_ENV, "agent_partner_1")
    r = client.post(
        "/tools/createDraft", json=_draft_body(), headers={"Authorization": f"Bearer {AGENT_CRED}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    events = store.query_events(correlation_id="corr_api_1")
    assert events and all(e.actorId == "agent_partner_1" for e in events)
    assert all(e.agentId == "agent_partner_1" for e in events)
    # The credential itself is never persisted
    dump = "\n".join(store._conn.iterdump())
    assert AGENT_CRED not in dump


def test_agent_default_actor_id(client, store, monkeypatch) -> None:
    monkeypatch.setenv(AGENT_TOKEN_ENV, AGENT_CRED)
    r = client.post(
        "/tools/createDraft", json=_draft_body(), headers={"Authorization": f"Bearer {AGENT_CRED}"}
    )
    assert r.status_code == 200
    assert store.query_events(correlation_id="corr_api_1")[0].actorId == "agent_service"


def test_actor_from_session(client: TestClient, store: PathStore) -> None:
    user_id, sid = _user_session(store)
    client.cookies.set(SESSION_COOKIE, sid)
    r = client.post("/tools/createDraft", json=_draft_body())
    assert r.status_code == 200, r.text
    resp = r.json()
    assert resp["ok"] is True
    events = store.query_events(correlation_id="corr_api_1")
    assert events and all(e.actorId == user_id for e in events)
    assert all(e.agentId is None for e in events)
    # Follow-up read works under the same session
    got = client.post(
        "/tools/getPath", json={"correlationId": "corr_api_2", "pathId": resp["pathId"]}
    )
    assert got.status_code == 200 and got.json()["ok"] is True


def test_body_actor_matching_session_is_accepted(client, store) -> None:
    user_id, sid = _user_session(store)
    client.cookies.set(SESSION_COOKIE, sid)
    r = client.post("/tools/createDraft", json=_draft_body(actorId=user_id))
    assert r.status_code == 200 and r.json()["ok"] is True


@pytest.mark.parametrize(
    "route,extra",
    [
        ("/tools/createDraft", {"actorId": "user_someone_else"}),
        ("/tools/createDraft", {"agentId": "agent_spoofed"}),
        ("/tools/publish", {"pathId": "p", "versionId": "v", "publisherId": "user_someone_else"}),
    ],
)
def test_body_identity_differing_from_session_is_403(client, store, route, extra) -> None:
    _, sid = _user_session(store)
    client.cookies.set(SESSION_COOKIE, sid)
    r = client.post(route, json=_draft_body(**extra))
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "ACTOR_MISMATCH"
    assert store._conn.execute("SELECT COUNT(*) FROM paths").fetchone()[0] == 0


def test_body_actor_cannot_override_agent(client, store, monkeypatch) -> None:
    monkeypatch.setenv(AGENT_TOKEN_ENV, AGENT_CRED)
    r = client.post(
        "/tools/createDraft",
        json=_draft_body(actorId="user_victim"),
        headers={"Authorization": f"Bearer {AGENT_CRED}"},
    )
    assert r.status_code == 403
    assert store._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_unknown_expired_or_revoked_session_is_401(client, store) -> None:
    client.cookies.set(SESSION_COOKIE, "not-a-session")
    assert client.post("/tools/createDraft", json=_draft_body()).status_code == 401

    learner = store.register_or_login(email="old@example.com", first_name="Old", last_name="User")
    expired = store.create_session(learner["userId"], ttl_seconds=-1)
    client.cookies.set(SESSION_COOKIE, expired)
    assert client.post("/tools/createDraft", json=_draft_body()).status_code == 401

    _, live = _user_session(store, "rev@example.com")
    store.revoke_session(live)
    client.cookies.set(SESSION_COOKIE, live)
    assert client.post("/tools/createDraft", json=_draft_body()).status_code == 401


def test_user_id_as_cookie_is_not_a_session(client, store) -> None:
    user_id, _ = _user_session(store)
    client.cookies.set(SESSION_COOKIE, user_id)
    client.cookies.set("myroad_uid", user_id)
    assert client.post("/tools/createDraft", json=_draft_body()).status_code == 401


def test_wrong_bearer_does_not_fall_back_to_session(client, store, monkeypatch) -> None:
    monkeypatch.setenv(AGENT_TOKEN_ENV, AGENT_CRED)
    _, sid = _user_session(store)
    client.cookies.set(SESSION_COOKIE, sid)
    r = client.post("/tools/createDraft", json=_draft_body(), headers={"Authorization": "Bearer bad"})
    assert r.status_code == 401


def test_session_id_is_stored_hashed(store: PathStore) -> None:
    _, sid = _user_session(store)
    rows = store._conn.execute("SELECT sid_hash FROM auth_sessions").fetchall()
    assert [r[0] for r in rows] == [session_digest(sid)]
    assert sid not in "\n".join(store._conn.iterdump())


def test_ui_login_session_is_accepted_by_tools_api(tmp_path, monkeypatch) -> None:
    pytest.importorskip("jinja2")
    from myroad_core.ui.app import create_learner_app

    monkeypatch.delenv(AGENT_TOKEN_ENV, raising=False)
    shared = PathStore(str(tmp_path / "shared.db"))
    try:
        ui = TestClient(create_learner_app(store=shared, seed=False, seed_content=False))
        ui.post(
            "/login",
            data={"first_name": "Noa", "last_name": "Levi", "email": "noa.api@example.com", "next": "/"},
            follow_redirects=False,
        )
        sid = ui.cookies.get(SESSION_COOKIE)
        assert sid
        user_id = shared.get_learner_by_email("noa.api@example.com")["userId"]
        api = TestClient(create_app(shared), headers={"X-MyRoad-Request": "1"})
        api.cookies.set(SESSION_COOKIE, sid)
        r = api.post("/tools/createDraft", json=_draft_body())
        assert r.status_code == 200 and r.json()["ok"] is True
        assert shared.query_events(correlation_id="corr_api_1")[0].actorId == user_id
    finally:
        shared.close()


def test_forged_uid_cookie_does_not_sign_in_to_ui(tmp_path) -> None:
    pytest.importorskip("jinja2")
    from myroad_core.ui.app import create_learner_app

    shared = PathStore(str(tmp_path / "ui.db"))
    try:
        learner = shared.register_or_login(email="victim@example.com", first_name="V", last_name="Ictim")
        ui = TestClient(create_learner_app(store=shared, seed=False, seed_content=False))
        ui.cookies.set("myroad_uid", learner["userId"])
        r = ui.get("/settings", follow_redirects=False)
        assert r.status_code == 303 and "/login" in r.headers["location"]
    finally:
        shared.close()


# ---------- Cyber security review of #46: CSRF, ownership, agent scope ----------

def _create(client, **extra) -> dict:
    r = client.post("/tools/createDraft", json=_draft_body(**extra))
    assert r.status_code == 200 and r.json()["ok"], r.text
    return r.json()


def test_cookie_call_without_csrf_header_is_403(client, store) -> None:
    _, sid = _user_session(store)
    client.cookies.set(SESSION_COOKIE, sid)
    del client.headers["X-MyRoad-Request"]
    r = client.post("/tools/createDraft", json=_draft_body())
    assert r.status_code == 403 and r.json()["detail"]["code"] == "CSRF_HEADER_REQUIRED"
    r = client.post("/tools/createDraft", json=_draft_body(), headers={"X-MyRoad-Request": "0"})
    assert r.status_code == 403
    assert store._conn.execute("SELECT COUNT(*) FROM paths").fetchone()[0] == 0


def test_bearer_call_needs_no_csrf_header(client, store, monkeypatch) -> None:
    monkeypatch.setenv(AGENT_TOKEN_ENV, AGENT_CRED)
    del client.headers["X-MyRoad-Request"]
    r = client.post("/tools/createDraft", json=_draft_body(), headers={"Authorization": f"Bearer {AGENT_CRED}"})
    assert r.status_code == 200


def _path_ops(path_id: str, version_id: str) -> list[tuple[str, dict]]:
    base = {"correlationId": "corr_x", "pathId": path_id, "versionId": version_id}
    return [
        ("/tools/getPath", base),
        ("/tools/getVersion", base),
        ("/tools/addBlock", {**base, "type": "explanation", "title": "Injected"}),
        ("/tools/editBlock", {**base, "blockId": "blk_x", "patch": {"title": "x"}}),
        ("/tools/addEdge", {**base, "from": "a", "to": "b", "relationship": "sequence"}),
        ("/tools/reviseDraft", {**base, "baseVersionId": version_id}),
        ("/tools/validatePath", base),
        ("/tools/recordFeedback", {**base, "comment": "x"}),
        ("/tools/requestPublish", base),
        ("/tools/publish", base),
    ]


def test_user_cannot_touch_another_users_path(client, store) -> None:
    _, sid_a = _user_session(store, "alice@example.com")
    client.cookies.set(SESSION_COOKIE, sid_a)
    created = _create(client)
    pid, vid = created["pathId"], created["versionId"]
    events_before = store._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    _, sid_b = _user_session(store, "bob@example.com")
    client.cookies.set(SESSION_COOKIE, sid_b)
    for route, body in _path_ops(pid, vid):
        r = client.post(route, json=body)
        assert r.status_code == 404, (route, r.status_code, r.text)
        assert r.json()["detail"]["code"] == "NOT_FOUND"
        assert "Injected" not in r.text
    # Same answer as a path that does not exist
    missing = client.post("/tools/getPath", json={"correlationId": "c", "pathId": "path_nope"})
    assert missing.status_code == 404
    # Nothing written, nothing published
    assert store._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == events_before
    assert store.get_version(pid, vid).status.value == "draft"
    assert store.get_version(pid, vid).blocks == []


def test_owner_can_read_and_edit_own_path(client, store) -> None:
    _, sid = _user_session(store, "own@example.com")
    client.cookies.set(SESSION_COOKIE, sid)
    created = _create(client)
    pid, vid = created["pathId"], created["versionId"]
    r = client.post("/tools/addBlock", json={"correlationId": "c", "pathId": pid, "versionId": vid,
                                             "type": "explanation", "title": "Mine"})
    assert r.status_code == 200 and r.json()["ok"]
    got = client.post("/tools/getVersion", json={"correlationId": "c", "pathId": pid, "versionId": vid})
    assert got.status_code == 200 and "Mine" in got.text


def test_agent_scoped_to_its_own_paths_or_allow_list(client, store, monkeypatch) -> None:
    monkeypatch.setenv(AGENT_TOKEN_ENV, AGENT_CRED)
    bearer = {"Authorization": f"Bearer {AGENT_CRED}"}
    # A user's path: the agent may not touch it
    _, sid = _user_session(store, "user.path@example.com")
    client.cookies.set(SESSION_COOKIE, sid)
    user_path = _create(client)
    client.cookies.clear()
    for route, body in _path_ops(user_path["pathId"], user_path["versionId"]):
        assert client.post(route, json=body, headers=bearer).status_code == 404, route
    # Its own draft: allowed
    own = client.post("/tools/createDraft", json=_draft_body(), headers=bearer).json()
    r = client.post("/tools/getPath", json={"correlationId": "c", "pathId": own["pathId"]}, headers=bearer)
    assert r.status_code == 200 and r.json()["ok"]
    # Explicit allow-list grants a named path
    monkeypatch.setenv("MYROAD_AGENT_ALLOWED_PATHS", f"path_other, {user_path['pathId']}")
    r = client.post("/tools/getPath", json={"correlationId": "c", "pathId": user_path["pathId"]}, headers=bearer)
    assert r.status_code == 200
    # The allow-list never applies to users
    _, sid_c = _user_session(store, "carol@example.com")
    client.cookies.set(SESSION_COOKIE, sid_c)
    r = client.post("/tools/getPath", json={"correlationId": "c", "pathId": user_path["pathId"]})
    assert r.status_code == 404


def test_doc_author_field_cannot_grant_access(client, store) -> None:
    _, sid_a = _user_session(store, "a2@example.com")
    client.cookies.set(SESSION_COOKIE, sid_a)
    created = _create(client)
    bob_id, sid_b = _user_session(store, "b2@example.com")
    # Even if the document claims bob is the author, ownership follows paths.author_id
    rev = store.revise_draft(
        actor_id="x", correlation_id="c", path_id=created["pathId"], base_version_id=created["versionId"],
        change_set={"actors": {"authorId": bob_id}},
    )
    client.cookies.set(SESSION_COOKIE, sid_b)
    r = client.post("/tools/getVersion", json={"correlationId": "c", "pathId": created["pathId"],
                                               "versionId": rev.versionId})
    assert r.status_code == 404


def test_revise_change_set_cannot_publish_or_move_a_version(client, store) -> None:
    _, sid = _user_session(store, "rev2@example.com")
    client.cookies.set(SESSION_COOKIE, sid)
    created = _create(client)
    pid, vid = created["pathId"], created["versionId"]
    r = client.post("/tools/reviseDraft", json={
        "correlationId": "c", "pathId": pid, "baseVersionId": vid,
        "changeSet": {"status": "published", "pathId": "path_victim", "versionId": "ver_x", "version": 99},
    })
    assert r.status_code == 200 and r.json()["ok"], r.text
    new_vid = r.json()["versionId"]
    doc = store.get_version(pid, new_vid)
    assert doc.status.value == "draft" and doc.pathId == pid and new_vid != "ver_x" and doc.version == 2
