"""Road page timeline (arena road-ui final, base c1 + grafts from c2 and c3): one template for every road shape.

The road page draws the whole road as one vertical line of שלבים (topics), each with its
משבצות (steps). Checks: the view model (road_timeline.py) on few, many, linear and read
only roads; the rendered page keeps every שלב and every משבצת on one screen; the current
שלב is the jump target (id="here") and the current משבצת carries aria-current="step"; one
next action (a sticky continue bar that JS shows only while the head button is off screen);
review differs by shape and word, not color alone; CSS is logical, themed and has 44px targets.
Grafts: a sticky overview bar (one segment per שלב sized by its משבצות), the line solid behind
the learner and dashed ahead, alternating sides on wide screens, and one message + one action
in the head for a finished road and for a locked road.
Replaces test_long_map.py, test_map_float_here.py and test_world_map.py (#57, #68, world map).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login_with_code

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app
from myroad_core.ui.road_timeline import OPEN_ALL_MAX_TILES, road_timeline

_CORE = Path(__file__).resolve().parents[1]
_STATIC = _CORE / "src" / "myroad_core" / "ui" / "static"
_CSS = (_STATIC / "road-timeline.css").read_text(encoding="utf-8")
LONG = "path_test_map_long"
SHORT = "path_test_map_short"
LOCKED = "path_test_map_locked"
N = 20  # stations; every 4th (index 3, 7, ...) is a review station


def _long() -> dict:
    topics, nodes, regular = [], [], []
    for i in range(N):
        tid = f"s{i:02d}"
        if i % 4 == 3:
            nid = f"r{i:02d}"
            topics.append({"id": tid, "titles": {"he": f"חזרה {i}", "en": f"Review {i}", "ar": f"مراجعة {i}"},
                           "emoji": "🔁", "node_ids": [nid]})
            nodes.append({"id": nid, "type": "practice", "kind": "review", "review_topic_ids": regular[-2:],
                          "title": f"חזרה {i}", "body_he": "כמה זה 2+2?",
                          "choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "5"}], "correct": "a"})
            continue
        topics.append({"id": tid, "titles": {"he": f"תחנה {i}", "en": f"Station {i}", "ar": f"محطة {i}"},
                       "node_ids": [f"l{i:02d}"]})
        nodes.append({"id": f"l{i:02d}", "type": "learn", "title": f"הסבר {i}", "body_he": "הסבר"})
        regular.append(tid)
    return {"id": LONG, "subject": "math", "group_ids": ["adult"], "emoji": "🧭", "estimated_minutes": 200,
            "titles": {"he": "מפה ארוכה", "en": "Long map", "ar": "خريطة طويلة"},
            "blurbs": {"he": "בדיקה.", "en": "Test.", "ar": "اختبار."}, "topics": topics, "nodes": nodes}


def _short() -> dict:
    return {"id": SHORT, "subject": "math", "group_ids": ["adult"], "emoji": "🧩", "estimated_minutes": 20,
            "titles": {"he": "מפה קצרה", "en": "Short map", "ar": "خريطة قصيرة"},
            "blurbs": {"he": "קצר.", "en": "Short.", "ar": "قصير."},
            "topics": [{"id": "a", "titles": {"he": "א", "en": "A"}, "node_ids": ["x1"]},
                       {"id": "b", "titles": {"he": "ב", "en": "B"}, "node_ids": ["x2"]}],
            "nodes": [{"id": "x1", "type": "learn", "title": "הסבר", "body_he": "הסבר"},
                      {"id": "x2", "type": "learn", "title": "עוד", "body_he": "עוד"}]}


def _locked() -> dict:
    doc = _long()
    doc.update(id=LOCKED, prerequisite_path_ids=[SHORT],
               titles={"he": "נעולה", "en": "Locked", "ar": "مقفل"})
    return doc


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_long(), _short(), _locked()):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "map.db"))
    application = create_learner_app(store=store, seed=False, seed_content=True)
    yield application
    store.close()


def _client(app, locale: str = "he") -> TestClient:
    c = TestClient(app)
    c.cookies.set("myroad_locale", locale)
    login_with_code(c, {"first_name": "Map", "last_name": "User", "email": f"map-{locale}@example.com", "next": "/"})
    c.cookies.set("myroad_locale", locale)
    return c


def _go_to_station(c: TestClient, n: int) -> None:
    """Ack learn steps / answer reviews until station ``n`` (1-based) is current."""
    c.post(f"/play/{LONG}/start")
    for i in range(n - 1):
        if i % 4 == 3:
            c.post(f"/play/{LONG}/answer", data={"choice": "a"})
        else:
            c.post(f"/play/{LONG}/ack")


def _stage(html: str, tid: str) -> str:
    """The <li> of one שלב, from its opening tag to the next שלב (or the end marker)."""
    at = html.find(f'data-topic-id="{tid}"')
    start = html.rfind('<li class="tl-stage', 0, at)
    nxt = [i for i in (html.find('<li class="tl-stage', at), html.find('<div class="tl-end', at)) if i > 0]
    return html[start:min(nxt)]


def _topics(spec: list[tuple[str, list[str]]], kinds: dict[str, str] | None = None) -> list[dict]:
    """``_topics_for_ui``-shaped topics from (topic id, [block ids]) in road order."""
    out, ix = [], 0
    for tid, bids in spec:
        steps = []
        for bid in bids:
            steps.append({"blockId": bid, "index": ix, "title": f"T {bid}", "titleLang": "he",
                          "kind": (kinds or {}).get(bid, "understanding")})
            ix += 1
        out.append({"id": tid, "title": f"S {tid}", "titleLang": "he", "steps": steps,
                    "isReview": all(s["kind"] == "review" for s in steps) and bool(steps)})
    return out



# --- view model -------------------------------------------------------------------------

def test_view_model_counts_states_and_the_next_tile() -> None:
    topics = _topics([("a", ["a1", "a2"]), ("b", ["b1", "b2", "b3"]), ("c", ["c1"])])
    tl = road_timeline(topics, mastered={"a1", "a2", "b1"}, current_block="b2")
    assert (tl["done"], tl["total"], tl["pct"], tl["stagesDone"], tl["stagesTotal"]) == (3, 6, 50, 1, 3)
    assert [s["state"] for s in tl["stages"]] == ["done", "here", "open"]
    assert [t["state"] for t in tl["stages"][1]["tiles"]] == ["done", "here", "open"]
    assert tl["next"]["id"] == "b2" and tl["next"]["stageN"] == 2 and tl["hereStage"] == 2
    # The last משבצת of a שלב with more than one is its בדיקה; a one-tile שלב has none.
    assert tl["stages"][1]["tiles"][-1]["check"] and not tl["stages"][2]["tiles"][0]["check"]


def test_view_model_next_skips_a_finished_saved_position() -> None:
    topics = _topics([("a", ["a1", "a2"]), ("b", ["b1"])])
    tl = road_timeline(topics, mastered={"a1"}, current_block="a1")  # reopened a done tile
    assert tl["next"]["id"] == "a2"
    done = road_timeline(topics, mastered={"a1", "a2", "b1"}, current_block="b1")
    assert done["finished"] and done["next"] is None and done["stagesDone"] == 2


def test_view_model_linear_chain_locks_tiles_past_the_gap() -> None:
    topics = _topics([("a", ["a1", "a2"]), ("b", ["b1", "b2"])])
    tl = road_timeline(topics, mastered={"a1"}, current_block="a2", linear=True)
    assert [t["state"] for s in tl["stages"] for t in s["tiles"]] == ["done", "here", "ahead", "ahead"]
    assert [s["state"] for s in tl["stages"]] == ["here", "ahead"]
    free = road_timeline(topics, mastered={"a1"}, current_block="a2", linear=False)
    assert [t["state"] for t in free["stages"][1]["tiles"]] == ["open", "open"]


def test_view_model_read_only_has_no_position() -> None:
    topics = _topics([("a", ["a1"]), ("b", ["b1"])])
    tl = road_timeline(topics, mastered=set(), current_block="a1", read_only=True)
    assert tl["next"] is None and {s["state"] for s in tl["stages"]} == {"view"}
    assert [s["open"] for s in tl["stages"]] == [True, True]  # short road: all open


def test_view_model_short_roads_open_every_stage_long_roads_only_the_current() -> None:
    short = _topics([(f"s{i}", [f"x{i}"]) for i in range(OPEN_ALL_MAX_TILES)])
    assert all(s["open"] for s in road_timeline(short, mastered=set(), current_block="x0")["stages"])
    long = _topics([(f"s{i}", [f"x{i}a", f"x{i}b"]) for i in range(20)])
    tl = road_timeline(long, mastered={"x0a", "x0b"}, current_block="x1a")
    assert [s["n"] for s in tl["stages"] if s["open"]] == [2]


def test_view_model_handles_empty_and_one_stage_roads() -> None:
    empty = road_timeline([], mastered=None, current_block=None)
    assert empty["total"] == 0 and empty["pct"] == 0 and empty["next"] is None and not empty["finished"]
    one = road_timeline(_topics([("only", [f"n{i}" for i in range(13)])]), mastered=set(), current_block=None)
    assert one["stagesTotal"] == 1 and one["next"]["id"] == "n0" and one["stages"][0]["open"]


def test_view_model_walked_stages_stage_pct_and_first_tile() -> None:
    topics = _topics([("a", ["a1", "a2"]), ("b", ["b1", "b2"]), ("c", ["c1", "c2"])])
    tl = road_timeline(topics, mastered={"a1", "a2", "b1"}, current_block="b2")
    assert [s["walked"] for s in tl["stages"]] == [True, False, False]
    assert [s["pct"] for s in tl["stages"]] == [100, 50, 0] and tl["first"] == "a1"
    done = road_timeline(topics, mastered={"a1", "a2", "b1", "b2", "c1", "c2"}, current_block=None)
    assert all(s["walked"] for s in done["stages"]) and done["finished"]
    peek = road_timeline(topics, mastered=set(), current_block=None, read_only=True)
    assert not any(s["walked"] for s in peek["stages"])
    assert road_timeline([], mastered=None, current_block=None)["first"] is None


def test_view_model_handles_a_97_tile_road() -> None:
    sizes = [3, 8, 6, 7, 7, 7, 7, 7, 7, 7, 6, 8, 6, 9, 2]  # the AMIRNET road's shape
    spec, n = [], 0
    for i, k in enumerate(sizes):
        spec.append((f"t{i}", [f"b{n + j}" for j in range(k)]))
        n += k
    topics = _topics(spec)
    mastered = {f"b{i}" for i in range(23)}
    tl = road_timeline(topics, mastered=mastered, current_block="b23")
    assert tl["total"] == 97 and tl["done"] == 23 and tl["hereStage"] == 4 and tl["stagesDone"] == 3
    assert sum(1 for s in tl["stages"] if s["open"]) == 1


# --- rendered page ----------------------------------------------------------------------

@pytest.mark.parametrize("locale", ["he", "en", "ar"])
def test_current_stage_is_the_jump_target_and_the_tile_has_aria_current(app, locale) -> None:
    c = _client(app, locale)
    _go_to_station(c, 15)
    html = c.get(f"/play/{LONG}?view=map").text
    assert html.count('aria-current="step"') == 1 and html.count('id="here"') == 1
    here = _stage(html, "s14")
    head = here.split(">", 1)[0]
    assert "tl-stage is-here" in head and 'id="here"' in head
    assert "<details open" in here and 'aria-current="step"' in here
    assert 'aria-current' not in _stage(html, "s13") and 'id="here"' not in _stage(html, "s15")
    assert "tl-stage is-done" in _stage(html, "s13").split(">", 1)[0]
    assert f'dir="{"ltr" if locale == "en" else "rtl"}"' in html[:200]


def test_whole_road_is_on_one_screen_with_every_tile(app) -> None:
    c = _client(app)
    html = c.get(f"/play/{LONG}?view=map").text
    assert html.count('<li class="tl-stage ') == N
    # Every משבצת is drawn twice: a dot on the closed face and a named row inside.
    assert html.count('<li class="tl-tile ') == N and html.count('class="tl-dots"') == N
    assert 'data-stages="20" data-tiles="20"' in html
    assert 'class="tl-end' in html and "סוף הדרך" in html


def test_one_next_action_sticky_bar_targets_the_next_tile(app) -> None:
    c = _client(app)
    _go_to_station(c, 3)
    html = c.get(f"/play/{LONG}?view=map").text
    bar = html[html.index("data-tl-continue"):]
    bar = bar[:bar.index("</div>")]
    assert "hidden" in html[html.index('<div class="tl-continue"'):html.index("data-tl-continue") + 30]
    assert 'href="#here"' in bar and 'name="node" value="blk_002_' in bar and "המשך" in bar
    assert html.count('class="primary big continue-btn"') == 1  # the head keeps the one visible button
    head = html[html.index('class="continue-card"'):html.index("continue-btn")]
    assert 'class="continue-next"' in head and "המשבצת הבאה" in head  # the head names the next tile too
    js = (_STATIC / "platform.js").read_text(encoding="utf-8")
    fn = js[js.index("function stickyContinue"):]
    fn = fn[:fn.index("\n  }\n") + 4]
    assert "IntersectionObserver" in fn and ".continue-btn" in fn and "bar.hidden" in fn
    links = js[js.index("function hereLinks"):]
    links = links[:links.index("\n  }\n") + 4]
    assert 'a[href="#here"]' in links and "myroadReduceMotion" in links and ".focus(" in links


def test_overview_bar_has_a_segment_per_stage_sized_by_its_tiles(app) -> None:
    c = _client(app)
    _go_to_station(c, 15)
    html = c.get(f"/play/{LONG}?view=map").text
    ov = html[html.index('class="tl-overview"'):html.index('<ol class="tl">')]
    assert ov.count('class="tl-seg ') == N and ov.count('style="flex-grow: 1"') == N
    assert ov.count("tl-seg is-here") == 1 and ov.count("tl-seg is-done") == 14
    assert 'class="tl-sum-here" href="#here"' in ov and "שלב <bdi>15</bdi> מתוך <bdi>20</bdi>" in ov
    assert 'role="progressbar"' in ov and 'aria-valuenow="14"' in ov and 'aria-valuemax="20"' in ov
    assert re.search(r"\.road-tl \.tl-overview \{[^}]*position: sticky", _CSS)
    assert re.search(r"\.road-tl \.tl-overview \{[^}]*background: var\(--card\)", _CSS)  # opaque over the line


def test_line_is_solid_behind_the_learner_and_dashed_ahead(app) -> None:
    c = _client(app)
    _go_to_station(c, 3)
    html = c.get(f"/play/{LONG}?view=map").text
    assert "is-walked" in _stage(html, "s00").split(">", 1)[0] and "is-walked" in _stage(html, "s01").split(">", 1)[0]
    assert "is-walked" not in _stage(html, "s02").split(">", 1)[0]  # the current שלב
    assert "is-walked" not in _stage(html, "s05").split(">", 1)[0]
    assert re.search(r"\.road-tl \.tl-stage::before \{[^}]*background: var\(--tl-dash\)", _CSS)
    assert re.search(r"\.road-tl \.tl-stage\.is-walked::before \{[^}]*var\(--tl-line-done\)", _CSS)


def test_wide_screens_alternate_sides_around_a_centered_line() -> None:
    wide = _CSS[_CSS.index("@container tl (min-width: 720px)"):]
    assert "minmax(0, 1fr) var(--tl-gutter) minmax(0, 1fr)" in wide
    assert re.search(r"\.road-tl \.tl-stage > details \{ grid-column: 1; grid-row: 1; \}", wide)
    assert re.search(r"\.tl-stage:nth-child\(even\) > details,[^{]*\{ grid-column: 3;", wide)
    assert "inset-inline-start: calc(50% - var(--tl-w) / 2)" in wide


def test_head_names_the_next_tile_first_and_its_button_opens_that_tile(app) -> None:
    c = _client(app)
    _go_to_station(c, 3)
    html = c.get(f"/play/{LONG}?view=map").text
    assert html.index('class="continue-card"') < html.index('class="goal-meter"')  # action before stats
    card = html[html.index('class="continue-card"'):]
    card = card[:card.index("</section>")]
    assert 'name="node" value="blk_002_' in card and card.count('class="primary big continue-btn"') == 1


def test_finished_road_head_has_one_message_and_a_secondary_way_back(app) -> None:
    c = _client(app)
    c.post(f"/play/{SHORT}/start")
    c.post(f"/play/{SHORT}/ack")
    c.post(f"/play/{SHORT}/ack")
    html = c.get(f"/play/{SHORT}?view=map").text
    card = html[html.index('class="continue-card is-finished"'):]
    card = card[:card.index("</section>")]
    assert "כל <bdi>2</bdi> המשבצות בדרך הושלמו" in card and "הדרך הושלמה" in card
    assert 'class="secondary big continue-btn"' in card and 'name="node" value="' in card
    assert 'class="primary big' not in html.split('<nav class="side"')[0]
    assert "data-tl-continue" not in html and 'class="tl-end is-done is-walked"' in html


def test_locked_road_head_has_one_message_and_one_action(app) -> None:
    c = _client(app)
    html = c.get(f"/play/{LOCKED}?view=map").text
    head = html[html.index('class="card path-head'):html.index('class="card road-tl')]
    assert 'class="continue-card lock-banner"' in head and f'data-locked-by="{SHORT}"' in head
    assert head.count("continue-btn") == 1 and f'href="/play/{LOCKED}?view=learn"' in head
    assert "map-actions" not in html and html.count("lock-banner") == 1


def test_road_page_title_has_no_dash(app) -> None:
    c = _client(app)
    html = c.get(f"/play/{LONG}?view=map").text
    title = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
    assert "מפה ארוכה" in title and "—" not in title and "–" not in title


def test_map_links_carry_the_fragment_and_load_the_jump_script(app) -> None:
    c = _client(app)
    _go_to_station(c, 3)
    play = c.get(f"/play/{LONG}?view=learn").text
    assert f'href="/play/{LONG}?view=map#here" class="back"' in play
    html = c.get(f"/play/{LONG}?view=map").text
    assert '<script src="/static/platform.js" defer></script>' in html
    assert '<link rel="stylesheet" href="/static/road-timeline.css" />' in html
    assert "worldmap.js" not in html
    stats = (_CORE / "src" / "myroad_core" / "ui" / "templates" / "stats.html").read_text(encoding="utf-8")
    assert "?view=map#here" in stats


def test_jump_script_respects_reduced_motion_and_restored_scroll() -> None:
    js = (_STATIC / "platform.js").read_text(encoding="utf-8")
    fn = js[js.index("function jumpToCurrentStation"):]
    fn = fn[:fn.index("\n  }\n") + 4]
    assert 'getElementById("here")' in fn
    assert "prefers-reduced-motion: reduce" in fn and 'behavior: reduce ? "auto" : "smooth"' in fn
    assert "window.location.hash" in fn and "back_forward" in fn
    assert "fits" in fn  # no movement when the stage is already on screen
    assert ".focus(" not in fn  # scroll only: screen reader users keep their reading position


def test_read_only_map_has_no_position_and_no_actions(app) -> None:
    c = _client(app)
    html = c.get(f"/play/{LOCKED}?view=map").text
    assert "lock-banner" in html and "road-tl is-view" in html
    main = html.split('<nav class="side"')[0]  # the road picker marks the open road, not a stage
    assert 'aria-current' not in main and 'id="here"' not in html and "data-tl-continue" not in html
    # Links instead of start forms: one read-only peek per שלב, every משבצת listed.
    assert html.count('class="tl-tile is-view') == N and f'action="/play/{LOCKED}/start"' not in html
    assert html.count("tl-peek") == N


def test_short_map_opens_every_stage_and_marks_the_current(app) -> None:
    c = _client(app)
    c.post(f"/play/{SHORT}/start")
    c.post(f"/play/{SHORT}/ack")
    html = c.get(f"/play/{SHORT}?view=map").text
    assert html.count("<details open") >= 2 and html.count('aria-current="step"') == 1
    assert "tl-stage is-here" in _stage(html, "b").split(">", 1)[0]
    assert "tl-stage is-done" in _stage(html, "a").split(">", 1)[0]


def test_review_stages_differ_by_shape_and_word(app) -> None:
    c = _client(app)
    html = c.get(f"/play/{LONG}?view=map").text
    review = _stage(html, "s03")
    assert "is-review" in review.split(">", 1)[0] and "חזרה" in review and "🔁" not in review
    assert "is-review" not in _stage(html, "s02").split(">", 1)[0]
    assert re.search(r"\.road-tl \.is-review > \.tl-node \{[^}]*border-radius: 10px", _CSS)
    assert re.search(r"\.road-tl \.tl-node \{[^}]*border-radius: 50%", _CSS)
    assert re.search(r"\.road-tl \.is-ahead > \.tl-node \{[^}]*border-style: dashed", _CSS)


def test_timeline_css_is_logical_themed_and_has_targets() -> None:
    code = re.sub(r"/\*.*?\*/", "", _CSS, flags=re.S)
    assert not re.search(r"(border|padding|margin)-(left|right)\b|(?<![\w-])(left|right)\s*:", code)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", code)  # theme tokens only, both themes follow
    assert re.search(r"\.road-tl \.tl-stage summary \{[^}]*min-block-size: 44px", code)
    assert re.search(r"\.road-tl \.tl-row \{[^}]*min-block-size: 44px", code)
    assert re.search(r"summary:focus-visible \{[^}]*outline: 3px solid", code)
    assert "@media (prefers-reduced-motion: reduce)" in code
    assert "container: tl / inline-size" in code


def test_timeline_strings_exist_and_are_dashless() -> None:
    packs = {code: json.loads((_CORE / "locales" / f"{code}.json").read_text(encoding="utf-8")) for code in ("he", "en", "ar")}
    keys = {k for k in packs["he"] if k.startswith("tl_")}
    assert len(keys) >= 15 and all(keys <= set(p) for p in packs.values())
    for code, pack in packs.items():
        for k in keys:
            v = pack[k]
            assert v.strip() and "—" not in v and "–" not in v and " - " not in v, (code, k)
            assert set(re.findall(r"{(\w+)}", v)) == set(re.findall(r"{(\w+)}", packs["he"][k])), (code, k)
    assert not any(k.startswith("world_") for k in packs["he"])  # the world map is gone
