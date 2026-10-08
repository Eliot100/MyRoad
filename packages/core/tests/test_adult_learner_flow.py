"""Learner flow on long adult paths (issue #44).

Locked prerequisites (read-only), review steps, station progress on a 20+ station map,
"continue" resuming the last step, and the adult group on home. The synthetic paths use
only schema v2 fields (docs/vision/06-content-format.md); the last tests run on the real
MyRoad-content adult math paths when they are in CONTENT_DIR.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient

from myroad_core.content.loader import default_content_dir, load_content_paths
from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app

_CORE = Path(__file__).resolve().parents[1]
_LOCALES = _CORE / "locales"
_CSS = _CORE / "src" / "myroad_core" / "ui" / "static" / "platform.css"

LONG = "path_test_adult_long"
NEXT = "path_test_adult_next"
N_TOPICS = 22  # regular topics; every 5th one is a mixed review station
EMAIL = "adult@example.com"


def _long_path() -> dict:
    topics, nodes = [], []
    regular: list[str] = []
    for i in range(N_TOPICS):
        tid = f"t{i:02d}"
        if i and i % 5 == 0:
            mixes = regular[-2:]
            nid = f"rev{i:02d}"
            topics.append({"id": tid, "titles": {"he": f"חזרה מעורבת {i}", "en": f"Mixed review {i}"},
                           "emoji": "🔁", "node_ids": [nid]})
            nodes.append({"id": nid, "type": "practice", "kind": "review", "review_topic_ids": mixes,
                          "title": f"חזרה {i}", "body_he": "כמה זה 2+2?",
                          "choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "5"}], "correct": "a"})
            continue
        learn, prac = f"l{i:02d}", f"p{i:02d}"
        topics.append({"id": tid, "titles": {"he": f"נושא {i}", "en": f"Topic {i}"}, "node_ids": [learn, prac]})
        nodes.append({"id": learn, "type": "learn", "title": f"הסבר {i}", "body_he": f"הסבר על נושא {i}"})
        nodes.append({"id": prac, "type": "practice", "kind": "understanding", "title": f"תרגול {i}",
                      "body_he": "כמה זה 1+1?",
                      "choices": [{"id": "a", "label": "2"}, {"id": "b", "label": "3"}], "correct": "a"})
        regular.append(tid)
    return {
        "id": LONG, "subject": "math", "group_ids": ["adult"], "emoji": "🧮", "estimated_minutes": 600,
        "titles": {"he": "מתמטיקה ארוכה למבוגרים", "en": "Long adult math", "ar": "رياضيات طويلة للبالغين"},
        "blurbs": {"he": "דרך ארוכה לבדיקה.", "en": "A long test path.", "ar": "مسار طويل للاختبار."},
        "topics": topics, "nodes": nodes,
    }


def _next_path() -> dict:
    return {
        "id": NEXT, "subject": "math", "group_ids": ["adult"], "emoji": "📈", "estimated_minutes": 120,
        "prerequisite_path_ids": [LONG],
        "titles": {"he": "הדרך הבאה", "en": "The next path", "ar": "المسار التالي"},
        "blurbs": {"he": "נפתחת אחרי הדרך הארוכה.", "en": "Opens after the long path.", "ar": "يُفتح بعد المسار الطويل."},
        "topics": [
            {"id": "a1", "titles": {"he": "פתיחה", "en": "Opening"}, "node_ids": ["x1", "x2"]},
            {"id": "a2", "titles": {"he": "המשך", "en": "Going on"}, "node_ids": ["x3"]},
        ],
        "nodes": [
            {"id": "x1", "type": "learn", "title": "הסבר", "body_he": "הסבר קצר"},
            {"id": "x2", "type": "practice", "title": "תרגול", "body_he": "כמה זה 3+3?",
             "choices": [{"id": "a", "label": "6"}, {"id": "b", "label": "7"}], "correct": "a"},
            {"id": "x3", "type": "celebrate", "title": "סוף", "body_he": "כל הכבוד"},
        ],
    }


@pytest.fixture
def adult_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_long_path(), _next_path()):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "adult.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    yield app, store
    store.close()


def _client(app, *, locale: str = "en", email: str = EMAIL) -> TestClient:
    c = TestClient(app)
    c.cookies.set("myroad_locale", locale)
    c.post("/login", data={"first_name": "Dana", "last_name": "Cohen", "email": email, "next": "/"})
    c.cookies.set("myroad_locale", locale)
    return c


def _user_id(store: PathStore, email: str = EMAIL) -> str:
    return store.get_learner_by_email(email)["userId"]


def _step_card(html: str) -> str:
    start = html.find('class="card step-card')
    assert start >= 0, "no step card"
    return html[start:html.find("</section>", start)]


def _finish(store: PathStore, user_id: str, path_id: str) -> None:
    store.save_progress(user_id, path_id, version_id=None, node_index=0, mastered=set(),
                        correct_taps=0, incorrect_taps=0, completed_at="2026-01-01T00:00:00+00:00")


# --- map: 20+ stations, compact and with progress per station ---

def test_long_map_is_a_compact_station_list_with_progress(adult_app) -> None:
    app, _store = adult_app
    c = _client(app)
    page = c.get(f"/play/{LONG}")
    assert page.status_code == 200
    html = page.text
    assert 'class="station-list" data-stations="22"' in html
    assert html.count('<li class="station ') == N_TOPICS
    assert "topic-diagram" not in html  # the big one-box-per-topic diagram is for short paths
    assert html.count("<details") == N_TOPICS and html.count("<details open") == 1
    assert "Station 1 of 22" in html and "0 of 22 stations done" in html
    assert html.count('class="mini-bar"') == N_TOPICS

    # Finish the first station (learn + practice), then the map shows it done and opens the next.
    c.post(f"/play/{LONG}/start")
    c.post(f"/play/{LONG}/ack")
    c.post(f"/play/{LONG}/answer", data={"choice": "a"})
    html = c.get(f"/play/{LONG}?view=map").text
    first = html[html.find('data-topic-id="t00"') - 40:html.find('data-topic-id="t01"')]
    assert 'class="station done' in first and "2/2 steps" in first and 'aria-valuenow="100"' in first
    second = html[html.find('data-topic-id="t01"') - 60:html.find('data-topic-id="t02"')]
    assert "station current" in second and "<details open" in second and "0/2 steps" in second
    assert "Station 2 of 22" in html and "1 of 22 stations done" in html
    # Steps inside a station are listed with their state.
    assert first.count('class="step-row done') == 2


def test_short_paths_keep_the_topic_diagram(adult_app) -> None:
    app, store = adult_app
    c = _client(app)
    _finish(store, _user_id(store), LONG)
    html = c.get(f"/play/{NEXT}").text
    assert "topic-diagram" in html and "station-list" not in html
    assert html.count('class="mini-bar"') == 2


# --- review steps ---

def test_review_step_has_badge_and_lists_mixed_topics(adult_app) -> None:
    app, _store = adult_app
    c = _client(app)
    page = c.get(f"/play/{LONG}?topic=t05")
    card = _step_card(page.text)
    assert 'data-step-kind="review"' in card
    assert '<span class="review-badge">Review</span>' in card
    assert "This review mixes:" in card
    chips = re.findall(r'class="review-topic-chip" data-topic-id="([^"]+)">\s*([^<]*)<', card)
    assert [cid for cid, _ in chips] == ["t03", "t04"]
    assert "Topic 3" in chips[0][1] and "Topic 4" in chips[1][1]
    assert "Station 6 of 22" in page.text

    plain = _step_card(c.get(f"/play/{LONG}?topic=t01").text)
    assert 'data-step-kind="understanding"' in plain
    assert "review-badge" not in plain and "review-topic-chip" not in plain

    # Review stations are marked on the map too.
    html = c.get(f"/play/{LONG}?view=map").text
    start = html.rfind('<li class="station', 0, html.find('data-topic-id="t05"'))
    station = html[start:html.find('data-topic-id="t06"')]
    assert station.split(">", 1)[0].split('"')[1].split()[-1] == "review" and "review-badge" in station


@pytest.mark.parametrize("locale,word", [("he", "חזרה"), ("ar", "مراجعة")])
def test_review_badge_is_localized_and_rtl(adult_app, locale: str, word: str) -> None:
    app, _store = adult_app
    c = _client(app, locale=locale)
    page = c.get(f"/play/{LONG}?topic=t10")
    assert 'dir="rtl"' in page.text
    assert f'<span class="review-badge">{word}</span>' in _step_card(page.text)


# --- locked prerequisites (read-only) ---

def test_locked_path_names_the_prerequisite_on_home_and_map(adult_app) -> None:
    app, _store = adult_app
    c = _client(app)
    home = c.get("/?group=adult&tab=catalog&view=status").text
    card = home[home.find(f'data-path-id="{NEXT}"'):]
    card = card[:card.find("</a>")]
    assert "🔒 Locked" in card and f'data-locked-by="{LONG}"' in card and "Long adult math" in card
    unlocked = home[home.find(f'data-path-id="{LONG}"'):]
    assert "status-pill locked" not in unlocked[:unlocked.find("</a>")]

    page = c.get(f"/play/{NEXT}")
    assert page.status_code == 200
    assert "lock-banner" in page.text and "This path is still locked" in page.text
    assert f'<a class="lock-link" href="/play/{LONG}"><bdi>Long adult math</bdi></a>' in page.text
    # Still openable, read-only: links instead of start forms.
    assert f'href="/play/{NEXT}?topic=a1"' in page.text and "Look inside (read-only)" in page.text
    assert f'action="/play/{NEXT}/start"' not in page.text


def test_locked_path_opens_read_only_and_never_writes_progress(adult_app) -> None:
    app, store = adult_app
    c = _client(app)
    uid = _user_id(store)

    learn = c.get(f"/play/{NEXT}?view=learn").text
    assert "read-only" in learn and "Read-only" in learn
    assert f'action="/play/{NEXT}/ack"' not in learn and f'action="/play/{NEXT}/answer"' not in learn

    started = c.post(f"/play/{NEXT}/start", data={"topic": "a1"})
    assert started.status_code == 200
    nav = c.post(f"/play/{NEXT}/nav", data={"direction": "next"})  # no mastery gate in read-only
    card = _step_card(nav.text)
    assert 'data-node-type="practice"' in card
    assert "read-only-choices" in card and "<form" not in card.split('class="nav row"')[0]

    for url, data in ((f"/play/{NEXT}/answer", {"choice": "a"}), (f"/play/{NEXT}/ack", {})):
        resp = c.post(url, data=data)
        assert resp.status_code == 200
        assert "finish the earlier path first" in resp.text
    assert store.get_progress(uid, NEXT) is None
    assert all(r["pathId"] != NEXT for r in store.list_user_progress(uid))

    # Finishing the prerequisite unlocks it: answers count again.
    _finish(store, uid, LONG)
    page = c.get(f"/play/{NEXT}?view=map").text
    assert "lock-banner" not in page and f'action="/play/{NEXT}/start"' in page
    c.post(f"/play/{NEXT}/start", data={"topic": "a1"})
    c.post(f"/play/{NEXT}/ack")
    c.post(f"/play/{NEXT}/answer", data={"choice": "a"})
    assert len(store.get_progress(uid, NEXT)["mastered"]) == 2


def test_finishing_a_path_shows_what_it_unlocked(adult_app) -> None:
    app, store = adult_app
    c = _client(app)
    _finish(store, _user_id(store), LONG)
    # Play the (now open) next path to the end.
    c.post(f"/play/{NEXT}/start")
    c.post(f"/play/{NEXT}/ack")
    c.post(f"/play/{NEXT}/answer", data={"choice": "a"})
    done = c.post(f"/play/{NEXT}/ack")
    assert "stats-card" in done.text
    assert "unlocked-next" not in done.text  # nothing requires NEXT

    c2 = _client(app, email="second@example.com")
    uid2 = _user_id(store, "second@example.com")
    store.save_progress(uid2, LONG, version_id=None, node_index=0, mastered=set(), correct_taps=0, incorrect_taps=0)
    # Pretend everything but the last step is mastered, then finish it through the UI.
    sess_html = c2.get(f"/play/{LONG}?view=map").text
    assert "station-list" in sess_html
    sess = next(s for s in app.state.play_sessions.values() if s["userId"] == uid2)
    doc = app.state.tools.get_version(actor_id="t", correlation_id="t", path_id=LONG, version_id=sess["versionId"]).data["document"]
    blocks = doc["blocks"]
    sess["mastered"] = {b["blockId"] for b in blocks[:-1]}
    sess["index"] = len(blocks) - 1
    final = c2.post(f"/play/{LONG}/answer", data={"choice": "a"})
    assert "stats-card" in final.text
    assert "unlocked-next" in final.text and f'href="/play/{NEXT}"' in final.text


# --- home: adult group + continue ---

def test_home_shows_adult_group_and_continue_resumes_last_step(adult_app) -> None:
    app, store = adult_app
    c = _client(app)
    c.post(f"/play/{LONG}/start")
    c.post(f"/play/{LONG}/ack")                      # step 1 (learn)
    c.post(f"/play/{LONG}/answer", data={"choice": "a"})  # step 2 (practice)
    c.post(f"/play/{LONG}/ack")                      # step 3 (learn, topic 1)
    assert store.get_progress(_user_id(store), LONG)["nodeIndex"] == 3

    # A new browser session for the same learner: home lands on the adult group.
    fresh = _client(app)
    home = fresh.get("/").text
    assert re.search(r'class="chip active" href="/\?group=adult&', home)
    assert "Adults starting from zero" in home
    assert "continue-card" in home
    assert 'data-step="4"' in home and "Step 4 of" in home and "Topic 1" in home
    href = re.search(r'class="primary big continue-btn" href="([^"]+)"', home).group(1)
    assert href == f"/play/{LONG}?view=learn"

    resumed = fresh.get(href)
    card = _step_card(resumed.text)
    assert 'data-node-type="practice"' in card and "תרגול 1" in card
    assert "Step 4 of" in resumed.text

    # An explicit group choice still wins.
    assert re.search(r'class="chip active" href="/\?group=grade3&', fresh.get("/?group=grade3").text)


def test_home_without_progress_keeps_default_group(adult_app) -> None:
    app, _store = adult_app
    c = _client(app, email="new@example.com")
    home = c.get("/").text
    assert "continue-card" not in home
    # No grade3 paths in this catalog: falls back to all groups, adult cards visible.
    assert f'data-path-id="{LONG}"' in home and f'data-path-id="{NEXT}"' in home


# --- strings + CSS ---

NEW_KEYS = (
    "locked_badge", "locked_title", "locked_finish_first", "locked_read_only", "read_only_badge",
    "read_only_open", "read_only_blocked", "review_mixes", "station_of", "stations_done",
    "map_long_lede", "station_current", "continue_step", "unlocked_next", "builder_match_why",
)


def test_new_strings_exist_in_every_locale() -> None:
    packs = {c: json.loads((_LOCALES / f"{c}.json").read_text(encoding="utf-8")) for c in ("he", "en", "ar")}
    assert set(packs["he"]) == set(packs["en"]) == set(packs["ar"])
    for key in NEW_KEYS:
        for code, pack in packs.items():
            assert pack.get(key, "").strip(), (code, key)
        placeholders = {code: set(re.findall(r"{(\w+)}", pack[key])) for code, pack in packs.items()}
        assert placeholders["he"] == placeholders["en"] == placeholders["ar"], key


def test_new_css_is_logical_and_has_a_phone_layout() -> None:
    css = _CSS.read_text(encoding="utf-8")
    block = css.split("/* --- Long adult paths (issue #44)", 1)[1]
    assert re.search(r"(?<![\w-])(left|right)\s*:", block) is None
    assert "margin-left" not in block and "margin-right" not in block
    assert "padding-left" not in block and "padding-right" not in block
    assert "@media (max-width: 480px)" in block
    assert 'html[dir="ltr"] .back .back-arrow' in css  # only the arrow flips, not the link text


# --- real content: math from zero (19 stations) and the 3-unit path ---

ZERO = "path_math_zero_to_equation"
BAGRUT = "path_math_bagrut_3_units"


def _real_ids() -> set[str]:
    try:
        return {p.id for p in load_content_paths(default_content_dir())}
    except Exception:
        return set()


@pytest.mark.skipif(not {ZERO, BAGRUT} <= _real_ids(), reason="MyRoad-content adult math paths not in CONTENT_DIR")
def test_real_adult_math_paths(tmp_path: Path) -> None:
    store = PathStore(str(tmp_path / "real.db"))
    app = create_learner_app(store=store, seed=False, seed_content=True)
    try:
        c = _client(app, locale="he")
        zero = c.get(f"/play/{ZERO}").text
        assert zero.count('<li class="station ') == 19 and "lock-banner" not in zero
        assert zero.count("review-badge") >= 3
        bagrut = c.get(f"/play/{BAGRUT}").text
        assert bagrut.count('<li class="station ') == 21
        assert "lock-banner" in bagrut and f'href="/play/{ZERO}"' in bagrut
        assert "מתמטיקה מאפס עד משוואה" in bagrut
        review = c.get(f"/play/{BAGRUT}?topic=t_review_tools").text
        assert "review-topic-chip" in review and "read-only-choices" in review
    finally:
        store.close()
