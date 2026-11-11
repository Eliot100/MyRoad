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



def j_orient(locale: str, key: str) -> str:
    import json as _json
    return _json.loads((_CORE / "locales" / f"{locale}.json").read_text(encoding="utf-8"))[key]


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
                  "road_orient_h", "road_orient_legend", "road_orient_vertical",
                  "road_orient_vertical_note", "road_orient_horizontal",
                  "road_orient_horizontal_note", "road_orient_narrow_note"):
            assert j[k] and "—" not in j[k] and "–" not in j[k]
        assert "מסע" not in j["jy_lede"] and "מסע" not in j["road_style_journey_note"]


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
        assert j_orient(locale, "road_orient_vertical") in sec
        assert j_orient(locale, "road_orient_horizontal") in sec


def test_prefs_bootstrap_and_css_toggle() -> None:
    js = (_UI / "static" / "prefs.js").read_text(encoding="utf-8")
    assert 'localStorage.getItem("myroad.roadStyle")' in js
    assert 'setAttribute("data-road-style"' in js
    assert 'window.myroadRoadStyle' in js
    css = (_UI / "static" / "road-journey.css").read_text(encoding="utf-8")
    assert 'html:not([data-road-style="journey"]) [data-road-style-panel="journey"]' in css
    assert 'html[data-road-style="journey"] [data-road-style-panel="timeline"]' in css
    # Light and dark lawn and stone tokens both exist.
    assert "--jy-lawn:" in css and "--jy-stone:" in css
    dark_at = css.index(':root[data-theme="dark"] .road-jy')
    assert "--jy-lawn:" in css[dark_at:dark_at + 900]
    assert "--jy-stone:" in css[dark_at:dark_at + 900]
    # Orientation is bootstrapped before paint, same as the style.
    assert 'localStorage.getItem("myroad.roadOrientation")' in js
    assert 'setAttribute("data-road-orientation"' in js
    assert 'window.myroadRoadOrientation' in js
    # Narrow screens stay vertical: horizontal layout is gated at 1024px.
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
    "he": ("כיוון הדרך", "אנכי", "אופקי"),
    "en": ("Path direction", "Vertical", "Horizontal"),
    "ar": ("اتجاه الطريق", "عمودي", "أفقي"),
}


def test_orientation_labels_in_all_three() -> None:
    for code, (h, vertical, horizontal) in ORIENT_LABELS.items():
        j = json.loads((_CORE / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        assert j["road_orient_h"] == h
        assert j["road_orient_vertical"] == vertical
        assert j["road_orient_horizontal"] == horizontal


def test_orientation_persists_and_applies(app) -> None:
    """Orientation is saved in localStorage, used on wide screens, and ignored on narrow ones."""
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
            ctx = br.new_context(locale="he-IL", viewport={"width": 1280, "height": 800})
            pg = ctx.new_page()
            pg.request.post(base + "/login", headers={"Origin": base}, form={
                "mode": "register", "first_name": "Noa", "last_name": "Levi",
                "email": "rs-orient@example.com", "next": "/"})
            assert codes, "no login code"
            pg.request.post(base + "/login/verify", headers={"Origin": base},
                            form={"code": codes[-1], "next": "/"})
            pg.goto(base + "/roads")
            href = pg.locator('a[href^="/play/"]').first.get_attribute("href")
            if not href:
                href = pg.locator('a[href^="/road/"]').first.get_attribute("href")
            assert href
            play = href if "view=map" in href else (href.split("?")[0] + "?view=map")
            # Default orientation is vertical.
            pg.goto(base + "/settings")
            pg.wait_for_load_state()
            assert pg.evaluate("document.documentElement.getAttribute('data-road-orientation')") == "vertical"
            assert pg.locator('input[name="road_orientation"][value="vertical"]').is_checked()
            # Switch to horizontal; it persists.
            pg.locator('input[name="road_orientation"][value="horizontal"]').click()
            assert pg.evaluate("localStorage.getItem('myroad.roadOrientation')") == "horizontal"
            assert "נשמרו" in (pg.locator("#road-style-saved").inner_text() or "")
            pg.reload()
            assert pg.locator('input[name="road_orientation"][value="horizontal"]').is_checked()
            # Journey style on a wide screen lays out horizontally, RTL starts on the right.
            pg.evaluate("localStorage.setItem('myroad.roadStyle','journey')")
            pg.goto(base + play)
            pg.wait_for_load_state()
            pg.wait_for_selector(".road-jy.is-laid", timeout=5000)
            pg.wait_for_timeout(300)
            assert pg.evaluate("document.documentElement.getAttribute('data-road-orientation')") == "horizontal"
            assert pg.locator(".road-jy").first.is_visible()
            assert pg.locator(".road-jy.is-horizontal").count() == 1
            assert pg.locator('[data-jy-orient="horizontal"]').get_attribute("aria-pressed") == "true"
            boxes = pg.evaluate("""() => {
              const steps = [...document.querySelectorAll('.jy-step')];
              if (steps.length < 2) return null;
              const a = steps[0].getBoundingClientRect();
              const b = steps[steps.length - 1].getBoundingClientRect();
              const here = document.querySelector('.jy-step.is-here, #jy-here');
              const hr = here ? here.getBoundingClientRect() : null;
              const field = document.querySelector('.jy-field');
              const fr = field.getBoundingClientRect();
              const jy = document.querySelector('.road-jy');
              return {
                firstX: a.x, lastX: b.x, n: steps.length,
                here: hr && {x: hr.x, y: hr.y, w: hr.width, h: hr.height},
                field: fr && {x: fr.x, y: fr.y, w: fr.width, h: fr.height, sl: field.scrollLeft, sw: field.scrollWidth, cw: field.clientWidth},
                laid: jy && jy.className,
                hereInView: hr ? (hr.right > fr.left && hr.left < fr.right && hr.bottom > fr.top && hr.top < fr.bottom) : true
              };
            }""")
            assert boxes and boxes["n"] >= 2
            # RTL: the path starts on the right, so the first stone is to the right of the last
            # (or they share the visible frame if the path is short). Reading direction is right to left.
            assert boxes["firstX"] >= boxes["lastX"] - 2
            assert boxes["hereInView"] is True
            # On-page toggle switches back to vertical.
            pg.locator(".jy-orient").scroll_into_view_if_needed()
            pg.locator('[data-jy-orient="vertical"]').click()
            pg.wait_for_timeout(300)
            assert pg.evaluate("localStorage.getItem('myroad.roadOrientation')") == "vertical"
            assert pg.locator(".road-jy.is-horizontal").count() == 0
            assert pg.locator(".road-jy.is-vertical").count() == 1
            # Narrow screens stay vertical even when the stored preference is horizontal.
            pg.evaluate("localStorage.setItem('myroad.roadOrientation','horizontal'); document.documentElement.setAttribute('data-road-orientation','horizontal')")
            pg.set_viewport_size({"width": 375, "height": 812})
            pg.goto(base + play)
            pg.wait_for_load_state()
            pg.wait_for_timeout(400)
            assert pg.evaluate("localStorage.getItem('myroad.roadOrientation')") == "horizontal"
            assert pg.locator(".road-jy.is-horizontal").count() == 0
            # Stones are stacked (first is above the last).
            stacked = pg.evaluate("""() => {
              const steps = [...document.querySelectorAll('.jy-step')];
              if (steps.length < 2) return null;
              const a = steps[0].getBoundingClientRect();
              const b = steps[steps.length - 1].getBoundingClientRect();
              return { firstY: a.y, lastY: b.y };
            }""")
            assert stacked and stacked["lastY"] > stacked["firstY"]
            # The on-page orientation control is not shown on a narrow screen.
            assert pg.locator(".jy-orient").first.is_visible() is False
            br.close()
    finally:
        server.should_exit = True
        th.join(timeout=5)

