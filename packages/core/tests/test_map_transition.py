"""View transition between the path map and the step player (#58).

Pure CSS cross-document View Transitions, scoped to map/play, with no motion under
prefers-reduced-motion and a logical (RTL-aware) slide direction. htmx swaps (#65) and the
scroll-to-current station (#68) are untouched; no focus handling is added.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

_UI = Path(__file__).resolve().parents[1] / "src" / "myroad_core" / "ui"
CSS = (_UI / "static" / "transitions.css").read_text(encoding="utf-8")
LINK = '<link rel="stylesheet" href="/static/transitions.css" />'
PID = "path_test_vt"


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _doc() -> dict:
    return {"id": PID, "subject": "math", "group_ids": ["adult"], "emoji": "🎞️", "estimated_minutes": 5,
            "titles": {"he": "מעבר", "en": "Transition", "ar": "انتقال"},
            "blurbs": {"he": "בדיקה.", "en": "Test.", "ar": "اختبار."},
            "topics": [{"id": "t1", "titles": {"he": "א", "en": "A", "ar": "أ"}, "node_ids": ["n1", "n2"]}],
            "nodes": [{"id": "n1", "type": "learn", "title": "הסבר", "body_he": "הסבר"},
                      {"id": "n2", "type": "practice", "title": "שאלה", "body_he": "1+1?",
                       "choices": [{"id": "a", "label": "2"}, {"id": "b", "label": "3"}], "correct": "a"}]}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_doc(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "vt.db"))
    c = TestClient(create_learner_app(store=store, seed=False, seed_content=True))
    c.post("/login", data={"first_name": "V", "last_name": "T", "email": "vt@example.com", "next": "/"})
    yield c
    store.close()


def test_everything_is_inside_the_no_preference_query() -> None:
    css = _strip_comments(CSS).strip()
    assert css.startswith("@media (prefers-reduced-motion: no-preference) {") and css.endswith("}")
    # Exactly one top-level block: nothing animates (or opts in) under reduced motion.
    depth, top = 0, 0
    for ch in css:
        if ch == "{":
            top += depth == 0
            depth += 1
        elif ch == "}":
            depth -= 1
    assert depth == 0 and top == 1
    assert "@view-transition { navigation: auto; }" in css
    assert "prefers-reduced-motion: reduce" not in css


def test_names_and_direction_are_logical() -> None:
    css = _strip_comments(CSS)
    for rule in ('.path-head { view-transition-name: vt-path-head; }',
                 '.map-view .map-card { view-transition-name: vt-map; }',
                 'body.play:not(.map-view) #step-card { view-transition-name: vt-step; }'):
        assert rule in css
    assert ":root { --vt-shift: 28px;" in css and ':root[dir="rtl"] { --vt-shift: -28px; }' in css
    # Map ↔ step slides only when the other side is absent (:only-child); step → step cross-fades.
    for sel in ("::view-transition-old(vt-map):only-child", "::view-transition-new(vt-step):only-child",
                "::view-transition-old(vt-step):only-child", "::view-transition-new(vt-map):only-child"):
        assert sel in css
    assert "translateX(var(--vt-shift))" in css and "translateX(calc(-1 * var(--vt-shift)))" in css
    assert not re.search(r"\b(left|right)\s*:", css)  # no physical offsets
    assert "220ms" in css


@pytest.mark.parametrize("locale", ["he", "en", "ar"])
def test_linked_on_map_and_play_only(client, locale) -> None:
    client.cookies.set("myroad_locale", locale)
    client.post(f"/play/{PID}/start")
    map_html = client.get(f"/play/{PID}?view=map").text
    play_html = client.get(f"/play/{PID}?view=learn").text
    assert LINK in map_html and LINK in play_html
    assert '<section class="card map-card">' in map_html
    assert re.search(r'<body class="[^"]*\bplay map-view\b', map_html)
    assert not re.search(r'<body class="[^"]*\bmap-view\b', play_html)
    assert 'id="step-card"' in play_html and 'class="card path-head"' in play_html
    assert LINK not in client.get("/").text
    stats = client.get(f"/play/{PID}?view=stats")
    if stats.status_code == 200:
        assert LINK not in stats.text
    assert f'dir="{"ltr" if locale == "en" else "rtl"}"' in map_html[:200]


def test_htmx_partials_and_focus_are_untouched(client) -> None:
    client.post(f"/play/{PID}/start")
    client.post(f"/play/{PID}/ack")
    part = client.post(f"/play/{PID}/answer", data={"choice": "b"}, headers={"HX-Request": "true"})
    assert part.status_code == 200 and "<html" not in part.text and "transitions.css" not in part.text
    assert 'id="step-card"' in part.text
    css = _strip_comments(CSS)
    assert "focus" not in css and "pointer-events" not in css and "inert" not in css
    js = (_UI / "static" / "platform.js").read_text(encoding="utf-8")
    assert "startViewTransition" not in js  # htmx swaps are not navigations; no JS involvement
