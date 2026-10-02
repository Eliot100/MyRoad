"""Catalog chrome follows UI locale (titles/blurbs)."""

from __future__ import annotations

import pytest

from myroad_core.content.loader import default_content_dir, list_catalog_cards, load_content_paths, seed_content_paths
from myroad_core.content.locale_rules import validate_catalog_chrome
from myroad_core.store import PathStore

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient

from myroad_core.ui.app import create_learner_app


def test_all_grade3_paths_have_en_catalog_chrome() -> None:
    paths = load_content_paths(default_content_dir())
    assert len(paths) == 10
    for p in paths:
        assert p.title_en and p.title_en.strip(), f"{p.id} missing title_en"
        assert p.blurb_en and p.blurb_en.strip(), f"{p.id} missing blurb_en"
        assert any(ch.isascii() and ch.isalpha() for ch in p.title_en), p.id
        errs = validate_catalog_chrome(p, require_en=True)
        assert errs == [], errs


def test_list_catalog_cards_follow_ui_locale(store: PathStore) -> None:
    seed_content_paths(store, content_dir=default_content_dir())
    he_cards = {c["pathId"]: c for c in list_catalog_cards(store, locale="he")}
    en_cards = {c["pathId"]: c for c in list_catalog_cards(store, locale="en")}
    assert len(he_cards) == len(en_cards) == 10
    for pid, card in he_cards.items():
        if card["subject"] in {"math", "physics", "piano"}:
            assert any("\u0590" <= ch <= "\u05FF" for ch in card["title"]), pid
            assert card["title"] == card.get("titleHe") or card["title"]
        if card["subject"] == "english":
            assert card["title"] == card.get("titleHe") or card["title"]
    for pid, card in en_cards.items():
        assert card["titleEn"], pid
        assert card["title"] == card["titleEn"], pid
        assert card["blurb"] == card["blurbEn"], pid
        assert card["subjectLabel"] in {"Math", "English", "Physics", "Piano", "General"}


@pytest.fixture
def platform_client(tmp_path):
    store = PathStore(str(tmp_path / "plat.db"))
    app = create_learner_app(store=store, seed=True, seed_content=True)
    with TestClient(app) as c:
        yield c
    store.close()


def test_catalog_home_en_shows_english_path_titles(platform_client: TestClient) -> None:
    r = platform_client.post("/locale", data={"locale": "en", "next": "/?tab=catalog"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Addition up to 20" in r.text
    assert "Light and shadow" in r.text
    assert "Do-Re-Mi" in r.text
    assert "Hand rhythm" in r.text
    assert "Multiplication as repeated addition" in r.text
    assert "Force and push" in r.text
    assert "חיבור עד 20" not in r.text
    assert "אור וצל" not in r.text
    assert "Paths for Grade 3" in r.text


def test_catalog_home_he_keeps_hebrew_native_titles(platform_client: TestClient) -> None:
    r = platform_client.get("/?tab=catalog")
    assert r.status_code == 200
    assert "חיבור עד 20" in r.text
    assert "אור וצל" in r.text
    assert "Addition up to 20" not in r.text
