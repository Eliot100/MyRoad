"""Privacy notice and terms of use (#209): open before and after sign in, linked from the footer,
settings and the signup step; the notice discloses the pseudonymous log; copy has no dashes (email addresses may contain a hyphen)."""
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
LOCALES = ("he", "en", "ar")
DASHES = re.compile(r"[\u2010-\u2015\u2212-]")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PRIVACY_CONTACT = "eli4056-3ery4h@mail.grokbot.com"
PLACEHOLDERS = re.compile(
    r"TODO|TBD|XXX|placeholder|TO FILL|להשלים|للاستكمال",
    re.I,
)
LOG_WORDS = {
    "he": ("יומן", "לחיצות", "תשובות", "זמני מסכים", "מזהה בדוי"),
    "en": ("log", "taps", "answers", "screen timings", "pseudonymous"),
    "ar": ("سجل", "نقرات", "إجابات", "أوقات الشاشات", "مستعار"),
}


def _main(html: str) -> str:
    return html[html.index("<main"):html.index("</main>")]


def _text(fragment: str) -> str:
    return re.sub(r"<[^>]+>", " ", fragment)


@pytest.fixture()
def client(tmp_path):
    store = PathStore(str(tmp_path / "legal.db"))
    app = create_learner_app(store=store, seed=True)
    with TestClient(app) as c:
        yield c
    store.close()


def _footer_links(html: str) -> list[str]:
    start = html.rfind("<footer")
    footer = html[start:html.index("</footer>", start)]
    return re.findall(r'href="([^"]+)"', footer)


@pytest.mark.parametrize("locale", LOCALES)
def test_pages_render_logged_out_and_in(client, locale) -> None:
    client.cookies.set("myroad_locale", locale)
    for url in ("/privacy", "/terms"):
        r = client.get(url, follow_redirects=False)
        assert r.status_code == 200, url
        assert 'href="/login"' in r.text  # signed out: way back to sign in
        assert _footer_links(r.text) == ["/privacy", "/terms"]
    login(client, f"legal-{locale}@example.com", first_name="L", last_name="P")
    client.cookies.set("myroad_locale", locale)
    for url in ("/privacy", "/terms"):
        r = client.get(url)
        assert r.status_code == 200, url
        assert 'aria-current="page"' in r.text[r.text.rfind("<footer"):]


def test_rtl_and_landmarks(client) -> None:
    for locale, d in (("he", "rtl"), ("ar", "rtl"), ("en", "ltr")):
        client.cookies.set("myroad_locale", locale)
        html = client.get("/privacy").text
        assert f'dir="{d}"' in html
        assert html.count("<h1") == 1 and "<main" in html and "<footer" in html
        assert 'class="legal-links" aria-label=' in html


@pytest.mark.parametrize("locale", LOCALES)
def test_notice_discloses_pseudonymous_log(client, locale) -> None:
    client.cookies.set("myroad_locale", locale)
    body = _text(_main(client.get("/privacy").text))
    for word in LOG_WORDS[locale]:
        assert word.lower() in body.lower(), word


def _without_emails(text: str) -> str:
    return EMAIL.sub("EMAIL", text)


@pytest.mark.parametrize("locale", LOCALES)
def test_no_dashes_in_copy(client, locale) -> None:
    client.cookies.set("myroad_locale", locale)
    for url in ("/privacy", "/terms"):
        assert not DASHES.search(_without_emails(_text(_main(client.get(url).text)))), url
    j = json.loads((_CORE / "locales" / f"{locale}.json").read_text(encoding="utf-8"))
    for k, v in j.items():
        if k.startswith(("privacy_", "terms_", "legal_", "register_legal", "settings_legal")):
            assert not DASHES.search(_without_emails(v)), k


@pytest.mark.parametrize("locale", LOCALES)
def test_legal_copy_is_filled(locale) -> None:
    j = json.loads((_CORE / "locales" / f"{locale}.json").read_text(encoding="utf-8"))
    for k, v in j.items():
        if k.startswith(("privacy_", "terms_", "legal_", "register_legal", "settings_legal")):
            assert not PLACEHOLDERS.search(v), k
            assert "[" not in v and "]" not in v, k
    assert j["privacy_contact_p"].count(PRIVACY_CONTACT) == 1
    assert j["terms_more_p"].count(PRIVACY_CONTACT) == 1
    assert "10 November 2026" in j["legal_updated"] or "10 בנובמבר 2026" in j["legal_updated"] or "10 نوفمبر 2026" in j["legal_updated"]


def test_links_in_footer_settings_and_signup(client) -> None:
    reg = client.get("/login?mode=register").text
    assert 'class="lede tiny register-legal"' in reg
    assert 'href="/privacy"' in _main(reg) and 'href="/terms"' in _main(reg)
    assert _footer_links(client.get("/login").text) == ["/privacy", "/terms"]
    login(client, "legal-links@example.com", first_name="L", last_name="P")
    for url in ("/", "/settings"):
        assert _footer_links(client.get(url).text) == ["/privacy", "/terms"], url
    settings = _main(client.get("/settings").text)
    assert 'id="settings-legal"' in settings
    assert 'href="/privacy"' in settings and 'href="/terms"' in settings
