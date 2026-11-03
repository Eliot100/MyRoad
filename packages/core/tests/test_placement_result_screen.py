"""Placement result in the first step of the recommended road (#212, #200, decision 0013)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code
from test_english_bagrut_flow import _mini

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app
from myroad_core.ui.placement_result_view import placement_result_view

PLACE = "path_english_bagrut5_00_placement"
ZERO = "path_english_bagrut5_01_zero"
ROAD_URL = f"/play/{ZERO}?view=learn&from=placement"
DASHES = re.compile("[\u002d\u2010-\u2015\u2212]")
KEYS = ["pr_title", "pr_overall", "pr_domain_a11y", "pr_gap_title", "pr_start", "pr_map"] + [f"pr_level_{i}" for i in range(1, 6)]
LOCALES = Path(__file__).resolve().parents[1] / "locales"


def _many():
    return {
        "domains": [
            {"id": "t0", "level": 4, "score": 72, "items": 4},
            {"id": "t1", "level": 2, "score": 31, "items": 4},
            {"id": "t2", "level": 3, "score": 55, "items": 3},
        ],
        "overall": 54,
        "weights": {"t0": 0.21, "t1": 0.53, "t2": 0.26},
    }


# --- view helper: missing, partial, 0, 1, many -------------------------------------------

@pytest.mark.parametrize("detail", [None, {}, {"domains": []}, {"domains": None, "overall": 50}, "x"])
def test_missing_or_empty_domains_fall_back(detail):
    assert placement_result_view(detail) is None


def test_partial_rows_are_skipped_and_clamped():
    v = placement_result_view({"domains": [{"id": "a", "score": 140}, {"level": 3, "score": 2}, {"id": "b"},
                                           {"id": "c", "score": -5, "level": 9}]})
    assert [(d["id"], d["level"], d["score"]) for d in v["domains"]] == [("a", 5, 100), ("c", 5, 0)]
    assert v["overall"] is None
    assert [g["id"] for g in v["gaps"]] == ["c"]  # no weights: lower score first


def test_one_domain_names_no_gap():
    v = placement_result_view({"domains": [{"id": "t0", "level": 2, "score": 30}], "overall": 30, "weights": {"t0": 1}})
    assert len(v["domains"]) == 1 and v["gaps"] == [] and v["overall"] == 30


def test_many_domains_gap_follows_weights_highest_first():
    v = placement_result_view(_many(), {"t0": "Grammar", "t1": "Listening"})
    assert [g["id"] for g in v["gaps"]] == ["t1"]
    assert v["domains"][0]["label"] == "Grammar" and v["domains"][2]["label"] == "t2"


def test_even_weights_name_no_gap():
    d = {"domains": [{"id": "a", "score": 50}, {"id": "b", "score": 50}], "weights": {"a": 0.5, "b": 0.5}}
    assert placement_result_view(d)["gaps"] == []


# --- copy -----------------------------------------------------------------------------------

@pytest.mark.parametrize("loc", ["he", "en", "ar"])
def test_copy_exists_and_has_no_dashes(loc):
    pack = json.loads((LOCALES / f"{loc}.json").read_text(encoding="utf-8"))
    for k in KEYS:
        assert pack.get(k), (loc, k)
        assert not DASHES.search(pack[k]), (loc, k, pack[k])


# --- rendered in the road's first step ------------------------------------------------------

@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_mini(PLACE, "מבדק רמה", []), _mini(ZERO, "מאפס", [PLACE])):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "p.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    c = TestClient(app)
    login_with_code(c, {"first_name": "Eli", "last_name": "R", "email": "p212@example.com", "next": "/"})
    uid = store.get_session_user(c.cookies.get("myroad_session"))
    yield c, store, uid
    store.close()


def _visible_text(html: str) -> str:
    m = re.search(r'<section class="placement-result".*?</section>', html, re.S)
    assert m, "placement result missing"
    return re.sub(r"<[^>]+>", " ", m.group(0))


@pytest.mark.parametrize("loc,title,start", [("he", "התוצאה שלך במבדק", "ממשיכים לשלב הראשון"),
                                             ("en", "Your placement result", "Start practising"),
                                             ("ar", "نتيجتك في الاختبار", "ابدأ التدريب")])
def test_result_renders_in_first_step_per_locale(env, loc, title, start):
    c, store, uid = env
    store.save_placement_detail(uid, PLACE, _many())
    c.cookies.set("myroad_locale", loc)
    html = c.get(ROAD_URL).text
    sec = _visible_text(html)
    assert title in sec and start in sec
    assert 'id="step-card"' in html  # no interstitial: the step is on the same page
    assert html.count('class="primary big"') >= 1
    assert sec.count("<bdi>") == 0  # tags stripped; numbers checked below
    assert "<bdi>54</bdi>" in html
    assert not DASHES.search(" ".join(sec.split()).replace("100", ""))


def test_domains_levels_and_gap_order(env):
    c, store, uid = env
    store.save_placement_detail(uid, PLACE, _many())
    c.cookies.set("myroad_locale", "he")
    html = c.get(ROAD_URL).text
    assert html.count("<li class=\"pr-domain") == 3
    assert "רמה טוב, ציון 72 מתוך 100" in html  # screen reader: domain + level + score
    gap = re.search(r'<ol class="pr-gap-list">(.*?)</ol>', html, re.S).group(1)
    assert gap.count("<li") == 1
    assert 'data-ev="placement_result_start"' in html and 'href="/play/' + ZERO + '?view=learn#step-card"' in html


def test_no_detail_keeps_plain_hint(env):
    c, _, _ = env
    html = c.get(ROAD_URL).text
    assert 'id="placement-hint"' in html and "placement-result" not in html


def test_not_from_placement_shows_nothing(env):
    c, store, uid = env
    store.save_placement_detail(uid, PLACE, _many())
    html = c.get(f"/play/{ZERO}?view=learn").text
    assert "placement-result" not in html and "placement-hint" not in html
