"""Road style setting (timeline | journey) in Settings, persisted in localStorage."""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

_CORE = Path(__file__).resolve().parents[1]
_UI = _CORE / "src" / "myroad_core" / "ui"
LABELS = {
    "he": ("סגנון הדרך", "ציר זמן", "דרך מפותלת", "איך מוצג הנתיב"),
    "en": ("Road style", "Timeline", "Winding road", "How the path is shown"),
    "ar": ("أسلوب الطريق", "خط زمني", "طريق متعرّج", "كيف يُعرض المسار"),
}


@pytest.fixture
def app(tmp_path):
    store = PathStore(str(tmp_path / "rs.db"))
    yield create_learner_app(store=store, seed=True, seed_content=True)
    store.close()


def test_locale_keys_in_all_three() -> None:
    for code, (h, timeline, journey, legend) in LABELS.items():
        j = json.loads((_CORE / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        assert j["road_style_h"] == h and j["road_style_timeline"] == timeline
        assert j["road_style_journey"] == journey and j["road_style_legend"] == legend
        for k in ("road_style_timeline_note", "road_style_journey_note", "jy_lede",
                  "road_orientation_legend", "road_orientation_vertical",
                  "road_orientation_horizontal", "road_orientation_vertical_note",
                  "road_orientation_horizontal_note"):
            assert j[k] and "—" not in j[k] and "–" not in j[k]


@pytest.mark.parametrize("locale", list(LABELS))
def test_settings_has_the_road_style_control(app, locale) -> None:
    with TestClient(app) as c:
        login(c, f"rs-{locale}@example.com", first_name="T", last_name="H")
        c.cookies.set("myroad_locale", locale)
        h, timeline, journey, legend = LABELS[locale]
        page = c.get("/settings").text
        sec = page[page.index('class="settings-road-style"'):]
        assert f'<h2 id="settings-road-style">{h}</h2>' in sec
        assert 'name="road_style" value="timeline"' in sec
        assert 'name="road_style" value="journey"' in sec
        assert timeline in sec and journey in sec and legend in sec
        assert 'localStorage.setItem("myroad.roadStyle"' in sec
        assert 'name="road_orientation" value="vertical"' in sec
        assert 'name="road_orientation" value="horizontal"' in sec
        assert 'localStorage.setItem("myroad.roadOrientation"' in sec


def test_prefs_bootstrap_and_css_toggle() -> None:
    js = (_UI / "static" / "prefs.js").read_text(encoding="utf-8")
    assert 'localStorage.getItem("myroad.roadStyle")' in js
    assert 'setAttribute("data-road-style"' in js
    assert 'window.myroadRoadStyle' in js
    css = (_UI / "static" / "road-journey.css").read_text(encoding="utf-8")
    assert 'html:not([data-road-style="journey"]) [data-road-style-panel="journey"]' in css
    assert 'html[data-road-style="journey"] [data-road-style-panel="timeline"]' in css
    # Light and dark field / stone tokens both exist.
    assert "--jy-field-0:" in css and "--jy-stone:" in css
    dark_at = css.index(':root[data-theme="dark"] .road-jy')
    assert "--jy-field-0:" in css[dark_at:dark_at + 500]
    assert "--jy-stone:" in css[dark_at:dark_at + 500]
    # Orientation is persisted and only applied on wide screens.
    js = (_UI / "static" / "prefs.js").read_text(encoding="utf-8")
    assert 'localStorage.getItem("myroad.roadOrientation")' in js
    assert 'setAttribute("data-road-orientation"' in js
    assert 'window.myroadRoadOrientation' in js
    assert "@media (min-width: 1024px)" in css
    assert 'html[data-road-orientation="horizontal"]' in css


def test_map_page_includes_both_styles_and_defaults_to_timeline(app) -> None:
    with TestClient(app) as c:
        login(c, "rs-map@example.com", first_name="T", last_name="H")
        # Seeded content has at least one playable road. Use the short English placement or first path.
        home = c.get("/").text
        # Fall back: list roads.
        roads = c.get("/roads").text
        m = re.search(r'href="/play/([^"?]+)', roads) or re.search(r'href="/road/([^"?]+)', roads)
        assert m, "no road link on /roads"
        pid = m.group(1)
        html = c.get(f"/play/{pid}?view=map").text
        assert 'data-road-style-panel="timeline"' in html
        assert 'data-road-style-panel="journey"' in html
        assert 'class="card road-tl' in html
        assert 'class="card road-jy' in html
        assert 'id="journey-track"' in html
        assert "jy-stone" in html and "jy-field" in html
        assert 'name="jy_orientation" value="horizontal"' in html
        assert 'id="track"' in html
        assert "/static/road-journey.css" in html and "/static/road-journey.js" in html
        # Default (no JS): both are in the DOM; CSS without data-road-style=journey hides journey.
        assert 'html:not([data-road-style="journey"])' in (_UI / "static" / "road-journey.css").read_text()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_switching_persists_and_renders_the_chosen_style(app) -> None:
    """Settings radios write myroad.roadStyle; the map page then shows that style."""
    sync_api = pytest.importorskip("playwright.sync_api")
    uvicorn = pytest.importorskip("uvicorn")
    codes: list[str] = []
    app.state.login_code_sender = lambda email, code: codes.append(code)
    app.state.login_notice_sender = lambda email: None
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        with sync_api.sync_playwright() as p:
            chrome = os.environ.get("MYROAD_CHROME", "/usr/bin/google-chrome")
            try:
                br = p.chromium.launch(executable_path=chrome if Path(chrome).exists() else None,
                                       args=["--no-sandbox"])
            except Exception as exc:
                pytest.skip(f"no headless browser: {exc}")
            ctx = br.new_context(locale="he-IL", viewport={"width": 375, "height": 812})
            pg = ctx.new_page()
            pg.request.post(base + "/login", headers={"Origin": base}, form={
                "mode": "register", "first_name": "Noa", "last_name": "Levi",
                "email": "rs-pw@example.com", "next": "/"})
            assert codes, "no login code"
            pg.request.post(base + "/login/verify", headers={"Origin": base},
                            form={"code": codes[-1], "next": "/"})
            # Find a road to open.
            pg.goto(base + "/roads")
            href = pg.locator('a[href^="/play/"]').first.get_attribute("href")
            if not href:
                href = pg.locator('a[href^="/road/"]').first.get_attribute("href")
            assert href
            play = href if "view=map" in href else (href.split("?")[0] + "?view=map")
            # Default is the timeline.
            pg.goto(base + play)
            pg.wait_for_load_state()
            assert pg.evaluate("document.documentElement.getAttribute('data-road-style')") == "timeline"
            assert pg.locator(".road-tl").first.is_visible()
            assert not pg.locator(".road-jy").first.is_visible()
            # Switch in Settings.
            pg.goto(base + "/settings")
            pg.locator('input[name="road_style"][value="journey"]').click()
            assert pg.evaluate("localStorage.getItem('myroad.roadStyle')") == "journey"
            assert "נשמרו" in (pg.locator("#road-style-saved").inner_text() or "")
            # Reload settings: the radio stays on journey.
            pg.reload()
            assert pg.locator('input[name="road_style"][value="journey"]').is_checked()
            # The map now shows the journey style, not the timeline.
            pg.goto(base + play)
            pg.wait_for_load_state()
            assert pg.evaluate("document.documentElement.getAttribute('data-road-style')") == "journey"
            assert pg.locator(".road-jy").first.is_visible()
            assert not pg.locator(".road-tl").first.is_visible()
            assert pg.locator(".jy-stage").count() >= 1
            # Switch back; it persists.
            pg.goto(base + "/settings")
            pg.locator('input[name="road_style"][value="timeline"]').click()
            assert pg.evaluate("localStorage.getItem('myroad.roadStyle')") == "timeline"
            pg.goto(base + play)
            pg.wait_for_load_state()
            assert pg.locator(".road-tl").first.is_visible()
            assert not pg.locator(".road-jy").first.is_visible()
            br.close()
    finally:
        server.should_exit = True
        th.join(timeout=5)


ORIENT_LABELS = {
    "he": ("כיוון הנתיב", "אנכי", "אופקי"),
    "en": ("Path direction", "Vertical", "Horizontal"),
    "ar": ("اتجاه المسار", "عمودي", "أفقي"),
}


@pytest.mark.parametrize("locale", list(ORIENT_LABELS))
def test_settings_has_the_orientation_control(app, locale) -> None:
    with TestClient(app) as c:
        login(c, f"ro-{locale}@example.com", first_name="T", last_name="H")
        c.cookies.set("myroad_locale", locale)
        legend, vertical, horizontal = ORIENT_LABELS[locale]
        page = c.get("/settings").text
        sec = page[page.index('class="settings-road-style"'):]
        assert legend in sec and vertical in sec and horizontal in sec
        assert 'name="road_orientation" value="vertical"' in sec
        assert 'name="road_orientation" value="horizontal"' in sec


def test_orientation_prefs_and_wide_only_css() -> None:
    js = (_UI / "static" / "prefs.js").read_text(encoding="utf-8")
    assert 'localStorage.getItem("myroad.roadOrientation")' in js
    assert 'data-road-orientation' in js
    css = (_UI / "static" / "road-journey.css").read_text(encoding="utf-8")
    # Horizontal layout is gated to wide screens; narrow is always vertical.
    assert "@media (min-width: 1024px)" in css
    assert 'html[data-road-orientation="horizontal"][data-road-style="journey"]' in css
    assert "@media (max-width: 1023.98px)" in css
    assert ".road-jy .jy-orient { display: none !important; }" in css


def test_switching_orientation_persists_and_is_horizontal_on_wide(app) -> None:
    """Settings radios write myroad.roadOrientation; the map uses it on wide screens only."""
    sync_api = pytest.importorskip("playwright.sync_api")
    uvicorn = pytest.importorskip("uvicorn")
    codes: list[str] = []
    app.state.login_code_sender = lambda email, code: codes.append(code)
    app.state.login_notice_sender = lambda email: None
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        with sync_api.sync_playwright() as p:
            chrome = os.environ.get("MYROAD_CHROME", "/usr/bin/google-chrome")
            try:
                br = p.chromium.launch(executable_path=chrome if Path(chrome).exists() else None,
                                       args=["--no-sandbox"])
            except Exception as exc:
                pytest.skip(f"no headless browser: {exc}")
            # Wide viewport first.
            ctx = br.new_context(locale="he-IL", viewport={"width": 1280, "height": 800})
            pg = ctx.new_page()
            pg.request.post(base + "/login", headers={"Origin": base}, form={
                "mode": "register", "first_name": "Noa", "last_name": "Levi",
                "email": "ro-pw@example.com", "next": "/"})
            assert codes, "no login code"
            pg.request.post(base + "/login/verify", headers={"Origin": base},
                            form={"code": codes[-1], "next": "/"})
            pg.goto(base + "/roads")
            href = pg.locator('a[href^="/play/"]').first.get_attribute("href")
            if not href:
                href = pg.locator('a[href^="/road/"]').first.get_attribute("href")
            assert href
            play = href if "view=map" in href else (href.split("?")[0] + "?view=map")
            # Turn on the journey style and horizontal orientation in Settings.
            pg.goto(base + "/settings")
            pg.locator('input[name="road_style"][value="journey"]').click()
            pg.locator('input[name="road_orientation"][value="horizontal"]').click()
            assert pg.evaluate("localStorage.getItem('myroad.roadOrientation')") == "horizontal"
            assert "נשמרו" in (pg.locator("#road-style-saved").inner_text() or "")
            pg.reload()
            assert pg.locator('input[name="road_orientation"][value="horizontal"]').is_checked()
            # On a wide map, the field is a horizontal scroller and the current stone is in view.
            pg.goto(base + play)
            pg.wait_for_load_state()
            assert pg.evaluate("document.documentElement.getAttribute('data-road-orientation')") == "horizontal"
            assert pg.locator(".road-jy").first.is_visible()
            field = pg.locator(".jy-field")
            pg.locator(".jy-stone").first.wait_for()
            pg.wait_for_timeout(200)
            overflow = pg.evaluate(
                """() => {
                    const f = document.querySelector('.jy-field');
                    const stages = document.querySelector('.jy-stages');
                    return {
                      ox: getComputedStyle(f).overflowX,
                      dir: stages ? getComputedStyle(stages).flexDirection : '',
                    };
                }"""
            )
            assert overflow["ox"] in ("auto", "scroll")
            assert overflow["dir"] == "row"
            # Current stone (or the stage) is within the field's visible horizontal range if present.
            here = pg.locator("[data-jy-current], #jy-here").first
            if here.count():
                box = here.bounding_box()
                field_box = field.bounding_box()
                assert box and field_box
                mid = box["x"] + box["width"] / 2
                assert field_box["x"] - 8 <= mid <= field_box["x"] + field_box["width"] + 8
            # Narrow screens stay vertical: the field does not scroll sideways and the toggle is hidden.
            pg.set_viewport_size({"width": 375, "height": 812})
            pg.wait_for_timeout(80)
            narrow = pg.evaluate(
                """() => {
                    const f = document.querySelector('.jy-field');
                    const stages = document.querySelector('.jy-stages');
                    const orient = document.querySelector('.jy-orient');
                    const cs = getComputedStyle(f);
                    return {
                      ox: cs.overflowX,
                      dir: stages ? getComputedStyle(stages).flexDirection : '',
                      orientDisplay: orient ? getComputedStyle(orient).display : 'none',
                    };
                }"""
            )
            assert narrow["dir"] == "column"
            assert narrow["ox"] in ("visible", "hidden", "clip", "auto")
            # Auto without row layout is fine; the path itself is a column.
            assert narrow["orientDisplay"] == "none"
            # Stored preference is unchanged.
            assert pg.evaluate("localStorage.getItem('myroad.roadOrientation')") == "horizontal"
            br.close()
    finally:
        server.should_exit = True
        th.join(timeout=5)
