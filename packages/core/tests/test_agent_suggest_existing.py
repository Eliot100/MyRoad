"""Builder step 2 offers existing published paths before building a new one (issue #43).

Runs against the real MyRoad-content files (CI clones them into CONTENT_DIR).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from auth_helpers import login_with_code
from fastapi.testclient import TestClient

from myroad_core.agent_builder.suggest import (
    MAX_MATCHES,
    catalog_entries,
    completed_path_ids,
    content_prerequisites,
    goal_terms,
    rank_existing,
)
from myroad_core.content.loader import default_content_dir, load_content_paths, seed_content_paths
from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

ZERO = "path_math_zero_to_equation"
BAGRUT = "path_math_bagrut_3_units"
ADULT_MATH = {ZERO, BAGRUT}


def _content_ids() -> set[str]:
    return {p.id for p in load_content_paths(default_content_dir())}


needs_adult_paths = pytest.mark.skipif(
    not ADULT_MATH <= _content_ids(), reason="MyRoad-content adult math paths not in CONTENT_DIR"
)


@pytest.fixture(scope="module")
def store():
    s = PathStore(":memory:")
    seed_content_paths(s, content_dir=default_content_dir())
    yield s
    s.close()


def _ids(matches: list[dict]) -> list[str]:
    return [m["pathId"] for m in matches]


def test_goal_terms_drop_stop_words_and_keep_numbers() -> None:
    assert goal_terms("I want to learn math from zero") == ["math", "zero"]
    assert goal_terms("אני רוצה ללמוד מתמטיקה מאפס") == ["מתמטיקה", "מאפס"]
    assert goal_terms("Bagrut 3-units!") == ["bagrut", "3", "units"]
    assert goal_terms("") == []


@needs_adult_paths
@pytest.mark.parametrize("locale", ["en", "he", "ar"])
@pytest.mark.parametrize("goal", ["math from zero", "מתמטיקה מאפס"])
def test_math_from_zero_offers_both_adult_math_paths(store, locale: str, goal: str) -> None:
    matches = rank_existing(goal, catalog_entries(store, locale=locale), subject="general")
    assert _ids(matches)[:2] == [ZERO, BAGRUT]
    zero, bagrut = matches[0], matches[1]
    assert zero["reason"]["code"] == "goal_match"
    assert "title" in zero["reason"]["fields"]
    assert zero["prerequisites"] == [] and zero["missing_prerequisites"] == []
    # Bagrut requires the zero path; the learner has not done it yet.
    assert bagrut["missing_prerequisites"] == [ZERO]
    assert bagrut["prerequisites"][0]["available"] is True
    assert bagrut["prerequisites"][0]["title"] == zero["title"]


@needs_adult_paths
@pytest.mark.parametrize("goal", ["bagrut 3 units", "בגרות 3 יחידות", "Math 3 units bagrut prep"])
def test_bagrut_3_units_offers_it_with_its_prerequisite(store, goal: str) -> None:
    matches = rank_existing(goal, catalog_entries(store, locale="en"), subject="general")
    assert _ids(matches)[:2] == [BAGRUT, ZERO]
    assert matches[0]["reason"]["code"] == "goal_match"
    assert matches[0]["missing_prerequisites"] == [ZERO]
    assert matches[1]["reason"]["required_by"] == BAGRUT


@needs_adult_paths
def test_completed_prerequisite_is_not_missing(store) -> None:
    entries = catalog_entries(store, locale="en")
    matches = rank_existing("bagrut 3 units", entries, completed={ZERO})
    assert _ids(matches) == [BAGRUT]
    assert matches[0]["missing_prerequisites"] == []
    assert matches[0]["prerequisites"] == [{"pathId": ZERO, "title": matches[0]["prerequisites"][0]["title"],
                                            "done": True, "available": True}]


@needs_adult_paths
def test_prerequisites_come_from_the_content_files() -> None:
    assert content_prerequisites()[BAGRUT] == [ZERO]
    assert content_prerequisites()[ZERO] == []


def test_unrelated_goal_has_no_matches(store) -> None:
    entries = catalog_entries(store, locale="en")
    assert rank_existing("cooking pasta", entries) == []
    assert rank_existing("3", entries) == [], "a number alone never matches"
    assert rank_existing("", entries) == []


def test_at_most_three_matches_and_deterministic(store) -> None:
    entries = catalog_entries(store, locale="en")
    for goal in ("math", "english animals colors hello", "piano"):
        first = rank_existing(goal, entries)
        assert 0 < len(first) <= MAX_MATCHES
        assert first == rank_existing(goal, entries)
        assert len(set(_ids(first))) == len(first)


def test_subject_and_audience_break_ties(store) -> None:
    entries = catalog_entries(store, locale="en")
    plain = rank_existing("english", entries)
    assert all(m["card"]["subject"] == "english" for m in plain)
    grade3 = rank_existing("math", entries, subject="math", audience="grade3")
    assert grade3[0]["card"]["groupIds"] == ["grade3"]


def test_completed_path_ids_reads_learner_progress(tmp_path: Path) -> None:
    s = PathStore(str(tmp_path / "p.db"))
    s.ensure_learner_schema()
    s.save_progress("u1", "p_done", version_id=None, node_index=3, mastered=[], correct_taps=3,
                    incorrect_taps=0, completed_at="2026-10-01T10:00:00Z")
    s.save_progress("u1", "p_open", version_id=None, node_index=1, mastered=[], correct_taps=1,
                    incorrect_taps=0)
    assert completed_path_ids(s, "u1") == {"p_done"}
    assert completed_path_ids(s, None) == set()
    s.close()


# --- route: step 2 of /add-path, demo mode, no Cloudflare ---


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_GATEWAY_ID", "CLOUDFLARE_AI_GATEWAY_TOKEN",
                 "CLOUDFLARE_AI_GATEWAY_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    def _no_network(*a, **kw):
        raise AssertionError("network must not be used in tests")

    monkeypatch.setattr("myroad_core.ui.cloudflare_gateway.urlopen", _no_network)
    db = tmp_path / "suggest.db"
    s = PathStore(str(db))
    app = create_learner_app(store=s, db_path=str(db), seed=True, seed_content=True)
    with TestClient(app) as client:
        yield client, s
    s.close()


def _login(client: TestClient, locale: str = "en") -> None:
    client.cookies.set("myroad_locale", locale)
    # Two-step email-code sign-in (#41): request the code, then verify it.
    login_with_code(client, {"first_name": "Dana", "last_name": "Cohen", "email": "dana@example.com", "next": "/"})


def _goal(client: TestClient, goal: str, subject: str = "general", **extra: str) -> None:
    data = {"goal": goal, "subject": subject, "ui_locale": "he", "length": "medium", "mode": "demo", **extra}
    r = client.post("/add-path/goal", data=data, follow_redirects=False)
    assert r.headers["location"] == "/add-path/existing"


@needs_adult_paths
def test_route_existing_step_offers_adult_math_paths(app_client) -> None:
    client, _store = app_client
    _login(client)
    _goal(client, "math from zero")
    page = client.get("/add-path/existing")
    assert page.status_code == 200
    ctx = page.context
    matches = ctx["existing_matches"]
    assert [m["pathId"] for m in matches][:2] == [ZERO, BAGRUT]
    assert all(m["reason_text"] for m in matches)
    assert matches[0]["href"] == f"/play/{ZERO}"
    assert matches[1]["missing_prerequisites"] == [ZERO]
    assert "finish first" in matches[1]["prerequisites_text"]
    # The current template shows matches first, as cards that open the path.
    assert [c["pathId"] for c in ctx["existing"]][:2] == [ZERO, BAGRUT]
    assert ctx["existing"][0]["match"]["reason_text"] == matches[0]["reason_text"]
    assert f'href="/play/{ZERO}"' in page.text and f'href="/play/{BAGRUT}"' in page.text
    assert "Existing paths that fit your goal (2)" in ctx["flash_ok"]
    assert "Existing paths that fit your goal" in page.text
    # "Build anyway": the outline step still works and may name a match as prerequisite.
    assert client.post("/add-path/outline", follow_redirects=False).headers["location"] == "/add-path/outline"
    assert client.get("/add-path/outline").status_code == 200


@needs_adult_paths
@pytest.mark.parametrize("locale", ["he", "ar"])
def test_route_reasons_are_localized_and_rtl_safe(app_client, locale: str) -> None:
    client, _store = app_client
    _login(client, locale)
    _goal(client, "בגרות 3 יחידות")
    ctx = client.get("/add-path/existing").context
    matches = ctx["existing_matches"]
    assert [m["pathId"] for m in matches] == [BAGRUT, ZERO]
    assert matches[1]["reason"]["code"] == "required_by"
    for m in matches:
        assert "\u2068" in m["reason_text"] and "\u2069" in m["reason_text"]
    flash = ctx["flash_ok"]
    assert flash.count("\u2068") == flash.count("\u2069")
    assert ("נדרשת לפני" if locale == "he" else "مطلوب قبل") in matches[1]["reason_text"]


@needs_adult_paths
def test_route_completed_prerequisite_is_shown_as_done(app_client) -> None:
    client, store = app_client
    _login(client)
    user = store.get_learner_by_email("dana@example.com")
    store.save_progress(user["userId"], ZERO, version_id=None, node_index=0, mastered=[], correct_taps=5,
                        incorrect_taps=0, completed_at="2026-10-01T10:00:00Z")
    _goal(client, "bagrut 3 units")
    matches = client.get("/add-path/existing").context["existing_matches"]
    assert [m["pathId"] for m in matches] == [BAGRUT]
    assert matches[0]["missing_prerequisites"] == []
    assert matches[0]["prerequisites_text"] == "you already finished what it requires"


def test_route_no_match_keeps_same_subject_cards(app_client) -> None:
    client, _store = app_client
    _login(client)
    _goal(client, "cooking pasta", subject="piano")
    page = client.get("/add-path/existing")
    ctx = page.context
    assert ctx["existing_matches"] == []
    assert ctx["flash_ok"] == ""
    assert ctx["existing"] and all(c["subject"] == "piano" for c in ctx["existing"])
