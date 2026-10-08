"""Step player (issue #56): answer without a reload, feedback under the choices.

- htmx requests (HX-Request: true) get only the step card back (+ the progress block out-of-band).
- Without JS the plain form post + 303 redirect keeps working, and the feedback still
  renders under the choices of the same step.
- Step text renders through the ``bdi`` filter so math reads right in Hebrew.
- The learner quote bar uses logical properties; targets are >= 24px; htmx is vendored.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login
from markupsafe import Markup

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app
from myroad_core.ui.bidi import MAX_WRAP_CHARS, bidi_isolate

_CORE = Path(__file__).resolve().parents[1]
_UI = _CORE / "src" / "myroad_core" / "ui"
_STATIC = _UI / "static"
HTMX_FILE = "htmx-2.0.11.min.js"

PID = "path_test_step_player"
HX = {"HX-Request": "true"}
MATH_HE = "כמה זה 5 − (−3)?"


def _path() -> dict:
    return {
        "id": PID, "subject": "math", "group_ids": ["adult"], "emoji": "➖", "estimated_minutes": 10,
        "titles": {"he": "מספרים שליליים", "en": "Negative numbers", "ar": "الأعداد السالبة"},
        "blurbs": {"he": "חיסור של מספר שלילי.", "en": "Subtracting a negative.", "ar": "طرح عدد سالب."},
        "topics": [{"id": "t1", "titles": {"he": "חיסור", "en": "Subtraction", "ar": "الطرح"},
                    "node_ids": ["l1", "p1", "c1", "end"]}],
        "nodes": [
            {"id": "l1", "type": "learn", "title": "הסבר", "body_he": "חיסור של מספר שלילי הוא חיבור.",
             "body_en": "Subtracting a negative number is adding."},
            {"id": "p1", "type": "practice", "title": "תרגול 1", "title_en": "Practice 1",
             "body_he": MATH_HE, "body_en": "What is 5 − (−3)?",
             "choices": [{"id": "a", "label": "2"}, {"id": "b", "label": "8"}, {"id": "c", "label": "−8"}],
             "correct": "b",
             "feedback_ok": "נכון! 5 − (−3) = 8.",
             "feedback_try": "מינוס של מינוס הוא פלוס: 5 + 3."},
            {"id": "c1", "type": "check", "title": "בדיקה", "body_he": "כמה זה 2 − (−2)?",
             "choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "0"}], "correct": "a",
             "feedback_ok": "מצוין! 2 + 2 = 4.", "feedback_try": "הפכו את המינוס הכפול לפלוס."},
            {"id": "end", "type": "celebrate", "title": "סוף", "body_he": "כל הכבוד"},
        ],
    }


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(_path(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "steps.db"))
    application = create_learner_app(store=store, seed=False, seed_content=True)
    yield application
    store.close()


def _client(app, locale: str = "he") -> TestClient:
    c = TestClient(app)
    c.cookies.set("myroad_locale", locale)
    login(c, f"noa-{locale}@example.com", first_name="Noa", last_name="Levi")
    c.cookies.set("myroad_locale", locale)
    return c


def _at_practice(app, locale: str = "he") -> TestClient:
    c = _client(app, locale)
    c.post(f"/play/{PID}/start")
    c.post(f"/play/{PID}/ack")  # learn -> practice
    return c


def _progress(app, c: TestClient) -> dict:
    store = app.state.store
    uid = store.get_session_user(c.cookies.get("myroad_session"))  # server-side session (#46)
    return store.get_progress(uid, PID) or {}


def _card(html: str) -> str:
    start = html.find('<section id="step-card"')
    assert start >= 0, "no step card"
    return html[start:html.find("</section>", start)]


def _text(html: str) -> str:
    return re.sub(r"</?bdi[^>]*>", "", html)


# --- htmx: partial responses -------------------------------------------------

def test_hx_wrong_answer_returns_only_the_step_card_with_feedback_under_choices(app) -> None:
    c = _at_practice(app)
    before = _progress(app, c)["nodeIndex"]
    r = c.post(f"/play/{PID}/answer", data={"choice": "a"}, headers=HX)
    assert r.status_code == 200
    body = r.text.strip()
    assert body.startswith('<section id="step-card"')
    assert "<html" not in body and "<!DOCTYPE" not in body and "<header" not in body
    assert "HX-Request" in r.headers.get("vary", "")
    card = _card(body)
    assert 'data-node-type="practice"' in card
    # Feedback sits right after the choices and before the nav, in a polite status region.
    i_form, i_fb, i_nav = card.index("</form>"), card.index('id="step-feedback"'), card.index('class="nav row')
    assert i_form < i_fb < i_nav
    fb = card[i_fb - 200:i_nav]
    assert 'role="status"' in fb and 'aria-live="polite"' in fb and 'tabindex="-1"' in fb
    assert "step-feedback try" in fb
    assert "מינוס של מינוס הוא פלוס" in fb  # the content's feedback_try explains the wrong pick
    assert "עוד לא." in fb and "בחרו תשובה אחרת." in fb
    # The tapped tile is marked (shape + text, not color alone) and points at the feedback.
    picked = re.search(r'<button[^>]*value="a"[^>]*>', card).group(0)
    assert "is-wrong" in picked and 'aria-describedby="step-feedback"' in picked
    assert "disabled" not in picked  # the learner can pick again
    # Focus moves to the feedback after the swap; the progress block comes out-of-band.
    assert 'data-swap-focus="step-feedback"' in card
    assert 'id="play-status" class="play-status" hx-swap-oob="true"' in body
    # Same step, nothing advanced.
    assert _progress(app, c)["nodeIndex"] == before


def test_hx_right_answer_shows_feedback_then_continue_swaps_next_step(app) -> None:
    c = _at_practice(app)
    r = c.post(f"/play/{PID}/answer", data={"choice": "b"}, headers=HX)
    card = _card(r.text)
    assert 'data-node-type="practice"' in card and "is-answered" in card
    right = re.search(r'<button[^>]*value="b"[^>]*>', card).group(0)
    assert "is-correct" in right and "disabled" in right
    assert "step-feedback ok" in card and "נכון." in card
    assert '<bdi dir="ltr">5 − (−3) = 8</bdi>' in card  # feedback goes through the bdi filter
    # The session already moved on; the learner continues when ready.
    assert _progress(app, c)["nodeIndex"] == 2
    cont = re.search(r'<a class="primary big continue-step"[^>]*>', card).group(0)
    assert f'href="/play/{PID}?view=learn"' in cont and f'hx-get="/play/{PID}?view=learn"' in cont
    assert 'hx-target="#step-card"' in cont
    assert 'class="nav row">' not in card  # prev/next would skip around the answered step
    # The page-top flash is not left behind for the next full load.
    assert "flash ok" not in c.get(f"/play/{PID}?view=learn").text

    nxt = c.get(f"/play/{PID}?view=learn", headers=HX)
    assert nxt.text.strip().startswith('<section id="step-card"')
    ncard = _card(nxt.text)
    assert 'data-node-type="check"' in ncard and 'data-swap-focus="step-title"' in ncard
    assert 'id="step-title" tabindex="-1"' in ncard


def test_hx_last_answer_continues_to_the_summary_as_a_full_page(app) -> None:
    c = _at_practice(app)
    # Everything but the practice step is mastered, so a right answer finishes the path.
    sess = next(s for s in app.state.play_sessions.values() if s["pathId"] == PID)
    blocks = app.state.tools.get_version(actor_id="t", correlation_id="t", path_id=PID,
                                         version_id=sess["versionId"]).data["document"]["blocks"]
    sess["mastered"] = {b["blockId"] for b in blocks if b["blockId"] != blocks[1]["blockId"]}
    r = c.post(f"/play/{PID}/answer", data={"choice": "b"}, headers=HX)
    assert 'data-node-type="practice"' in _card(r.text)
    cont = re.search(r'<a class="primary big continue-step"[^>]*>', r.text).group(0)
    assert f'href="/play/{PID}?view=stats"' in cont and "hx-get" not in cont
    assert "stats-card" in c.get(f"/play/{PID}?view=stats").text


def test_hx_get_of_a_non_learn_view_asks_for_a_full_navigation(app) -> None:
    c = _client(app)
    r = c.get(f"/play/{PID}?view=map", headers=HX)
    assert r.status_code == 200 and r.headers.get("HX-Redirect") == f"/play/{PID}"
    assert r.text == ""


# --- no JS: the plain form post still works -------------------------------------

def test_no_js_wrong_answer_redirects_and_shows_feedback_under_choices_once(app) -> None:
    c = _at_practice(app)
    r = c.post(f"/play/{PID}/answer", data={"choice": "c"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"/play/{PID}?view=learn#step-feedback"
    page = c.get(r.headers["location"].split("#")[0])
    assert page.text.lstrip().startswith("<!DOCTYPE html>")
    assert '<form method="post" action="/play/%s/answer"' % PID in page.text  # real post target
    card = _card(page.text)
    assert card.index("</form>") < card.index('id="step-feedback"') < card.index('class="nav row')
    assert "מינוס של מינוס הוא פלוס" in card
    assert "is-wrong" in re.search(r'<button[^>]*value="c"[^>]*>', card).group(0)
    assert "data-swap-focus" not in page.text  # only htmx swaps move focus
    assert 'class="flash warn"' not in page.text  # no page-top duplicate
    # One-time: a reload shows a clean step.
    again = _card(c.get(f"/play/{PID}?view=learn").text)
    assert "מינוס של מינוס" not in again and "is-wrong" not in again


def test_no_js_right_answer_still_goes_to_the_next_step(app) -> None:
    c = _at_practice(app)
    r = c.post(f"/play/{PID}/answer", data={"choice": "b"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/play/{PID}?view=learn"
    page = c.get(r.headers["location"]).text
    assert 'data-node-type="check"' in _card(page)
    assert 'class="flash ok"' in page and '<bdi dir="ltr">5 − (−3) = 8</bdi>' in page


def test_full_page_loads_vendored_htmx_only_on_the_player(app) -> None:
    c = _at_practice(app)
    page = c.get(f"/play/{PID}?view=learn").text
    assert f'<script src="/static/{HTMX_FILE}"></script>' in page
    assert not re.search(r'<script[^>]+src="(https?:)?//', page)  # no CDN at runtime
    assert '"allowEval": false' in page
    form = re.search(r'<form method="post" action="/play/[^"]+/answer" class="choices"[^>]*>', page).group(0)
    assert 'hx-post="/play/%s/answer"' % PID in form and 'hx-target="#step-card"' in form
    assert 'hx-swap="outerHTML"' in form
    js = c.get(f"/static/{HTMX_FILE}")
    assert js.status_code == 200 and "htmx" in js.text[:200]
    assert HTMX_FILE not in c.get("/").text


# --- locales and direction ---------------------------------------------------------

@pytest.mark.parametrize(
    ("locale", "direction", "verdict", "label"),
    [("he", "rtl", "עוד לא.", "תרגול 1"), ("en", "ltr", "Not yet.", "Practice 1"), ("ar", "rtl", "ليس بعد.", None)],
)
def test_feedback_follows_ui_locale_and_direction(app, locale, direction, verdict, label) -> None:
    c = _at_practice(app, locale)
    full = c.get(f"/play/{PID}?view=learn").text
    assert f'dir="{direction}"' in full[:200]
    r = c.post(f"/play/{PID}/answer", data={"choice": "a"}, headers=HX)
    assert verdict in _card(r.text)
    if locale == "en":
        assert "What is 5 − (−3)?" in r.text and label in r.text  # English prose stays unwrapped
    elif locale == "he":
        assert label in _text(r.text)


def test_step_text_goes_through_the_bdi_filter_and_stays_escaped(app, tmp_path: Path) -> None:
    c = _at_practice(app)
    card = _card(c.get(f"/play/{PID}?view=learn").text)
    assert 'כמה זה <bdi dir="ltr">5 − (−3)</bdi>?' in card
    assert '<span class="choice-label" dir="auto"><bdi dir="ltr">−8</bdi></span>' in card
    assert 'id="step-title" tabindex="-1" dir="auto">תרגול <bdi dir="ltr">1</bdi></h2>' in card
    # TTS source stays plain text (attribute, no markup).
    assert f'data-speak="{MATH_HE}"' in card


def test_markup_in_step_text_is_escaped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = _path()
    doc["nodes"][1]["body_he"] = 'שאלה <img src=x onerror="alert(1)"> 3 + 4'
    doc["nodes"][1]["choices"][0]["label"] = "<b>2</b>"
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    (content / f"{PID}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "x.db"))
    try:
        c = _at_practice(create_learner_app(store=store, seed=False, seed_content=True))
        card = _card(c.get(f"/play/{PID}?view=learn").text)
        assert "<img" not in card and "<b>2</b>" not in card
        assert "&lt;img" in card and "&lt;b&gt;" in card
        assert '<bdi dir="ltr">3 + 4</bdi>' in card
    finally:
        store.close()


# --- the bdi filter --------------------------------------------------------------------

def test_bdi_wraps_math_numbers_and_latin_runs_in_rtl_text() -> None:
    assert bidi_isolate(MATH_HE) == 'כמה זה <bdi dir="ltr">5 − (−3)</bdi>?'
    assert bidi_isolate("1,000 − 367 = ?") == '<bdi dir="ltr">1,000 − 367 = ?</bdi>'
    assert bidi_isolate("נכון! Red = אדום.") == 'נכון! <bdi dir="ltr">Red</bdi> = אדום.'
    assert bidi_isolate("x² − 5x + 6 = 0 היא משוואה") == '<bdi dir="ltr">x² − 5x + 6 = 0</bdi> היא משוואה'
    # A list of numbers keeps RTL order: each number is its own run.
    assert bidi_isolate("המספרים 5, 6") == 'המספרים <bdi dir="ltr">5</bdi>, <bdi dir="ltr">6</bdi>'
    # A hyphen glued to a Hebrew prefix letter is a connector, not a minus.
    assert bidi_isolate("ו-7") == 'ו-<bdi dir="ltr">7</bdi>'
    assert bidi_isolate("−8") == '<bdi dir="ltr">−8</bdi>'  # bare math label
    assert bidi_isolate("12 − 4 = 8 بالضبط") == '<bdi dir="ltr">12 − 4 = 8</bdi> بالضبط'


def test_bdi_escapes_before_marking_safe() -> None:
    raw = bidi_isolate('<script>alert("x")</script> כמה זה 3 & 4?')
    assert isinstance(raw, Markup)
    out = str(raw)
    assert "<script" not in out and "</script" not in out and "&lt;" in out
    assert "&amp;" in out and ("&#34;" in out or "&quot;" in out)
    # Escaping happens per piece after matching, so entities are never split by a <bdi>.
    assert not re.search(r"&[#\w]*<bdi", out) and not re.search(r"&#<", out)
    # Markup input is treated as text too.
    assert bidi_isolate(Markup("<ש>שלום 3")) == '&lt;ש&gt;שלום <bdi dir="ltr">3</bdi>'
    assert bidi_isolate(None) == "" and bidi_isolate(42) == '<bdi dir="ltr">42</bdi>'


def test_bdi_leaves_english_prose_alone_and_bounds_long_input() -> None:
    assert bidi_isolate("What is 5 − (−3)?") == "What is 5 − (−3)?"
    assert bidi_isolate("Tom & Jerry") == "Tom &amp; Jerry"
    long_text = "מילה 5 " * (MAX_WRAP_CHARS // 4)
    out = bidi_isolate(long_text + "<i>")
    assert "<bdi" not in out and out.endswith("&lt;i&gt;")


def test_bdi_filter_is_registered_and_autoescape_is_on(app) -> None:
    from myroad_core.ui.app import TEMPLATES

    env = TEMPLATES.env
    assert env.filters["bdi"] is bidi_isolate
    tpl = env.from_string("{{ x|bdi }} | {{ x }}")
    assert tpl.render(x='<ש> 5 − 3 & "ק"') == (
        '&lt;ש&gt; <bdi dir="ltr">5 − 3</bdi> &amp; &#34;ק&#34; | &lt;ש&gt; 5 − 3 &amp; &#34;ק&#34;'
    )


# --- CSS: quote bar, target size, motion ------------------------------------------------

def _rule(css: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, selector
    return m.group(1)


def test_learner_quote_bar_uses_logical_properties() -> None:
    css = (_STATIC / "learner.css").read_text(encoding="utf-8")
    shell = _rule(css, ".shell")
    assert "border-inline-start:" in shell and "padding-inline-start:" in shell
    assert not re.search(r"(border|padding|margin)-(left|right)\b", css)


def test_step_player_targets_and_reduced_motion() -> None:
    css = (_STATIC / "platform.css").read_text(encoding="utf-8")
    m = re.search(r"\.play \.choice-tile,[^{]*\{([^}]*)\}", css)
    assert m and "min-block-size: 44px" in m.group(1) and "min-inline-size: 44px" in m.group(1)
    for sel in (".play .nav button", ".play .step-card .primary", ".play .icon-btn"):
        assert sel in css[m.start():m.end()]
    assert re.search(r"\.play \.shell-top \.back,[^{]*\{[^}]*min-block-size: 24px", css)
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (prefers-reduced-motion: no-preference)" in css
    # The new step-player block keeps to logical properties too.
    block = css[css.index("/* --- Step player (#56)"):]
    assert not re.search(r"(border|padding|margin)-(left|right)\b|[^-]\b(left|right):", block)


def test_new_locale_keys_exist_in_he_en_ar() -> None:
    keys = {"feedback_correct", "feedback_not_yet", "feedback_pick_again", "next_step"}
    for code in ("he", "en", "ar"):
        data = json.loads((_CORE / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        assert keys <= set(data), code
        assert all(data[k].strip() for k in keys)
