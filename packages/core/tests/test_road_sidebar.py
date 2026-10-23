"""Road picker side panel (sidebar option 4): on home and track, not in the step player;
settings live only in the bottom user chip; phone drawer markup works without JS."""

from __future__ import annotations

import re

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

PID = "path_grade3_english_animals"


@pytest.fixture
def client(tmp_path):
    store = PathStore(str(tmp_path / "side.db"))
    app = create_learner_app(store=store, seed=True, seed_content=True)
    with TestClient(app) as c:
        login_with_code(c, data={"first_name": "Noa", "last_name": "Side", "email": "side@example.com", "next": "/"},
                        follow_redirects=True)
        yield c
    store.close()


def _side(html: str) -> str:
    m = re.search(r'<nav class="side" id="roads".*?</nav>', html, re.S)
    assert m, "road panel missing"
    return m.group(0)


@pytest.mark.parametrize("locale", ["he", "en", "ar"])
def test_panel_on_home_and_track(client: TestClient, locale: str) -> None:
    client.cookies.set("myroad_locale", locale)
    for url in ("/", f"/play/{PID}?view=map"):
        html = client.get(url).text
        side = _side(html)
        assert 'class="qtabs"' in side and 'name="group"' in side and 'id="side-q"' in side
        assert 'href="/add-path"' in side
        assert f'href="/play/{PID}?view=map' in side
        assert '<script src="/static/sidebar.js" defer></script>' in html
    track = client.get(f"/play/{PID}?view=map").text
    assert re.search(rf'<a class="road[^"]*" href="/play/{PID}\?view=map[^"]*" data-path-id="{PID}" aria-current="page"', track)
    assert 'href="#track"' in track and 'id="track"' in track


def test_step_player_stays_full_width(client: TestClient) -> None:
    html = client.get(f"/play/{PID}?view=learn").text
    assert 'id="roads"' not in html and "app-shell" not in html


@pytest.mark.parametrize("url", ["/", f"/play/{PID}?view=map", f"/play/{PID}?view=learn", "/add-path",
                                 "/series/english-bagrut5"])
def test_settings_link_only_in_user_chip(client: TestClient, url: str) -> None:
    html = client.get(url).text
    links = re.findall(r'<a [^>]*href="/settings"[^>]*>', html)
    if 'id="roads"' in html:
        assert links == ['<a class="user" href="/settings">']
        assert html.index('class="side-foot"') < html.index('href="/settings"')
    else:
        assert links == []


def test_subject_tab_and_group_filter_reuse_url_params(client: TestClient) -> None:
    side = _side(client.get("/?subject=english&group=all").text)
    assert re.search(r'href="/\?[^"]*subject=english[^"]*" aria-current="true"', side)
    assert '<option value="all" selected>' in side
    rows = re.findall(r'data-path-id="([^"]+)"', side)
    assert rows and PID in rows
    assert all("english" in r for r in rows)


def test_drawer_markup_works_without_js(client: TestClient) -> None:
    html = client.get("/").text
    menu = re.search(r'<a class="ibtn menu-btn"[^>]*>', html).group(0)
    assert 'href="#roads"' in menu and 'aria-controls="roads"' in menu
    side = _side(html)
    assert 'aria-labelledby="roads-title"' in side
    assert '<button type="submit"' in side  # group filter submits without JS
    js = (client.get("/static/sidebar.js")).text
    for needle in ("aria-expanded", ".inert", "Escape", '"Tab"', "matchMedia"):
        assert needle in js
    css = client.get("/static/platform.css").text
    assert "prefers-reduced-motion: reduce) { .js .side" in css
