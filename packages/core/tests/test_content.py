"""Content schema validation + catalog/player smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from myroad_core.content.loader import (
    content_to_path_version,
    default_content_dir,
    list_catalog_cards,
    load_content_paths,
    seed_content_paths,
)
from myroad_core.content.schema import ContentPath, validate_content_path
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
        assert 5 <= p.estimated_minutes <= 12
        assert len(p.nodes) >= 3


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


def test_content_to_path_version_blocks() -> None:
    paths = load_content_paths(default_content_dir())
    sample = next(p for p in paths if p.id == "path_grade3_math_add20")
    doc = content_to_path_version(sample)
    assert isinstance(doc, type(doc))
    assert len(doc.blocks) == len(sample.nodes)
    assert doc.blocks[0].content.get("nodeType") == "learn"


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
    # Platform shell is general — not a global kids rebrand
    assert "פלטפורמת למידה" in r.text


def test_play_math_path_mouse_flow(platform_client: TestClient) -> None:
    home = platform_client.get("/play/path_grade3_math_add20")
    assert home.status_code == 200
    assert "חיבור" in home.text
    assert "הקראה" in home.text

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


def test_health_reports_content_count(platform_client: TestClient) -> None:
    h = platform_client.get("/health")
    assert h.json()["contentPaths"] == 10
