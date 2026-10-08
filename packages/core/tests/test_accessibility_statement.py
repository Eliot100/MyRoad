"""Accessibility statement page (#60).

Public page in he/en/ar, linked from the footer of every page and from settings.
States only facts about the product; real-world details (coordinator, phone, email,
dates) come from MYROAD_A11Y_* env vars and render as marked placeholders until set.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient

from auth_helpers import login

from myroad_core.store import PathStore
from myroad_core.ui.a11y_statement import DONE, GAPS, OPTIONAL_FIELDS, REQUIRED_FIELDS, statement_details
from myroad_core.ui.app import create_learner_app

_CORE = Path(__file__).resolve().parents[1]
_UI = _CORE / "src" / "myroad_core" / "ui"
_LOCALES = _CORE / "locales"
PID = "path_test_a11y"
LINK = '<a class="a11y-link" href="/accessibility">'
ENV_NAMES = [name for _, name, _ in REQUIRED_FIELDS + OPTIONAL_FIELDS]


def _doc() -> dict:
    return {"id": PID, "subject": "math", "group_ids": ["adult"], "emoji": "♿", "estimated_minutes": 5,
            "titles": {"he": "נגישות", "en": "Access", "ar": "وصول"},
            "blurbs": {"he": "בדיקה.", "en": "Test.", "ar": "اختبار."},
            "topics": [{"id": "t1", "titles": {"he": "א", "en": "A", "ar": "أ"}, "node_ids": ["n1"]}],
            "nodes": [{"id": "n1", "type": "learn", "title": "הסבר", "body_he": "הסבר"}]}


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_doc(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "a11y.db"))
    yield create_learner_app(store=store, seed=True, seed_content=True)
    store.close()


def _anon(app, locale: str = "he") -> TestClient:
    c = TestClient(app)
    c.cookies.set("myroad_locale", locale)
    return c


def _signed_in(app, locale: str = "he") -> TestClient:
    c = _anon(app, locale)
    login(c, f"a11y-{locale}@example.com", first_name="A", last_name="B")
    c.cookies.set("myroad_locale", locale)
    return c


def _strings(locale: str) -> dict:
    return json.loads((_LOCALES / f"{locale}.json").read_text(encoding="utf-8"))


def _main(html: str) -> str:
    return html[html.index("<main"):html.index("</main>")]


# --- the page --------------------------------------------------------------------------

@pytest.mark.parametrize("locale", ["he", "en", "ar"])
def test_public_page_in_each_language(app, locale) -> None:
    r = _anon(app, locale).get("/accessibility", follow_redirects=False)
    assert r.status_code == 200  # no sign-in needed
    html, s = r.text, _strings(locale)
    assert f'<html lang="{locale}" dir="{"ltr" if locale == "en" else "rtl"}">' in html
    assert f"<h1>{s['a11y_title']}</h1>" in html
    main = _main(html)
    for key in DONE + GAPS:
        assert f'data-key="{key}"' in main, key
    plain = html_lib.unescape(re.sub(r"<[^>]+>", "", main))
    for key in ("a11y_standard", "a11y_contact", "a11y_tested", *DONE, *GAPS):
        assert s[key] in plain, key
    assert "a11y_" not in plain  # no raw keys
    # Standard named, conformance stated honestly.
    assert "5568" in plain and "WCAG 2.2" in plain
    # One h1, sections labelled by their h2.
    assert main.count("<h1") == 1
    for sid in ("a11y-standard", "a11y-done", "a11y-gaps", "a11y-contact", "a11y-tested"):
        assert f'aria-labelledby="{sid}"' in main and f'<h2 id="{sid}">' in main
    assert LINK in html  # its own footer too


def test_locale_strings_are_complete_and_in_the_right_script() -> None:
    he, en, ar = _strings("he"), _strings("en"), _strings("ar")
    keys = {k for k in en if k.startswith("a11y_")}
    assert keys == {k for k in he if k.startswith("a11y_")} == {k for k in ar if k.startswith("a11y_")}
    assert set(DONE) | set(GAPS) <= keys
    for k in keys:
        assert he[k].strip() and en[k].strip() and ar[k].strip(), k
        assert re.search(r"[\u0590-\u05FF]", he[k]), k
        assert re.search(r"[\u0600-\u06FF]", ar[k]), k


# --- placeholders: never invented ------------------------------------------------------

def test_unset_details_are_marked_placeholders_not_made_up(app) -> None:
    html = _anon(app).get("/accessibility").text
    main = _main(html)
    marks = re.findall(r'<mark class="a11y-placeholder" data-placeholder="([A-Z0-9_]+)">', main)
    assert sorted(marks) == sorted(name for _, name, _ in REQUIRED_FIELDS)
    assert "למילוי" in main
    assert "mailto:" not in main and "tel:" not in main
    assert 'data-field="address"' not in main  # optional, hidden when unset
    assert not re.search(r"\d{2,3}-?\d{7}", re.sub(r"<[^>]+>", "", main))  # no phone-like numbers
    assert statement_details({})["missing"] == [name for _, name, _ in REQUIRED_FIELDS]


def test_configured_details_replace_placeholders(app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MYROAD_A11Y_ORG_NAME", "Example Ltd")
    monkeypatch.setenv("MYROAD_A11Y_COORDINATOR_NAME", "<b>Dana</b>")
    monkeypatch.setenv("MYROAD_A11Y_PHONE", "03-555 0000")
    monkeypatch.setenv("MYROAD_A11Y_EMAIL", "access@example.com")
    monkeypatch.setenv("MYROAD_A11Y_STATEMENT_DATE", "2026-10-08")
    monkeypatch.setenv("MYROAD_A11Y_AUDIT_DATE", "2026-11-01")
    monkeypatch.setenv("MYROAD_A11Y_ADDRESS", "1 Example St")
    main = _main(_anon(app, "en").get("/accessibility").text)
    assert "a11y-placeholder" not in main
    assert '<a href="mailto:access@example.com" dir="ltr">access@example.com</a>' in main
    assert '<a href="tel:035550000" dir="ltr">03-555 0000</a>' in main
    assert "&lt;b&gt;Dana&lt;/b&gt;" in main and "<b>Dana" not in main  # escaped
    assert 'data-field="address"' in main and "1 Example St" in main
    assert "Example Ltd" in main and "2026-10-08" in main and "2026-11-01" in main


def test_bad_email_or_phone_gets_no_link() -> None:
    d = statement_details({"MYROAD_A11Y_EMAIL": "javascript:alert(1)", "MYROAD_A11Y_PHONE": "call us"})
    assert d["fields"]["email"]["href"] == "" and d["fields"]["phone"]["href"] == ""
    assert d["fields"]["email"]["value"] == "javascript:alert(1)"  # shown as text, escaped by Jinja


# --- reachable from every page -----------------------------------------------------------

def test_every_full_page_template_links_the_statement() -> None:
    pages = [p for p in (_UI / "templates").glob("*.html") if "<!DOCTYPE html>" in p.read_text(encoding="utf-8")]
    assert {p.name for p in pages} >= {"home.html", "map.html", "play.html", "stats.html", "settings.html",
                                       "login.html", "add_path.html", "learner.html", "accessibility.html"}
    for p in pages:
        text = p.read_text(encoding="utf-8")
        footer = text[text.rfind("<footer"):text.rfind("</footer>")]
        assert '{% include "_a11y_link.html" %}' in footer, p.name


@pytest.mark.parametrize("locale", ["he", "en", "ar"])
def test_rendered_pages_have_the_footer_link(app, locale) -> None:
    label = _strings(locale)["a11y_link"]
    anon = _anon(app, locale)
    assert LINK + label + "</a>" in anon.get("/login").text
    c = _signed_in(app, locale)
    c.post(f"/play/{PID}/start")
    urls = ["/", f"/play/{PID}?view=map", f"/play/{PID}?view=learn", "/settings", "/add-path", "/accessibility"]
    for url in urls:
        r = c.get(url)
        assert r.status_code == 200, url
        footer = r.text[r.text.rfind("<footer"):]
        assert LINK + label + "</a>" in footer, url
    author = c.get("/author")
    if author.status_code == 200:
        assert LINK in author.text


def test_settings_links_the_statement(app) -> None:
    html = _signed_in(app, "en").get("/settings").text
    section = html[html.index('class="settings-a11y"'):]
    assert '<h2 id="settings-a11y">Accessibility</h2>' in section
    assert '<a href="/accessibility">Accessibility statement</a>' in section


def test_language_buttons_switch_without_sign_in(app) -> None:
    c = _anon(app, "he")
    html = c.get("/accessibility").text
    form = html[html.index('class="a11y-langs"') - 40:html.index("</form>", html.index('class="a11y-langs"'))]
    assert 'action="/locale"' in form and 'name="next" value="/accessibility"' in form
    for loc in ("he", "en", "ar"):
        assert f'name="locale" value="{loc}" lang="{loc}"' in form
    assert 'value="he" lang="he" class="secondary" aria-current="true"' in form
    r = c.post("/locale", data={"locale": "ar", "next": "/accessibility"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/accessibility"
    assert '<html lang="ar" dir="rtl">' in c.get("/accessibility").text


def test_site_wide_focus_motion_and_target_rules() -> None:
    for css_name in ("platform.css", "learner.css"):
        css = (_UI / "static" / css_name).read_text(encoding="utf-8")
        tail = css[css.index("(#60)"):]
        assert ":where(a, button, input, select, textarea, summary, [tabindex]):focus-visible" in tail
        assert re.search(r"@media \(prefers-reduced-motion: reduce\) \{\s*\*, \*::before, \*::after \{ transition: none !important; animation: none !important;", tail)
        assert re.search(r"footer \.a11y-link(,\n[^{]+)? \{ display: inline-block; min-height: 24px;", tail)
    css = (_UI / "static" / "platform.css").read_text(encoding="utf-8")
    assert ".a11y-langs button { min-height: 44px; min-width: 44px;" in css
