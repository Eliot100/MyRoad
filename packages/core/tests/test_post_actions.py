"""Issue #53: no state change on GET; default ports in the Origin check."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from myroad_core.auth.origin import _origin_of, allowed_origins, same_origin_ok
from myroad_core.store import PathStore

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient  # noqa: E402
from starlette.requests import Request  # noqa: E402

from myroad_core.agent_builder import FakePathGenerator  # noqa: E402
from myroad_core.ui.app import create_learner_app  # noqa: E402

PATH = "path_grade3_math_add20"


# ---------- Origin: default ports ----------

def _request(scheme: str, host: str, origin: str | None = None, method: str = "POST") -> Request:
    headers = [(b"host", host.encode())]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    return Request({
        "type": "http", "method": method, "scheme": scheme, "path": "/x", "query_string": b"",
        "headers": headers, "server": (host.split(":")[0], 443 if scheme == "https" else 80),
    })


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://MyRoad.example:443", "https://myroad.example"),
        ("https://myroad.example/", "https://myroad.example"),
        ("http://myroad.example:80/path?q=1", "http://myroad.example"),
        ("http://myroad.example:443", "http://myroad.example:443"),
        ("https://myroad.example:80", "https://myroad.example:80"),
        ("https://myroad.example:8443", "https://myroad.example:8443"),
        ("http://[::1]:80", "http://[::1]"),
        ("https://myroad.example:notaport", None),
        ("https://user@myroad.example", None),
        ("null", None),
        ("", None),
    ],
)
def test_origin_is_normalised(url: str, expected: str | None) -> None:
    assert _origin_of(url) == expected


@pytest.mark.parametrize(
    "scheme,host,origin,ok",
    [
        ("https", "myroad.example", "https://myroad.example:443", True),
        ("https", "myroad.example:443", "https://myroad.example", True),
        ("http", "myroad.example:80", "http://myroad.example", True),
        ("http", "myroad.example", "http://myroad.example:80", True),
        ("https", "myroad.example:8443", "https://myroad.example:8443", True),
        ("https", "myroad.example:8443", "https://myroad.example", False),
        ("https", "myroad.example", "http://myroad.example", False),
        ("https", "myroad.example", "https://myroad.example:444", False),
    ],
)
def test_default_ports_match_but_other_ports_do_not(scheme, host, origin, ok) -> None:
    assert same_origin_ok(_request(scheme, host, origin)) is ok


def test_allowed_origins_env_is_normalised_too(monkeypatch) -> None:
    monkeypatch.setenv("MYROAD_ALLOWED_ORIGINS", "https://MyRoad.example:443, bogus")
    req = _request("http", "127.0.0.1:8000", "https://myroad.example")
    assert allowed_origins(req) == {"http://127.0.0.1:8000", "https://myroad.example"}
    assert same_origin_ok(req)


# ---------- /add-path: new and resume are POST ----------

@pytest.fixture
def builder_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_GATEWAY_ID", "CLOUDFLARE_AI_GATEWAY_TOKEN",
                 "CLOUDFLARE_AI_GATEWAY_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    db = tmp_path / "post.db"
    store = PathStore(str(db))
    app = create_learner_app(store=store, db_path=str(db), seed=True, seed_content=True)
    app.state.path_generator_factory = lambda mode: FakePathGenerator()
    with TestClient(app) as client:
        client.cookies.set("myroad_locale", "en")
        client.post("/login", data={"first_name": "Noa", "last_name": "Levi", "email": "post@example.com",
                                    "next": "/"}, follow_redirects=True)
        yield client, store
    store.close()


def _goal(client) -> None:
    r = client.post("/add-path/goal", data={"goal": "Light and shadow", "subject": "physics",
                                            "length": "short", "mode": "demo"}, follow_redirects=False)
    assert r.status_code == 303


def test_get_add_path_new_no_longer_clears_the_builder(builder_client) -> None:
    client, _ = builder_client
    _goal(client)
    assert client.get("/add-path/existing", follow_redirects=False).status_code == 200
    assert client.get("/add-path?new=1").status_code == 200
    # still there: the GET changed nothing
    assert client.get("/add-path/existing", follow_redirects=False).status_code == 200
    page = client.get("/add-path").text
    r = client.post("/add-path/new", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/add-path"
    assert client.get("/add-path/existing", follow_redirects=False).headers["location"] == "/add-path"
    assert page  # rendered fine


def test_add_path_new_needs_same_origin(builder_client) -> None:
    client, _ = builder_client
    _goal(client)
    r = client.post("/add-path/new", headers={"Origin": "https://evil.example"}, follow_redirects=False)
    assert r.status_code == 403
    assert client.get("/add-path/existing", follow_redirects=False).status_code == 200


def test_resume_is_post_only_and_rendered_as_a_form(builder_client) -> None:
    client, _ = builder_client
    _goal(client)
    client.post("/add-path/outline")
    client.post("/add-path/outline/approve", data={})
    client.post("/add-path/new")
    page = client.get("/add-path").text
    actions = re.findall(r'<form method="post" action="(/add-path/resume/[^"]+)" class="link-form">', page)
    assert actions, "draft list should offer resume as a POST form"
    assert 'href="/add-path/resume/' not in page
    assert client.get(actions[0], follow_redirects=False).status_code == 405
    assert client.post(actions[0], headers={"Origin": "https://evil.example"},
                       follow_redirects=False).status_code == 403
    r = client.post(actions[0], follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/add-path/build"
    # The review step offers "start a new path" as a POST form, not a ?new=1 link
    client.post("/add-path/build/all")
    review = client.get("/add-path/review").text
    assert '<form method="post" action="/add-path/new" class="link-form">' in review
    assert 'href="/add-path?new=1"' not in review


def test_resume_someone_elses_draft_is_refused(builder_client) -> None:
    client, _ = builder_client
    _goal(client)
    client.post("/add-path/outline")
    client.post("/add-path/outline/approve", data={})
    client.post("/add-path/new")
    action = re.findall(r'action="(/add-path/resume/[^"]+)"', client.get("/add-path").text)[0]
    client.post("/logout")
    client.post("/login", data={"first_name": "Eve", "last_name": "X", "email": "eve@example.com", "next": "/"})
    r = client.post(action, follow_redirects=False)
    assert r.headers["location"] == "/add-path"


# ---------- /play: attempts are recorded by POST only ----------

@pytest.fixture
def play_client(tmp_path):
    store = PathStore(str(tmp_path / "play.db"))
    app = create_learner_app(store=store, seed=True, seed_content=True)
    with TestClient(app) as c:
        c.post("/login", data={"first_name": "P", "last_name": "L", "email": "play@example.com", "next": "/"},
               follow_redirects=True)
        yield c, store
    store.close()


def _uid(client) -> str:
    return client.app.state.store.get_session_user(client.cookies.get("myroad_session"))


def _attempt_count(store: PathStore, uid: str) -> int:
    return store._conn.execute("SELECT COUNT(*) FROM learner_attempts WHERE user_id = ?", (uid,)).fetchone()[0]


def test_get_stats_view_records_nothing(play_client) -> None:
    c, store = play_client
    c.post(f"/play/{PATH}/start", data={}, follow_redirects=True)
    c.post(f"/play/{PATH}/ack", follow_redirects=True)
    uid = _uid(c)
    for _ in range(3):
        r = c.get(f"/play/{PATH}?view=stats")
        assert r.status_code == 200
    assert _attempt_count(store, uid) == 0
    assert store.latest_attempt(uid, PATH) is None


def test_post_finish_records_one_attempt(play_client) -> None:
    c, store = play_client
    c.post(f"/play/{PATH}/start", data={}, follow_redirects=True)
    c.post(f"/play/{PATH}/ack", follow_redirects=True)
    uid = _uid(c)
    r = c.post(f"/play/{PATH}/finish", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/play/{PATH}?view=stats"
    assert _attempt_count(store, uid) == 1
    c.post(f"/play/{PATH}/finish", follow_redirects=False)
    c.get(f"/play/{PATH}?view=stats")
    assert _attempt_count(store, uid) == 1  # once per play session
    attempt = store.latest_attempt(uid, PATH)
    assert attempt["nodesCompleted"] == 1


def test_post_finish_needs_same_origin(play_client) -> None:
    c, store = play_client
    c.post(f"/play/{PATH}/start", data={}, follow_redirects=True)
    r = c.post(f"/play/{PATH}/finish", headers={"Origin": "https://evil.example"}, follow_redirects=False)
    assert r.status_code == 403
    assert _attempt_count(store, _uid(c)) == 0


def test_finishing_answer_records_the_attempt_before_the_stats_get(play_client) -> None:
    c, store = play_client
    c.post(f"/play/{PATH}/start", data={}, follow_redirects=True)
    c.post(f"/play/{PATH}/ack", follow_redirects=True)
    for choice in ("b", "c", "b"):
        c.post(f"/play/{PATH}/answer", data={"choice": choice}, follow_redirects=True)
    uid = _uid(c)
    r = c.post(f"/play/{PATH}/ack", follow_redirects=False)  # last block
    assert r.headers["location"] == f"/play/{PATH}?view=stats"
    assert _attempt_count(store, uid) == 1  # recorded by the POST, not the GET
    page = c.get(r.headers["location"])
    assert page.status_code == 200
    assert _attempt_count(store, uid) == 1
    assert store.latest_attempt(uid, PATH)["masteryPct"] >= 90
