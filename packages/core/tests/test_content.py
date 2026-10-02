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

from myroad_core.ui.app import create_learner_app


def test_all_grade3_paths_validate() -> None:
    paths = load_content_paths(default_content_dir())
    assert len(paths) == 10
    ids = {p.id for p in paths}
    assert len(ids) == 10
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
    assert summary["count"] == 10
    cards = list_catalog_cards(store)
    assert len(cards) == 10
    for card in cards:
        doc = store.get_path_latest(card["pathId"])
        assert doc.status == PathStatus.published
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
    assert "פלטפורמת למידה" in r.text
    assert "HE" in r.text and "EN" in r.text and "AR" in r.text


def test_locale_switch_english_shell(platform_client: TestClient) -> None:
    r = platform_client.post("/locale", data={"locale": "en", "next": "/"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Learning platform" in r.text or "Learning paths" in r.text
    assert "Catalog" in r.text


def test_identity_login_and_whoami(platform_client: TestClient) -> None:
    r = platform_client.post(
        "/login",
        data={"display_name": "נועה", "next": "/"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "נועה" in r.text
    assert platform_client.cookies.get("myroad_uid")


def test_play_shows_topic_map_first(platform_client: TestClient) -> None:
    home = platform_client.get("/play/path_grade3_math_add20")
    assert home.status_code == 200
    assert "מפת הדרך" in home.text or "path_map" in home.text.lower() or "topic" in home.text.lower()
    assert "התחל" in home.text or "Start" in home.text


def test_play_math_path_mouse_flow(platform_client: TestClient) -> None:
    platform_client.post("/login", data={"display_name": "Tester", "next": "/"})
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
    platform_client.post("/login", data={"display_name": "Eli", "next": "/"})
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
    platform_client.post("/login", data={"display_name": "Fin", "next": "/"})
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

    uid = platform_client.cookies.get("myroad_uid")
    assert uid
    attempt = store.latest_attempt(uid, "path_grade3_math_add20")
    assert attempt is not None
    assert attempt["nodesCompleted"] >= 5
    assert attempt["masteryPct"] >= 90
    prog = store.get_progress(uid, "path_grade3_math_add20")
    assert prog and prog.get("completedAt")


def test_health_reports_content_count(platform_client: TestClient) -> None:
    h = platform_client.get("/health")
    assert h.json()["contentPaths"] == 10


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
