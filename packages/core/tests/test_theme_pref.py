"""Theme setting (light/dark, client-side) and the sidebar gear button."""
from __future__ import annotations

import json
import re
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
LABELS = {"he": ("הגדרות", "ערכת תצוגה", "בהיר", "כהה"), "en": ("Settings", "Theme", "Light", "Dark"),
          "ar": ("الإعدادات", "المظهر", "فاتح", "داكن")}


@pytest.fixture
def app(tmp_path):
    store = PathStore(str(tmp_path / "th.db"))
    yield create_learner_app(store=store, seed=True, seed_content=True)
    store.close()


def test_locale_keys_in_all_three() -> None:
    for code, (settings, h, light, dark) in LABELS.items():
        j = json.loads((_CORE / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        assert j["settings"] == settings and j["theme_h"] == h
        assert j["theme_light"] == light and j["theme_dark"] == dark and j["theme_legend"] and j["theme_note"]


@pytest.mark.parametrize("locale", list(LABELS))
def test_theme_control_and_gear(app, locale) -> None:
    with TestClient(app) as c:
        login(c, f"th-{locale}@example.com", first_name="T", last_name="H")
        c.cookies.set("myroad_locale", locale)
        settings, h, light, dark = LABELS[locale]
        home = c.get("/").text
        foot = home[home.index('class="side-foot"'):]
        assert re.search(rf'<a class="ibtn" href="/settings" title="{settings}"', foot)
        assert f'<span class="visually-hidden">{settings}</span></a>' in foot
        assert "<small>" not in foot[:foot.index("</nav>")]
        page = c.get("/settings").text
        sec = page[page.index('class="settings-theme"'):]
        assert f'<h2 id="settings-theme">{h}</h2>' in sec
        assert 'name="theme" value="light"' in sec and 'name="theme" value="dark"' in sec
        assert light in sec and dark in sec and 'localStorage.setItem("myroad.theme"' in sec


def test_theme_bootstrap_and_tokens() -> None:
    js = (_UI / "static" / "prefs.js").read_text(encoding="utf-8")
    assert 'localStorage.getItem("myroad.theme")' in js and 'setAttribute("data-theme"' in js
    css = (_UI / "static" / "platform.css").read_text(encoding="utf-8")
    assert ':root:not([data-theme="light"])' in css and ':root[data-theme="dark"] {' in css
    dark = css[css.index(':root[data-theme="dark"] {'):]
    assert "--accent: #5fd4c4;" in dark[:dark.index("}")]
