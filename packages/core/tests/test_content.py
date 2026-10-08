"""Content schema validation + catalog/player smoke tests."""

from __future__ import annotations

import pytest

from myroad_core.content.loader import (
    content_to_path_version,
    default_content_dir,
    list_catalog_cards,
    load_content_paths,
    seed_content_paths,
)
from myroad_core.content.schema import ContentPath, infer_topics, validate_content_path
from myroad_core.models import PathStatus
from myroad_core.store import PathStore

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code, request_login_code

from myroad_core.ui.app import create_learner_app

def _uid(client) -> str | None:
    """Signed-in user id, resolved from the server-side session cookie."""
    return client.app.state.store.get_session_user(client.cookies.get("myroad_session"))


def _reg(client, email: str, first: str = "Test", last: str = "User"):
    return login_with_code(
        client,
        data={"first_name": first, "last_name": last, "email": email, "next": "/"},
        follow_redirects=True,
    )



def test_all_grade3_paths_validate() -> None:
    all_paths = load_content_paths(default_content_dir())
    assert all_paths, "no content paths found"
    # path ids are unique across the whole content tree
    assert len({p.id for p in all_paths}) == len(all_paths)
    # the grade-3 demo checks apply only to grade-3 paths, not to new audiences
    paths = [p for p in all_paths if "grade3" in p.group_ids]
    assert paths, "no grade3 paths found"
    for p in paths:
        assert p.grade == 3
        assert "grade3" in p.group_ids
        assert p.subject in {"math", "english", "physics", "piano"}
        assert 5 <= p.estimated_minutes <= 15
        assert len(p.nodes) >= 3
        topics = infer_topics(p)
        assert len(topics) >= 1
        # every node id unique
        node_ids = [n.id for n in p.nodes]
        assert all(node_ids)
        assert len(node_ids) == len(set(node_ids))


def test_english_paths_are_longer() -> None:
    paths = {p.id: p for p in load_content_paths(default_content_dir())}
    for pid in (
        "path_grade3_english_colors",
        "path_grade3_english_animals",
        "path_grade3_english_hello",
    ):
        p = paths[pid]
        assert 8 <= len(p.nodes) <= 12
        assert p.title_en
        assert p.blurb_en
        assert p.topics and len(p.topics) >= 3
        assert any(n.type == "speak" for n in p.nodes)
        assert any(n.speak_text for n in p.nodes)


def test_topics_schema_and_infer() -> None:
    data = {
        "id": "path_test_topics",
        "title_he": "בדיקה",
        "subject": "general",
        "emoji": "📚",
        "blurb_he": "בדיקה",
        "estimated_minutes": 5,
        "group_ids": ["grade3"],
        "nodes": [
            {"type": "learn", "title": "א", "body_he": "א"},
            {"type": "practice", "title": "ב", "body_he": "ב",
             "choices": [{"id": "a", "label": "1"}, {"id": "b", "label": "2"}],
             "correct": "a"},
            {"type": "celebrate", "title": "ג", "body_he": "ג"},
        ],
    }
    path = validate_content_path(data)
    topics = infer_topics(path)
    assert len(topics) >= 2
    covered = {nid for t in topics for nid in t.node_ids}
    assert covered == {n.id for n in path.nodes}


def test_invalid_path_rejected() -> None:
    with pytest.raises(Exception):
        validate_content_path(
            {
                "id": "bad",
                "title_he": "x",
                "subject": "math",
                "emoji": "x",
                "blurb_he": "x",
                "estimated_minutes": 5,
                "nodes": [],
            }
        )


def test_seed_publishes_demo_only(store: PathStore) -> None:
    summary = seed_content_paths(store, content_dir=default_content_dir())
    loaded = load_content_paths(default_content_dir())
    expected = len(loaded)
    grade3 = {p.id for p in loaded if "grade3" in p.group_ids}
    assert expected >= 1
    assert summary["count"] == expected
    cards = list_catalog_cards(store)
    assert len(cards) == expected
    for card in cards:
        doc = store.get_path_latest(card["pathId"])
        assert doc.status == PathStatus.published
        if card["pathId"] in grade3:  # kids demo flag belongs to the grade-3 set
            assert card["kidsDemo"] is True
        raw = doc.model_dump(mode="json")
        assert raw.get("topics")


def test_content_to_path_version_blocks() -> None:
    paths = load_content_paths(default_content_dir())
    sample = next(p for p in paths if p.id == "path_grade3_math_add20")
    doc = content_to_path_version(sample)
    assert len(doc.blocks) == len(sample.nodes)
    assert doc.blocks[0].content.get("nodeType") == "learn"
    raw = doc.model_dump(mode="json")
    assert raw.get("topics")
    assert raw.get("nodeToBlock")


@pytest.fixture
def platform_client(tmp_path):
    store = PathStore(str(tmp_path / "plat.db"))
    app = create_learner_app(store=store, seed=True, seed_content=True)
    with TestClient(app) as c:
        login_with_code(
            c,
            data={
                "first_name": "Test",
                "last_name": "User",
                "email": "fixture@example.com",
                "next": "/",
            },
            follow_redirects=True,
        )
        yield c
    store.close()


def test_catalog_home_lists_grade3(platform_client: TestClient) -> None:
    r = platform_client.get("/")
    assert r.status_code == 200
    assert "MyRoad" in r.text
    assert "דרכים לתלמידי כיתה ג" in r.text
    assert "חיבור עד 20" in r.text
    assert "Colors" in r.text or "צבעים" in r.text
    assert "דו־רה־מי" in r.text or "דו-רה-מי" in r.text
    assert 'class="lang-switch"' not in r.text
    assert 'href="/settings"' in r.text
    settings = platform_client.get("/settings")
    assert settings.status_code == 200
    assert "עברית" in settings.text and "English" in settings.text and "العربية" in settings.text


def test_locale_switch_english_shell(platform_client: TestClient) -> None:
    r = platform_client.post("/locale", data={"locale": "en", "next": "/"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Learning platform" in r.text or "Learning paths" in r.text
    assert "Catalog" in r.text


def test_identity_login_and_whoami(platform_client: TestClient) -> None:
    r = _reg(platform_client, "noa@example.com", "נועה", "כהן")
    assert r.status_code == 200
    assert "נועה" in r.text
    uid = _uid(platform_client)
    assert uid
    assert "@" not in uid
    # Cookies hold an opaque session id, never the user id or email
    assert platform_client.cookies.get("myroad_uid") is None
    sid = platform_client.cookies.get("myroad_session")
    assert sid and uid not in sid and "@" not in sid


def test_play_shows_topic_map_first(platform_client: TestClient) -> None:
    home = platform_client.get("/play/path_grade3_math_add20")
    assert home.status_code == 200
    assert "מפת הדרך" in home.text or "path_map" in home.text.lower() or "topic" in home.text.lower()
    assert "התחל" in home.text or "Start" in home.text


def test_play_math_path_mouse_flow(platform_client: TestClient) -> None:
    _reg(platform_client, "tester@example.com", "Tester", "User")
    # enter learning from map
    start = platform_client.post(
        "/play/path_grade3_math_add20/start",
        data={},
        follow_redirects=True,
    )
    assert start.status_code == 200
    assert "הקראה" in start.text or "Speak" in start.text
    assert "חיבור" in start.text

    # ack learn
    r = platform_client.post("/play/path_grade3_math_add20/ack", follow_redirects=True)
    assert r.status_code == 200

    # wrong then right on first practice
    wrong = platform_client.post(
        "/play/path_grade3_math_add20/answer",
        data={"choice": "a"},
        follow_redirects=True,
    )
    assert wrong.status_code == 200
    assert "נסו שוב" in wrong.text or "לא בדיוק" in wrong.text or "flash" in wrong.text

    right = platform_client.post(
        "/play/path_grade3_math_add20/answer",
        data={"choice": "b"},
        follow_redirects=True,
    )
    assert right.status_code == 200


def test_progress_persists_per_user(platform_client: TestClient) -> None:
    _reg(platform_client, "eli@example.com", "Eli", "User")
    platform_client.post("/play/path_grade3_math_add20/start", data={}, follow_redirects=True)
    platform_client.post("/play/path_grade3_math_add20/ack", follow_redirects=True)
    # reopen path — should resume learn view (progress exists)
    again = platform_client.get("/play/path_grade3_math_add20")
    assert again.status_code == 200
    # catalog shows in progress
    home = platform_client.get("/")
    assert "בתהליך" in home.text or "In progress" in home.text or "Eli" in home.text


def test_completion_stats_and_attempt(platform_client: TestClient, tmp_path) -> None:
    # Use store from app
    store: PathStore = platform_client.app.state.store
    _reg(platform_client, "fin@example.com", "Fin", "User")
    platform_client.post("/play/path_grade3_math_add20/start", data={}, follow_redirects=True)
    # Walk all nodes: learn ack, 2 practices, check, celebrate
    # learn
    platform_client.post("/play/path_grade3_math_add20/ack", follow_redirects=True)
    # practice balloons correct b
    platform_client.post("/play/path_grade3_math_add20/answer", data={"choice": "b"}, follow_redirects=True)
    # practice candy correct c
    platform_client.post("/play/path_grade3_math_add20/answer", data={"choice": "c"}, follow_redirects=True)
    # check correct b
    platform_client.post("/play/path_grade3_math_add20/answer", data={"choice": "b"}, follow_redirects=True)
    # celebrate
    done = platform_client.post("/play/path_grade3_math_add20/ack", follow_redirects=True)
    assert done.status_code == 200
    assert "סיכום" in done.text or "summary" in done.text.lower() or "Path summary" in done.text or "stats" in done.text.lower() or "אחוז" in done.text or "Mastery" in done.text
    assert "חזרה לקטלוג" in done.text or "Back to catalog" in done.text

    uid = _uid(platform_client)
    assert uid
    attempt = store.latest_attempt(uid, "path_grade3_math_add20")
    assert attempt is not None
    assert attempt["nodesCompleted"] >= 5
    assert attempt["masteryPct"] >= 90
    prog = store.get_progress(uid, "path_grade3_math_add20")
    assert prog and prog.get("completedAt")


def test_health_reports_content_count(platform_client: TestClient) -> None:
    h = platform_client.get("/health")
    assert h.json()["contentPaths"] == len(load_content_paths(default_content_dir()))


def test_learner_identity_tables(store: PathStore) -> None:
    user = store.upsert_learner("usr_test1", "דני", locale="he")
    assert user["displayName"] == "דני"
    store.save_progress(
        "usr_test1",
        "path_x",
        version_id="ver_1",
        node_index=2,
        mastered={"a", "b"},
        correct_taps=3,
        incorrect_taps=1,
    )
    prog = store.get_progress("usr_test1", "path_x")
    assert prog is not None
    assert prog["correctTaps"] == 3
    assert "a" in prog["mastered"]
    att = store.record_attempt(
        user_id="usr_test1",
        path_id="path_x",
        version_id="ver_1",
        started_at="2026-01-01T00:00:00+00:00",
        duration_sec=42,
        nodes_completed=2,
        nodes_total=5,
        correct_taps=3,
        incorrect_taps=1,
        mastery_pct=40.0,
        message="ok",
    )
    assert att["attemptId"].startswith("att_")
    assert store.latest_attempt("usr_test1", "path_x")["durationSec"] == 42


def test_home_tabs_and_progress_bookmarks(platform_client: TestClient) -> None:
    """Home primary tabs: in progress / completed / practice; progress survives reload."""
    store: PathStore = platform_client.app.state.store
    _reg(platform_client, "tabuser@example.com", "Tab", "User")

    # Before any play — default tab is catalog (full list)
    home = platform_client.get("/")
    assert home.status_code == 200
    assert "דרכים שעשינו" in home.text or "Paths we started" in home.text
    assert "דרכים שסיימנו" in home.text or "Paths we finished" in home.text
    assert "דרכים לתרגול" in home.text or "Paths to practice" in home.text
    assert "חיבור עד 20" in home.text

    # Start a path → appears under in_progress after reload
    platform_client.post("/play/path_grade3_math_add20/start", data={}, follow_redirects=True)
    platform_client.post("/play/path_grade3_math_add20/ack", follow_redirects=True)

    uid = _uid(platform_client)
    assert uid
    prog = store.get_progress(uid, "path_grade3_math_add20")
    assert prog is not None
    assert prog.get("startedAt")
    assert not prog.get("completedAt")

    tab = platform_client.get("/?tab=in_progress")
    assert tab.status_code == 200
    assert "חיבור עד 20" in tab.text
    assert "בתהליך" in tab.text or "In progress" in tab.text

    # Fresh client cookies still resume via same cookie jar (TestClient persists)
    again = platform_client.get("/play/path_grade3_math_add20")
    assert again.status_code == 200

    # Wrong answers → needs practice tab
    platform_client.post(
        "/play/path_grade3_math_add20/answer",
        data={"choice": "a"},
        follow_redirects=True,
    )
    platform_client.post(
        "/play/path_grade3_math_add20/answer",
        data={"choice": "a"},
        follow_redirects=True,
    )
    practice = platform_client.get("/?tab=practice")
    assert practice.status_code == 200

    # Time view groups by subject
    by_time = platform_client.get("/?view=time")
    assert by_time.status_code == 200
    assert "לאחרונה" in by_time.text or "Recently" in by_time.text
    assert "מתמטיקה" in by_time.text or "Math" in by_time.text


def test_english_play_shows_content_token_and_he_explanation(platform_client: TestClient) -> None:
    _reg(platform_client, "eng@example.com", "Eng", "User")
    r = platform_client.post(
        "/play/path_grade3_english_colors/start",
        data={},
        follow_redirects=True,
    )
    assert r.status_code == 200
    # HE explanation chrome
    assert "צבעים" in r.text or "אנגלית" in r.text
    # Content token separated
    assert "red" in r.text.lower()
    assert "מילת יעד" in r.text or "Target word" in r.text

    # Switch UI to English — explanation switches, token stays
    platform_client.post(
        "/locale",
        data={"locale": "en", "next": "/play/path_grade3_english_colors?view=learn"},
        follow_redirects=True,
    )
    en = platform_client.get("/play/path_grade3_english_colors?view=learn")
    assert en.status_code == 200
    assert "Today we learn" in en.text or "color" in en.text.lower()
    assert "red" in en.text.lower()


def test_completed_tab_after_finish(platform_client: TestClient) -> None:
    _reg(platform_client, "done@example.com", "Done", "User")
    platform_client.post("/play/path_grade3_math_add20/start", data={}, follow_redirects=True)
    platform_client.post("/play/path_grade3_math_add20/ack", follow_redirects=True)
    platform_client.post("/play/path_grade3_math_add20/answer", data={"choice": "b"}, follow_redirects=True)
    platform_client.post("/play/path_grade3_math_add20/answer", data={"choice": "c"}, follow_redirects=True)
    platform_client.post("/play/path_grade3_math_add20/answer", data={"choice": "b"}, follow_redirects=True)
    platform_client.post("/play/path_grade3_math_add20/ack", follow_redirects=True)

    done = platform_client.get("/?tab=completed")
    assert done.status_code == 200
    assert "חיבור עד 20" in done.text
    assert "הושלם" in done.text or "Completed" in done.text


def test_auth_gate_redirects_and_email_only_return(tmp_path) -> None:
    store = PathStore(str(tmp_path / "gate.db"))
    app = create_learner_app(store=store, seed=False, seed_content=False)
    try:
        with TestClient(app) as c:
            assert c.get("/health").status_code == 200
            home = c.get("/", follow_redirects=False)
            assert home.status_code == 303
            assert "/login?next=" in home.headers["location"]
            author = c.get("/author", follow_redirects=False)
            assert author.status_code == 303
            assert "/login?next=" in author.headers["location"]
            settings = c.get("/settings", follow_redirects=False)
            assert settings.status_code == 303
            assert "/login?next=" in settings.headers["location"]
            missing = login_with_code(
                c,
                data={"email": "gate@example.com", "next": "/settings"},
                follow_redirects=False,
            )
            # Unknown email: neutral answer (code page), no account, no session
            assert missing.status_code == 303
            assert missing.headers["location"].startswith("/login/verify")
            assert _uid(c) is None and store.get_learner_by_email("gate@example.com") is None
            created = login_with_code(
                c,
                data={
                    "email": "gate@example.com",
                    "first_name": "Gate",
                    "last_name": "User",
                    "mode": "register",
                    "next": "/settings",
                },
                follow_redirects=False,
            )
            assert created.status_code == 303
            assert created.headers["location"].rstrip("/").endswith("/settings") or created.headers["location"].endswith("/settings")
            uid = _uid(c)
            assert uid and "@" not in uid
            c.cookies.clear()
            again = login_with_code(
                c,
                data={"email": "gate@example.com", "next": "/settings"},
                follow_redirects=True,
            )
            assert again.status_code == 200
            assert _uid(c) == uid
            assert "Gate" in again.text
            assert 'type="password"' not in again.text
            assert 'class="lang-switch"' not in again.text
            home_in = c.get("/")
            assert home_in.status_code == 200
            assert 'class="lang-switch"' not in home_in.text
            assert "<form" not in home_in.text.split("<header", 1)[-1].split("</header>", 1)[0]
    finally:
        store.close()


# ---------- Cyber security review of #46: cookie flags, logout, email change ----------

def _cookie_headers(resp, name: str) -> list[str]:
    return [h for h in resp.headers.get_list("set-cookie") if h.startswith(name + "=")]


def test_session_cookie_is_secure_by_default(tmp_path, monkeypatch) -> None:
    store = PathStore(str(tmp_path / "sec.db"))
    app = create_learner_app(store=store, seed=False, seed_content=False)
    try:
        with TestClient(app) as c:
            _, outbox = request_login_code(
                c, {"first_name": "S", "last_name": "C", "email": "secure@example.com", "next": "/"}
            )  # step 1 with the dev flag so the test client keeps the challenge cookie
            monkeypatch.delenv("MYROAD_DEV_INSECURE_COOKIES", raising=False)
            r = c.post("/login/verify", data={"code": outbox[-1][1], "next": "/"}, follow_redirects=False)
            (cookie,) = _cookie_headers(r, "myroad_session")
            low = cookie.lower()
            assert "secure" in low and "httponly" in low and "samesite=lax" in low
    finally:
        store.close()


def test_dev_flag_drops_secure_for_plain_http(tmp_path) -> None:
    store = PathStore(str(tmp_path / "dev.db"))
    app = create_learner_app(store=store, seed=False, seed_content=False)
    try:
        with TestClient(app) as c:  # conftest sets MYROAD_DEV_INSECURE_COOKIES=1
            r = _reg(c, "dev@example.com")
            assert r.status_code == 200
            assert _uid(c)
    finally:
        store.close()


def test_logout_revokes_the_session(platform_client: TestClient) -> None:
    store = platform_client.app.state.store
    sid = platform_client.cookies.get("myroad_session")
    assert store.get_session_user(sid)
    r = platform_client.post("/logout", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert store.get_session_user(sid) is None
    assert platform_client.cookies.get("myroad_session") is None
    # Replaying the old cookie does not sign in
    platform_client.cookies.set("myroad_session", sid)
    assert platform_client.get("/settings", follow_redirects=False).status_code == 303


def test_email_change_is_refused_until_it_can_be_verified(tmp_path) -> None:
    """Cyber security HIGH: no email change without proof of the new address."""
    store = PathStore(str(tmp_path / "email.db"))
    app = create_learner_app(store=store, seed=False, seed_content=False)
    try:
        with TestClient(app) as c:
            _reg(c, "first@example.com", "Em", "Change")
            uid = _uid(c)
            other_device = store.create_session(uid)
            # Attack 1: a stolen session tries to move the account to the attacker's address
            # Attack 2: Alice points her account at an unregistered newcomer@ address
            for target in ("attacker@example.com", "newcomer@example.com"):
                r = c.post("/settings", data={"first_name": "Em", "last_name": "Change", "email": target},
                           follow_redirects=False)
                assert r.status_code == 303 and "error=email_change_disabled" in r.headers["location"]
                assert store.get_learner(uid)["email"] == "first@example.com"
                assert store.get_learner_by_email(target) is None
            page = c.get("/settings?error=email_change_disabled")
            assert "Changing your sign-in email is not available yet" in page.text or "האימייל לא שונה" in page.text
            # Nobody else's sessions were touched, and the account keeps its email
            assert store.get_session_user(other_device) == uid
            # Saving the name with the same email (any case) still works
            r = c.post("/settings", data={"first_name": "Em2", "last_name": "Change", "email": "First@Example.com"},
                       follow_redirects=False)
            assert "saved=1" in r.headers["location"]
            assert store.get_learner(uid)["firstName"] == "Em2"
            with pytest.raises(ValueError, match="email_change_disabled"):
                store.update_learner_profile(uid, first_name="E", last_name="C", email="x@example.com")
    finally:
        store.close()


# ---------- Origin/Referer check on browser form POSTs ----------

@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Origin": "http://testserver.evil.example"},
        {"Referer": "https://evil.example/page"},
        {},
    ],
)
def test_cross_site_or_originless_form_posts_are_refused(platform_client: TestClient, headers) -> None:
    store = platform_client.app.state.store
    sid = platform_client.cookies.get("myroad_session")
    del platform_client.headers["Origin"]
    for path, data in (("/logout", {}), ("/settings", {"first_name": "X", "last_name": "Y", "email": "z@z.zz"}),
                       ("/locale", {"locale": "en", "next": "/"})):
        r = platform_client.post(path, data=data, headers=headers, follow_redirects=False)
        assert r.status_code == 403, (path, headers)
    assert store.get_session_user(sid)  # logout did not happen


def test_same_origin_form_posts_pass(platform_client: TestClient) -> None:
    del platform_client.headers["Origin"]
    r = platform_client.post("/locale", data={"locale": "en", "next": "/"},
                             headers={"Origin": "http://testserver"}, follow_redirects=False)
    assert r.status_code == 303
    r = platform_client.post("/locale", data={"locale": "he", "next": "/"},
                             headers={"Referer": "http://testserver/settings"}, follow_redirects=False)
    assert r.status_code == 303
    assert platform_client.get("/settings").status_code == 200  # GET needs no Origin


def test_allowed_origins_env_adds_the_public_origin(platform_client: TestClient, monkeypatch) -> None:
    del platform_client.headers["Origin"]
    hdr = {"Origin": "https://myroad.example"}
    assert platform_client.post("/locale", data={"locale": "en"}, headers=hdr,
                                follow_redirects=False).status_code == 403
    monkeypatch.setenv("MYROAD_ALLOWED_ORIGINS", "https://other.example, https://MyRoad.example/")
    assert platform_client.post("/locale", data={"locale": "en"}, headers=hdr,
                                follow_redirects=False).status_code == 303
