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
                   "road_orient_legend", "road_orient_vertical", "road_orient_horizontal",
                   "road_orient_note", "jy_orient_group"):
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
        assert 'name="road_orient" value="vertical"' in sec
        assert 'name="road_orient" value="horizontal"' in sec
        assert 'localStorage.setItem("myroad.roadOrientation"' in sec


def test_prefs_bootstrap_and_css_toggle() -> None:
    js = (_UI / "static" / "prefs.js").read_text(encoding="utf-8")
    assert 'localStorage.getItem("myroad.roadStyle")' in js
    assert 'setAttribute("data-road-style"' in js
    assert 'window.myroadRoadStyle' in js
    assert 'localStorage.getItem("myroad.roadOrientation")' in js
    assert 'setAttribute("data-road-orientation"' in js
    assert 'window.myroadRoadOrientation' in js
    css = (_UI / "static" / "road-journey.css").read_text(encoding="utf-8")
    # Orientation control is hidden on narrow screens and shown from 1024px.
    assert "@media (min-width: 1024px)" in css
    assert ".jy-orient" in css
    assert 'data-road-orientation="horizontal"' in css
    assert 'html:not([data-road-style="journey"]) [data-road-style-panel="journey"]' in css
    assert 'html[data-road-style="journey"] [data-road-style-panel="timeline"]' in css
    # Light and dark asphalt tokens both exist.
    assert "--jy-pave:" in css
    dark_at = css.index(':root[data-theme="dark"] .road-jy')
    assert "--jy-pave:" in css[dark_at:dark_at + 400]


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
        assert 'id="track"' in html
        assert "/static/road-journey.css" in html and "/static/road-journey.js" in html
        assert 'class="jy-stone' in html
        assert 'class="jy-stones"' in html
        assert 'data-jy-orient="horizontal"' in html
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


ORIENT = {
    "he": ("אנכי", "אופקי", "כיוון הדרך במסך רחב"),
    "en": ("Vertical", "Horizontal", "Road direction on a wide screen"),
    "ar": ("عمودي", "أفقي", "اتجاه الطريق على شاشة واسعة"),
}


@pytest.mark.parametrize("locale", list(ORIENT))
def test_settings_has_the_orientation_control(app, locale) -> None:
    with TestClient(app) as c:
        login(c, f"ro-{locale}@example.com", first_name="T", last_name="H")
        c.cookies.set("myroad_locale", locale)
        vert, horiz, legend = ORIENT[locale]
        page = c.get("/settings").text
        sec = page[page.index('class="settings-road-style"'):]
        assert legend in sec and vert in sec and horiz in sec
        assert 'name="road_orient" value="vertical"' in sec
        assert 'name="road_orient" value="horizontal"' in sec


def test_orientation_toggle_persists_and_is_wide_only(app) -> None:
    """Wide screens can switch vertical/horizontal; the choice persists; phones stay vertical."""
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
            # Choose the journey style, then open the road on a phone.
            pg.goto(base + "/settings")
            pg.locator('input[name="road_style"][value="journey"]').click()
            pg.locator('input[name="road_orient"][value="horizontal"]').click()
            assert pg.evaluate("localStorage.getItem('myroad.roadOrientation')") == "horizontal"
            assert pg.evaluate("document.documentElement.getAttribute('data-road-orientation')") == "horizontal"
            pg.goto(base + play)
            pg.wait_for_load_state()
            pg.locator(".road-jy").wait_for()
            # The attribute persists, but the on-page toggle is hidden and the
            # layout stays a vertical column of stones (phone is always vertical).
            assert pg.evaluate("document.documentElement.getAttribute('data-road-orientation')") == "horizontal"
            assert pg.locator(".jy-orient").first.is_hidden()
            stones = pg.locator(".jy-stone")
            assert stones.count() >= 2
            a = stones.nth(0).bounding_box()
            b = stones.nth(min(2, stones.count() - 1)).bounding_box()
            assert a and b
            # Vertical path: later stones are further down, not a horizontal row.
            assert b["y"] > a["y"] + 20
            # Current stone (if any) is a 44px-or-larger target.
            here = pg.locator(".jy-stone.is-here")
            if here.count():
                box = here.first.bounding_box()
                assert box and box["width"] >= 44 and box["height"] >= 44
                assert here.first.get_attribute("aria-current") == "step"
            # Wide screen: the toggle is visible and horizontal layout is applied.
            pg.set_viewport_size({"width": 1280, "height": 800})
            pg.reload()
            pg.locator(".road-jy").wait_for()
            assert pg.locator(".jy-orient").first.is_visible()
            assert pg.locator('[data-jy-orient="horizontal"]').get_attribute("aria-pressed") == "true"
            canvas = pg.locator(".jy-canvas")
            overflow = canvas.evaluate("el => getComputedStyle(el).overflowX")
            assert overflow in ("auto", "scroll")
            # Switching back to vertical on the road page persists.
            pg.locator('[data-jy-orient="vertical"]').click()
            assert pg.evaluate("localStorage.getItem('myroad.roadOrientation')") == "vertical"
            assert pg.locator('[data-jy-orient="vertical"]').get_attribute("aria-pressed") == "true"
            overflow = canvas.evaluate("el => getComputedStyle(el).overflowX")
            assert overflow in ("hidden", "visible", "clip")
            pg.reload()
            pg.locator(".road-jy").wait_for()
            assert pg.evaluate("localStorage.getItem('myroad.roadOrientation')") == "vertical"
            assert pg.locator('[data-jy-orient="vertical"]').get_attribute("aria-pressed") == "true"
            # Settings radio stays in sync.
            pg.goto(base + "/settings")
            assert pg.locator('input[name="road_orient"][value="vertical"]').is_checked()
            br.close()
    finally:
        server.should_exit = True
        th.join(timeout=5)
