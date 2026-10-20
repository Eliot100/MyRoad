"""Reading comfort settings (UX M7, #104): text size + reduce motion, client-side."""
from __future__ import annotations

import json
from pathlib import Path

from auth_helpers import login

_UI = Path(__file__).resolve().parents[1] / "src" / "myroad_core" / "ui"
_LOC = Path(__file__).resolve().parents[1] / "locales"


def _client():
    from test_visual_polish import _login_client
    return _login_client()


def test_prefs_script_loads_before_css_on_every_learner_page():
    for name in ("home.html", "map.html", "play.html", "settings.html", "login.html",
                 "accessibility.html", "stats.html", "add_path.html"):
        html = (_UI / "templates" / name).read_text(encoding="utf-8")
        head = html.split("</head>")[0]
        i = head.index('<script src="/static/prefs.js"></script>')  # sync, not defer
        assert i < head.index("platform.css"), name


def test_prefs_script_reads_storage_and_skips_view_transitions():
    js = (_UI / "static" / "prefs.js").read_text(encoding="utf-8")
    for s in ("myroad.textSize", "myroad.motion", "data-text-size", "data-motion",
              "prefers-reduced-motion", "skipTransition"):
        assert s in js


def test_css_scales_text_and_disables_motion():
    css = (_UI / "static" / "platform.css").read_text(encoding="utf-8")
    assert 'html[data-text-size="125"] { font-size: 125%; }' in css
    assert 'html[data-text-size="150"] { font-size: 150%; }' in css
    assert 'html[data-motion="reduce"] ::view-transition-group(*)' in css
    assert "scroll-behavior: auto !important" in css


def test_settings_page_offers_text_size_and_reduce_motion():
    c = _client()
    login(c, next="/settings")
    page = c.get("/settings").text
    assert 'id="reading-prefs"' in page
    for v in ("100", "125", "150"):
        assert f'name="text_size" value="{v}"' in page
    assert 'name="reduce_motion"' in page
    assert "<legend>" in page


def test_reading_prefs_strings_in_every_locale():
    keys = ("text_size", "text_size_100", "text_size_125", "text_size_150", "motion",
            "reduce_motion", "reading_prefs_note")
    for code in ("he", "en", "ar"):
        j = json.loads((_LOC / f"{code}.json").read_text(encoding="utf-8"))
        for k in keys:
            assert j[k].strip(), (code, k)
