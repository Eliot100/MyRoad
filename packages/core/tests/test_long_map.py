"""Long path map (issue #57): jump to the current station, narrow phones, review stations distinct.

Builds on the compact station list from #44/#55. Checks: the current station is the jump
target (id="here", aria-current="step"), map links carry #here so the jump works without JS,
the script respects reduced motion, narrow containers shrink each station to number + title,
and review stations differ by shape and icon, not only by color.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

_CORE = Path(__file__).resolve().parents[1]
_STATIC = _CORE / "src" / "myroad_core" / "ui" / "static"
LONG = "path_test_map_long"
SHORT = "path_test_map_short"
LOCKED = "path_test_map_locked"
N = 20  # stations; every 4th (index 3, 7, ...) is a review station


def _long() -> dict:
    topics, nodes, regular = [], [], []
    for i in range(N):
        tid = f"s{i:02d}"
        if i % 4 == 3:
            nid = f"r{i:02d}"
            topics.append({"id": tid, "titles": {"he": f"חזרה {i}", "en": f"Review {i}", "ar": f"مراجعة {i}"},
                           "emoji": "🔁", "node_ids": [nid]})
            nodes.append({"id": nid, "type": "practice", "kind": "review", "review_topic_ids": regular[-2:],
                          "title": f"חזרה {i}", "body_he": "כמה זה 2+2?",
                          "choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "5"}], "correct": "a"})
            continue
        topics.append({"id": tid, "titles": {"he": f"תחנה {i}", "en": f"Station {i}", "ar": f"محطة {i}"},
                       "node_ids": [f"l{i:02d}"]})
        nodes.append({"id": f"l{i:02d}", "type": "learn", "title": f"הסבר {i}", "body_he": "הסבר"})
        regular.append(tid)
    return {"id": LONG, "subject": "math", "group_ids": ["adult"], "emoji": "🧭", "estimated_minutes": 200,
            "titles": {"he": "מפה ארוכה", "en": "Long map", "ar": "خريطة طويلة"},
            "blurbs": {"he": "בדיקה.", "en": "Test.", "ar": "اختبار."}, "topics": topics, "nodes": nodes}


def _short() -> dict:
    return {"id": SHORT, "subject": "math", "group_ids": ["adult"], "emoji": "🧩", "estimated_minutes": 20,
            "titles": {"he": "מפה קצרה", "en": "Short map", "ar": "خريطة قصيرة"},
            "blurbs": {"he": "קצר.", "en": "Short.", "ar": "قصير."},
            "topics": [{"id": "a", "titles": {"he": "א", "en": "A"}, "node_ids": ["x1"]},
                       {"id": "b", "titles": {"he": "ב", "en": "B"}, "node_ids": ["x2"]}],
            "nodes": [{"id": "x1", "type": "learn", "title": "הסבר", "body_he": "הסבר"},
                      {"id": "x2", "type": "learn", "title": "עוד", "body_he": "עוד"}]}


def _locked() -> dict:
    doc = _long()
    doc.update(id=LOCKED, prerequisite_path_ids=[SHORT],
               titles={"he": "נעולה", "en": "Locked", "ar": "مقفل"})
    return doc


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_long(), _short(), _locked()):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "map.db"))
    application = create_learner_app(store=store, seed=False, seed_content=True)
    yield application
    store.close()


def _client(app, locale: str = "he") -> TestClient:
    c = TestClient(app)
    c.cookies.set("myroad_locale", locale)
    login_with_code(c, {"first_name": "Map", "last_name": "User", "email": f"map-{locale}@example.com", "next": "/"})
    c.cookies.set("myroad_locale", locale)
    return c


def _go_to_station(c: TestClient, n: int) -> None:
    """Ack learn steps / answer reviews until station ``n`` (1-based) is current."""
    c.post(f"/play/{LONG}/start")
    for i in range(n - 1):
        if i % 4 == 3:
            c.post(f"/play/{LONG}/answer", data={"choice": "a"})
        else:
            c.post(f"/play/{LONG}/ack")


def _station(html: str, tid: str) -> str:
    start = html.rfind('<li class="station', 0, html.find(f'data-topic-id="{tid}"'))
    return html[start:html.find("</li>", html.find(f'data-topic-id="{tid}"'))]


@pytest.mark.parametrize("locale", ["he", "en", "ar"])
def test_current_station_is_the_jump_target_with_aria_current(app, locale) -> None:
    c = _client(app, locale)
    _go_to_station(c, 15)
    html = c.get(f"/play/{LONG}?view=map").text
    assert html.count('aria-current="step"') == 1 and html.count('id="here"') == 1
    here = _station(html, "s14")
    head = here.split(">", 1)[0]
    assert 'class="station current' in head and 'id="here"' in head and 'aria-current="step"' in head
    assert "<details open" in here and "here-badge" in here
    # Done and upcoming stations are not marked.
    assert 'aria-current' not in _station(html, "s13") and 'aria-current' not in _station(html, "s15")
    # A jump link that works without JS, with an accessible name in the UI language.
    jump = re.search(r'<a class="station-pill current jump-here" href="#here">(.*?)</a>', html).group(1)
    expected = {"he": "מעבר לתחנה הנוכחית", "en": "go to your current station", "ar": "الانتقال إلى محطتك الحالية"}
    assert f'<span class="visually-hidden"> · {expected[locale]}</span>' in jump
    assert f'dir="{"ltr" if locale == "en" else "rtl"}"' in html[:200]


def test_map_links_carry_the_fragment_and_load_the_jump_script(app) -> None:
    c = _client(app)
    _go_to_station(c, 3)
    play = c.get(f"/play/{LONG}?view=learn").text
    assert f'href="/play/{LONG}?view=map#here" class="back"' in play
    html = c.get(f"/play/{LONG}?view=map").text
    assert '<script src="/static/platform.js" defer></script>' in html
    stats = (_CORE / "src" / "myroad_core" / "ui" / "templates" / "stats.html").read_text(encoding="utf-8")
    assert "?view=map#here" in stats


def test_jump_script_respects_reduced_motion_and_restored_scroll() -> None:
    js = (_STATIC / "platform.js").read_text(encoding="utf-8")
    fn = js[js.index("function jumpToCurrentStation"):]
    fn = fn[:fn.index("\n  }\n") + 4]
    assert 'getElementById("here")' in fn
    assert "prefers-reduced-motion: reduce" in fn and 'behavior: reduce ? "auto" : "smooth"' in fn
    assert "window.location.hash" in fn and "back_forward" in fn
    assert "fits" in fn  # no movement when the station is already on screen
    assert ".focus(" not in fn  # scroll only: screen reader users keep their reading position


def test_read_only_map_has_no_current_marker(app) -> None:
    c = _client(app)
    html = c.get(f"/play/{LOCKED}?view=map").text
    assert "lock-banner" in html and "station-list" in html
    assert 'aria-current' not in html and 'id="here"' not in html and "jump-here" not in html


def test_short_map_marks_the_current_station_too(app) -> None:
    c = _client(app)
    c.post(f"/play/{SHORT}/start")
    c.post(f"/play/{SHORT}/ack")
    html = c.get(f"/play/{SHORT}?view=map").text
    assert "topic-diagram" in html and html.count('aria-current="step"') == 1
    current = re.search(r'<div class="topic-station[^"]*"[^>]*data-topic-id="b"[^>]*>', html).group(0)
    assert "current" in current and 'id="here"' in current and 'aria-current="step"' in current


def test_review_stations_differ_by_shape_and_icon(app) -> None:
    c = _client(app)
    html = c.get(f"/play/{LONG}?view=map").text
    review = _station(html, "s03")
    assert review.split(">", 1)[0].split('"')[1].split()[-1] == "review"
    assert '<span class="review-icon" aria-hidden="true">🔁</span>' in review and "review-badge" in review
    assert "review-icon" not in _station(html, "s02")
    css = (_STATIC / "platform.css").read_text(encoding="utf-8")
    assert re.search(r"\.station-num \{[^}]*border-radius: 50%", css)
    assert re.search(r"\.station\.review \.station-num \{[^}]*border-radius: 5px", css)
    assert re.search(r"\.station\.review > details \{[^}]*border-inline-start-style: dashed", css)


def test_narrow_containers_shrink_stations_to_number_and_title() -> None:
    css = (_STATIC / "platform.css").read_text(encoding="utf-8")
    assert re.search(r"\.station-list \{[^}]*container-type: inline-size;[^}]*container-name: stations", css)
    block = css[css.index("@container stations (max-width: 22rem)"):]
    block = block[:block.index("\n}\n")]
    assert re.search(r"\.station summary \{[^}]*grid-template-columns: 1\.7rem minmax\(0, 1fr\)", block)
    assert re.search(r"\.station summary \.mini-bar \{ display: none; \}", block)
    # The step count is hidden visually but stays readable for screen readers.
    count = re.search(r"\.station-meta \.station-count \{([^}]*)\}", block).group(1)
    assert "clip-path: inset(50%)" in count and "display: none" not in count


def test_map_targets_focus_and_motion_rules() -> None:
    css = (_STATIC / "platform.css").read_text(encoding="utf-8")
    sect = css[css.index("/* --- Long map (#57)"):]
    assert ".map-view .station summary { min-block-size: 44px; }" in sect
    assert re.search(r"\.map-view \.jump-here \{[^}]*min-block-size: 24px", sect)
    assert re.search(r"\.map-view \.station summary:focus-visible \{[^}]*outline: 3px solid", sect)
    assert "scroll-margin-block-start" in sect
    assert "@media (prefers-reduced-motion: reduce)" in sect
    assert not re.search(r"(border|padding|margin)-(left|right)\b|[^-]\b(left|right):", sect)


def test_jump_locale_key_in_he_en_ar() -> None:
    for code in ("he", "en", "ar"):
        data = json.loads((_CORE / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        assert data.get("map_jump_here", "").strip(), code
