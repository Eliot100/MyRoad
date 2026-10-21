"""Map: floating "back to my station" button (UI pass 2026-10)."""
from __future__ import annotations

import json
import re
from pathlib import Path

_UI = Path(__file__).resolve().parents[1] / "src" / "myroad_core" / "ui"


def test_float_button_is_hidden_by_default_and_targets_here():
    html = (_UI / "templates" / "map.html").read_text(encoding="utf-8")
    m = re.search(r'<a class="float-here" href="#here" hidden>', html)
    assert m, "no-JS users never see it; the #here pill link keeps working"
    assert "not read_only" in html[html.rfind("{%", 0, m.start()):m.start()]


def test_float_button_uses_intersection_observer_and_reduced_motion():
    js = (_UI / "static" / "platform.js").read_text(encoding="utf-8")
    body = js.split("function floatBackToStation", 1)[1].split("\n  }\n", 1)[0]
    assert "IntersectionObserver" in body and "isIntersecting" in body
    assert "myroadReduceMotion" in body


def test_float_button_css_is_rtl_safe():
    css = (_UI / "static" / "platform.css").read_text(encoding="utf-8")
    rule = re.search(r"\.float-here \{([^}]*)\}", css).group(1)
    assert "inset-inline-end" in rule and "left" not in rule and "right" not in rule
    assert "min-height: 44px" in rule


def test_float_button_label_in_every_locale():
    loc = Path(__file__).resolve().parents[1] / "locales"
    for code in ("he", "en", "ar"):
        assert json.loads((loc / f"{code}.json").read_text(encoding="utf-8"))["map_back_to_station"].strip()
