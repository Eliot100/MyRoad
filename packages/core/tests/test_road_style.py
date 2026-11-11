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
        for k in ("road_style_timeline_note", "road_style_journey_note", "jy_lede"):
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


def test_prefs_bootstrap_and_css_toggle() -> None:
    js = (_UI / "static" / "prefs.js").read_text(encoding="utf-8")
    assert 'localStorage.getItem("myroad.roadStyle")' in js
    assert 'setAttribute("data-road-style"' in js
    assert 'window.myroadRoadStyle' in js
    css = (_UI / "static" / "road-journey.css").read_text(encoding="utf-8")
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
