"""Content-text fallback order (#58, MyRoad PM scope).

When a content string (path title/blurb, station title, step title/body, choices,
feedback) is missing in the UI locale, the view layer falls back to the path's own
language (``explain_locale``; Hebrew for adult paths), not to English, and marks the
fallback text with ``lang=<explain_locale>`` next to ``dir="auto"`` (the #57/#68 approach).
UI chrome (``pick``) and callers outside the view layer keep the manifest chain.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient

from myroad_core.content.loader import default_content_dir
from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app
from myroad_core.ui.i18n import content_lang, localize_path_chrome, pick, pick_content

HE_ONLY = "path_test_he_only"
HE_LOCKED = "path_test_he_only_locked"
BAGRUT = "path_math_bagrut_3_units"


# --- unit: pick_content / content_lang / localize_path_chrome -----------------------------

def test_pick_content_prefers_ui_then_path_language_then_anything() -> None:
    both = {"he": "שלום", "en": "Hello"}
    assert pick_content(both, "ar", source_locale="he") == ("שלום", "he")
    assert pick_content(both, "en", source_locale="he") == ("Hello", "en")
    assert pick_content(both, "he", source_locale="he") == ("שלום", "he")
    # An English-explained path falls back to English, its own language.
    assert pick_content(both, "ar", source_locale="en") == ("Hello", "en")
    # Unknown source → platform default (he); then whatever exists.
    assert pick_content(both, "ar") == ("שלום", "he")
    assert pick_content({"en": "Only"}, "ar", source_locale="he") == ("Only", "en")
    assert pick_content({"fr": "Salut"}, "ar", source_locale="he") == ("Salut", "fr")
    assert pick_content({"he": "  ", "en": ""}, "ar", default="x", default_lang="he") == ("x", "he")
    assert pick_content(None, "en") == ("", None)
    # UI chrome keeps its manifest chain (en first) — only content changed.
    assert pick(both, "ar") == "Hello"


def test_content_lang_marks_only_other_language_text() -> None:
    assert str(content_lang("he", "en")) == ' lang="he"'
    assert str(content_lang("he", "ar")) == ' lang="he"'
    assert str(content_lang("he", "he")) == ""
    assert str(content_lang("", "en")) == "" and str(content_lang(None, "en")) == ""
    assert str(content_lang('he" onload="x', "en")) == ""  # never emits an unsafe attribute
    assert str(content_lang("he", "en", "2")) == ""  # a bare number has no language
    assert str(content_lang("he", "en", "x = 2")) == ' lang="he"'


def test_localize_path_chrome_uses_source_locale_and_keeps_legacy_without_it() -> None:
    titles, blurbs = {"he": "מתמטיקה", "en": "Math"}, {"he": "תיאור"}
    out = localize_path_chrome(locale="ar", titles=titles, blurbs=blurbs, source_locale="he")
    assert (out["title"], out["titleLang"], out["blurb"], out["blurbLang"]) == ("מתמטיקה", "he", "תיאור", "he")
    # No source locale (content loader / JSON API callers): unchanged, English-first.
    legacy = localize_path_chrome(locale="ar", titles=titles, blurbs=blurbs)
    assert (legacy["title"], legacy["titleLang"]) == ("Math", "en")


# --- synthetic adult path with Hebrew-only content ----------------------------------------

def _he_only(pid: str = HE_ONLY, **extra) -> dict:
    doc = {
        "id": pid, "subject": "math", "group_ids": ["adult"], "emoji": "📐", "estimated_minutes": 10,
        "titles": {"he": "שברים למבוגרים"}, "blurbs": {"he": "מסלול בעברית בלבד."},
        "topics": [{"id": "t1", "titles": {"he": "תחנת שברים"}, "node_ids": ["n1", "n2"]}],
        "nodes": [
            {"id": "n1", "type": "learn", "title": "מה זה שבר", "body_he": "שבר הוא חלק מהשלם."},
            {"id": "n2", "type": "practice", "title": "תרגול שבר", "body_he": "כמה זה חצי ועוד חצי?",
             "choices": [{"id": "a", "label": "שלם אחד"}, {"id": "b", "label": "2"}], "correct": "a",
             "feedback_ok": "נכון, שני חצאים הם שלם.", "feedback_try": "נסו שוב: חצי ועוד חצי."},
        ],
    }
    doc.update(extra)
    return doc


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    locked = _he_only(HE_LOCKED, titles={"he": "המשך שברים"}, prerequisite_path_ids=[HE_ONLY])
    for doc in (_he_only(), locked):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "fb.db"))
    yield create_learner_app(store=store, seed=False, seed_content=True)
    store.close()


def _client(app, locale: str) -> TestClient:
    c = TestClient(app)
    c.cookies.set("myroad_locale", locale)
    c.post("/login", data={"first_name": "Fb", "last_name": "User", "email": f"fb-{locale}@example.com", "next": "/"})
    c.cookies.set("myroad_locale", locale)
    return c


def _attrs(html: str, text: str) -> str:
    """The opening tag of the innermost element (in <body>) whose text starts with ``text``."""
    body = html.find("<body")
    i = html.index(text, max(body, 0))
    start = html.rfind("<", 0, i)
    return html[start:html.index(">", start) + 1]


@pytest.mark.parametrize("locale", ["en", "ar"])
def test_he_only_path_falls_back_to_hebrew_marked_lang_he(app, locale) -> None:
    c = _client(app, locale)
    home = c.get("/").text
    for text in ("שברים למבוגרים", "מסלול בעברית בלבד."):
        tag = _attrs(home, text)
        assert 'dir="auto"' in tag and 'lang="he"' in tag, (text, tag)
    lock = _attrs(home, "שברים למבוגרים</bdi>") if "שברים למבוגרים</bdi>" in home else ""
    assert lock.startswith("<bdi") and 'lang="he"' in lock

    c.post(f"/play/{HE_ONLY}/start")
    page = c.get(f"/play/{HE_ONLY}?view=map").text
    for text in ("שברים למבוגרים", "מסלול בעברית בלבד.", "תחנת שברים"):
        tag = _attrs(page, text)
        assert 'dir="auto"' in tag and 'lang="he"' in tag, (text, tag)

    play = c.get(f"/play/{HE_ONLY}?view=learn").text
    for text in ("מה זה שבר", "שבר הוא חלק מהשלם."):
        tag = _attrs(play, text)
        assert 'dir="auto"' in tag and 'lang="he"' in tag, (text, tag)
    station_name = re.search(r'<span class="station-name"[^>]*>', play).group(0)
    assert 'lang="he"' in station_name

    c.post(f"/play/{HE_ONLY}/ack")
    play = c.get(f"/play/{HE_ONLY}?view=learn").text
    assert 'lang="he"' in _attrs(play, "שלם אחד")
    assert 'lang="he"' not in _attrs(play, "2</")  # numeric choice: no language to switch to
    after = c.post(f"/play/{HE_ONLY}/answer", data={"choice": "b"}, headers={"HX-Request": "true"}).text
    fb = _attrs(after, "נסו שוב")
    assert 'dir="auto"' in fb and 'lang="he"' in fb

    locked = c.get(f"/play/{HE_LOCKED}").text
    tag = _attrs(locked, "שברים למבוגרים</bdi>")
    assert tag.startswith("<bdi") and 'lang="he"' in tag


def test_he_ui_marks_nothing(app) -> None:
    c = _client(app, "he")
    c.post(f"/play/{HE_ONLY}/start")
    for url in ("/", f"/play/{HE_ONLY}?view=map", f"/play/{HE_ONLY}?view=learn"):
        assert 'lang="he"' not in c.get(url).text.split("<body", 1)[1], url


# --- real content: path_math_bagrut_3_units (he+en titles, no ar; Hebrew-only steps) -----

@pytest.fixture
def bagrut_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = default_content_dir()
    if not (Path(root) / "adult" / f"{BAGRUT}.json").is_file():
        pytest.skip("path_math_bagrut_3_units not in CONTENT_DIR")
    monkeypatch.setenv("CONTENT_DIR", str(root))
    store = PathStore(str(tmp_path / "bagrut.db"))
    yield create_learner_app(store=store, seed=False, seed_content=True)
    store.close()


def _bagrut_topics() -> list[dict]:
    doc = json.loads((Path(default_content_dir()) / "adult" / f"{BAGRUT}.json").read_text(encoding="utf-8"))
    return doc["topics"]


def test_bagrut_ar_station_titles_fall_back_to_hebrew_not_english(bagrut_app) -> None:
    topics = _bagrut_topics()
    assert not any(t["titles"].get("ar") for t in topics)  # precondition of this test
    c = _client(bagrut_app, "ar")
    c.post(f"/play/{BAGRUT}/start")
    page = c.get(f"/play/{BAGRUT}?view=map").text
    for t in topics:
        assert t["titles"]["en"] not in page, t["id"]
        assert t["titles"]["he"] in page, t["id"]
    stations = re.findall(r'<span class="station-title"([^>]*)>', page)
    assert len(stations) == len(topics)
    assert all('dir="auto"' in s and 'lang="he"' in s for s in stations)
    h1 = _attrs(page, "מתמטיקה 3 יחידות")
    assert 'lang="he"' in h1 and "Math 3 units" not in page.split("<main", 1)[-1]
    home = c.get("/?group=adult").text
    assert 'lang="he"' in _attrs(home, "מתמטיקה 3 יחידות")


def test_bagrut_en_uses_english_titles_and_marks_hebrew_only_steps(bagrut_app) -> None:
    topics = _bagrut_topics()
    c = _client(bagrut_app, "en")
    c.post(f"/play/{BAGRUT}/start")
    page = c.get(f"/play/{BAGRUT}?view=map").text
    stations = re.findall(r'<span class="station-title"([^>]*)>', page)
    assert len(stations) == len(topics)
    assert all('lang=' not in s for s in stations)  # English exists, shown as-is
    for t in topics:
        assert t["titles"]["en"] in page
    step_rows = re.findall(r'<span class="step-title" dir="auto"([^>]*)>', page)
    assert step_rows and all('lang="he"' in s for s in step_rows)  # step titles are Hebrew-only
    play = c.get(f"/play/{BAGRUT}?view=learn").text
    assert re.search(r'<h2 id="step-title" tabindex="-1" dir="auto" lang="he">', play)
