"""Every screen's footer is only the product name + a localized "learning platform" label."""
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
_TPL = _CORE / "src" / "myroad_core" / "ui" / "templates"
EXPECTED = {"he": "פלטפורמת למידה · MyRoad", "en": "MyRoad · Learning platform", "ar": "منصة تعلم · MyRoad"}


def test_every_template_footer_is_the_platform_line() -> None:
    for p in _TPL.glob("*.html"):
        text = p.read_text(encoding="utf-8")
        for footer in re.findall(r"<footer>(.*?)</footer>", text, flags=re.S):
            assert "footer_platform" in footer and "<a " not in footer, p.name


def test_accessibility_statement_is_gone(tmp_path) -> None:
    assert not (_TPL / "accessibility.html").exists() and not (_TPL / "_a11y_link.html").exists()
    for code in EXPECTED:
        j = json.loads((_CORE / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        assert "a11y_link" not in j and "a11y_title" not in j
        assert j["footer_platform"].format(product="MyRoad") == EXPECTED[code]


@pytest.mark.parametrize("locale", list(EXPECTED))
def test_rendered_footers(tmp_path, locale) -> None:
    store = PathStore(str(tmp_path / "f.db"))
    app = create_learner_app(store=store, seed=True, seed_content=True)
    with TestClient(app) as c:
        c.cookies.set("myroad_locale", locale)
        r = c.get("/login")
        assert EXPECTED[locale] in r.text[r.text.rfind("<footer"):]
        login(c, f"f-{locale}@example.com", first_name="F", last_name="T")
        c.cookies.set("myroad_locale", locale)
        assert c.get("/accessibility").status_code == 404
        for url in ("/", "/settings", "/add-path", "/play/path_grade3_math_add20?view=map",
                    "/play/path_grade3_math_add20?view=stats"):
            r = c.get(url)
            assert r.status_code == 200, url
            assert EXPECTED[locale] in r.text[r.text.rfind("<footer"):], url
    store.close()
