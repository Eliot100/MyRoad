"""Hopscotch journey layout: data-driven rows, real levels, no global bar.

The journey style is square stepping stones in a grass field, centred on the
vertical midline, read bottom to top. Row counts (1–3) come from the data:
practice peers share a row; learn and check sit alone. Levels use topic ids
ending in ``_lN``. One journey block per שלב shows the current רמה;
every stone carries a real title and a subject symbol. The timeline is unchanged.
"""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jinja2")

from fastapi.testclient import TestClient
from auth_helpers import login, login_with_code

from myroad_core.store import PathStore
from myroad_core.ui.app import create_learner_app
from myroad_core.ui.road_timeline import MAX_ROW, first_letters, hop_rows, road_timeline, stone_mark

_CORE = Path(__file__).resolve().parents[1]
_UI = _CORE / "src" / "myroad_core" / "ui"
_CSS = (_UI / "static" / "road-journey.css").read_text(encoding="utf-8")
_JS = (_UI / "static" / "road-journey.js").read_text(encoding="utf-8")
_TPL = (_UI / "templates" / "_road_journey.html").read_text(encoding="utf-8")

HOP = "path_test_hop_levels"
PLAIN = "path_test_hop_plain"


# --- view model -------------------------------------------------------------------------

def _tile(i, typ="", title=""):
    return {"id": f"t{i}", "type": typ, "title": title}


def test_hop_rows_packs_peers_to_three_and_leaves_a_short_tail() -> None:
    assert MAX_ROW == 3
    assert [len(r) for r in hop_rows(list(range(9)))] == [3, 3, 3]
    assert [len(r) for r in hop_rows(list(range(16)))] == [3, 3, 3, 3, 3, 1]
    assert [len(r) for r in hop_rows(list(range(4)))] == [3, 1]
    assert [len(r) for r in hop_rows(list(range(2)))] == [2]
    assert [len(r) for r in hop_rows(list(range(1)))] == [1]
    assert hop_rows([]) == []
    # Never more than 3 in a row, never a 1-2-3-2-1 diamond as a required pattern.
    for n in range(0, 22):
        widths = [len(r) for r in hop_rows(list(range(n)))]
        assert all(1 <= w <= 3 for w in widths)
        assert sum(widths) == n


def test_hop_rows_puts_learn_and_check_on_their_own_row() -> None:
    alg = [_tile(0, "learn")] + [_tile(i, "practice") for i in range(1, 15)] + [_tile(15, "check")]
    widths = [len(r) for r in hop_rows(alg)]
    assert widths == [1, 3, 3, 3, 3, 2, 1]
    assert hop_rows(alg)[0][0]["type"] == "learn"
    assert hop_rows(alg)[-1][0]["type"] == "check"
    # A short topic: learn + two practices → a 1-stone row and a 2-stone row.
    short = [_tile(0, "learn"), _tile(1, "practice"), _tile(2, "practice")]
    assert [len(r) for r in hop_rows(short)] == [1, 2]


def _topics(spec: list[tuple], *, types: dict | None = None) -> list[dict]:
    """(topic id, [block ids], review?) → ``_topics_for_ui``-shaped topics."""
    out, ix = [], 0
    for row in spec:
        tid, bids = row[0], row[1]
        review = row[2] if len(row) > 2 else False
        steps = []
        for bid in bids:
            steps.append({
                "blockId": bid, "index": ix, "title": bid, "titleLang": "he",
                "kind": "review" if review else "understanding",
                "type": (types or {}).get(bid, ""),
            })
            ix += 1
        out.append({"id": tid, "title": f"S {tid}", "titleLang": "he",
                    "isReview": review, "steps": steps})
    return out


def test_levels_come_from_real_lN_ids_and_are_not_invented() -> None:
    types = {"a_learn": "learn", "a_check": "check", "b_learn": "learn", "b_check": "check"}
    for i in range(4):
        types[f"a_p{i}"] = "practice"
        types[f"b_p{i}"] = "practice"
    alg = _topics([
        ("alg_l1", ["a_learn"] + [f"a_p{i}" for i in range(4)] + ["a_check"]),
        ("alg_l2", ["b_learn"] + [f"b_p{i}" for i in range(4)] + ["b_check"]),
        ("alg_l3", [f"c{i}" for i in range(3)]),
        ("alg_review", [f"r{i}" for i in range(4)], True),
    ], types=types)
    mastered = {"a_learn", "a_p0", "a_p1", "a_p2", "a_p3", "a_check"}
    tl = road_timeline(alg, mastered=mastered, current_block="b_learn")
    assert [s["stageGroup"] for s in tl["stages"]] == [1, 1, 1, 1]
    assert [s["level"] for s in tl["stages"]] == [1, 2, 3, None]
    assert [s["levelTotal"] for s in tl["stages"]] == [3, 3, 3, 3]
    assert all(s["hasRealLevels"] for s in tl["stages"])
    assert [s["boundary"] for s in tl["stages"]] == [None, "level-up", "level-up", "review"]
    assert [s["n"] for s in tl["stages"]] == [1, 2, 3, 4]  # timeline numbers unchanged
    assert [len(r) for r in tl["stages"][0]["rows"]] == [1, 3, 1, 1]  # learn, 3 practice + 1, check
    assert tl["hereStage"] == 2 and tl["stagesTotal"] == 4
    # Journey view: one block for the שלב, showing only the current level (l2).
    jy = tl["jyStages"]
    assert len(jy) == 1
    assert jy[0]["level"] == 2 and jy[0]["id"] == "alg_l2"
    assert jy[0]["boundary"] is None
    assert jy[0]["usePathTitle"] is True
    assert jy[0]["symbol"]  # stage always has a mark
    assert all(tile.get("symbol") for tile in jy[0]["tiles"])
    assert all(tile.get("title") for tile in jy[0]["tiles"])

    # A path with no _lN data: each topic is שלב N · רמה 1, never a invented רמה 2.
    plain = _topics([
        ("t_numbers", ["n1", "n2", "n3"]),
        ("t_addsub", ["a1", "a2"]),
        ("t_mul", ["m1"]),
    ])
    tl2 = road_timeline(plain, mastered={"n1"}, current_block="n2")
    assert [s["stageGroup"] for s in tl2["stages"]] == [1, 2, 3]
    assert [s["level"] for s in tl2["stages"]] == [1, 1, 1]
    assert [s["levelTotal"] for s in tl2["stages"]] == [1, 1, 1]
    assert not any(s["hasRealLevels"] for s in tl2["stages"])
    assert [s["boundary"] for s in tl2["stages"]] == [None, "stage", "stage"]
    jy2 = tl2["jyStages"]
    assert len(jy2) == 3
    assert [s["level"] for s in jy2] == [1, 1, 1]
    assert [s["boundary"] for s in jy2] == [None, "stage", "stage"]
    assert all(s.get("symbol") for s in jy2)
    assert all(tile.get("symbol") and tile.get("title") for s in jy2 for tile in s["tiles"])


def test_linear_unlock_is_unchanged_so_the_timeline_stays_the_same() -> None:
    topics = _topics([("a", ["a1", "a2"]), ("b", ["b1", "b2"])])
    tl = road_timeline(topics, mastered={"a1"}, current_block="a2", linear=True)
    assert [t["state"] for s in tl["stages"] for t in s["tiles"]] == ["done", "here", "ahead", "ahead"]
    free = road_timeline(topics, mastered={"a1"}, current_block="a2", linear=False)
    assert [t["state"] for s in free["stages"] for t in s["tiles"]] == ["done", "here", "open", "open"]



def test_stone_mark_is_deterministic_from_real_titles() -> None:
    """Symbols come from a fixed map of real titles; fallback is first letters."""
    assert stone_mark("משוואה לינארית 1", subject="math")["symbol"] == "="
    assert stone_mark("חזקות", subject="math")["symbol"] == "x²"
    assert stone_mark("שורש ריבועי", subject="math")["symbol"] == "√"
    assert stone_mark("זווית במשולש", subject="math")["symbol"] == "∠"
    assert stone_mark("אינטגרל של סינוס", subject="math")["symbol"] == "∫"
    assert stone_mark("אחוזים", subject="math")["symbol"] == "%"
    assert stone_mark("שבר פשוט", subject="math")["symbol"] == "½"
    assert stone_mark("אוצר מילים", subject="english") == {"symbol": "Aa", "markKind": "text"}
    assert stone_mark("קטע קריאה", subject="english")["markKind"] == "book"
    assert stone_mark("דיבור", subject="english")["markKind"] == "speech"
    assert stone_mark("כתב", subject="arabic")["symbol"] == "ا"
    # Fallback: first letters of the real title, never an empty mark.
    assert first_letters("משוואה לינארית 1") == "מל"
    assert first_letters("Present Simple") == "PS"
    assert first_letters("he") == "he"
    mystery = stone_mark("קסטם ייחודי", subject="math")
    assert mystery["symbol"] == first_letters("קסטם ייחודי") == "קי"
    assert stone_mark("", subject="math")["symbol"] == "x"
    assert stone_mark("", subject="")["symbol"]  # never blank


def test_every_tile_gets_a_title_and_a_symbol() -> None:
    topics = _topics([
        ("alg_l1", ["a_learn", "a_p0", "a_p1", "a_check"]),
    ], types={"a_learn": "learn", "a_p0": "practice", "a_p1": "practice", "a_check": "check"})
    # Give real titles (the helper uses the block id as the title).
    topics[0]["steps"][0]["title"] = "משוואה לינארית"
    topics[0]["steps"][1]["title"] = "חזקות"
    topics[0]["steps"][2]["title"] = "שורש"
    topics[0]["steps"][3]["title"] = "בדיקה"
    tl = road_timeline(topics, mastered=set(), current_block="a_learn", subject="math", path_title="אלגברה")
    tiles = tl["jyStages"][0]["tiles"]
    assert [t["symbol"] for t in tiles] == ["=", "x²", "√", "="]  # בדיקה + alg_ id → algebra mark
    assert all(t["title"] for t in tiles)
    assert tl["jyStages"][0]["symbol"] == "="  # אלגברה


# --- rendered page ----------------------------------------------------------------------

def _path(pid: str, title: str, topics: list[dict], nodes: list[dict]) -> dict:
    return {
        "id": pid, "subject": "math", "group_ids": ["adult"], "emoji": "🧭",
        "estimated_minutes": 40,
        "titles": {"he": title, "en": title, "ar": title},
        "blurbs": {"he": "בדיקה.", "en": "Test.", "ar": "اختبار."},
        "topics": topics, "nodes": nodes,
    }


def _level_path() -> dict:
    topics, nodes = [], []
    for lv, name in ((1, "בסיס"), (2, "יישום"), (3, "שליטה")):
        ids = [f"alg_l{lv}_learn"] + [f"alg_l{lv}_p{i}" for i in range(1, 7)] + [f"alg_l{lv}_check"]
        topics.append({"id": f"alg_l{lv}", "titles": {"he": f"רמה {lv}, {name}", "en": f"Level {lv}"},
                       "emoji": "▪️", "node_ids": ids})
        nodes.append({"id": ids[0], "type": "learn", "kind": "understanding",
                      "title": "משוואה לינארית", "body_he": "הסבר"})
        practice_titles = ["משוואה לינארית", "חזקות", "הפרש ריבועים", "אי שוויון", "שורש", "פתיחת סוגריים"]
        for i in range(1, 7):
            nodes.append({"id": f"alg_l{lv}_p{i}", "type": "practice", "kind": "understanding",
                          "title": practice_titles[i - 1], "body_he": "כמה זה 1+1?",
                          "choices": [{"id": "a", "label": "2"}, {"id": "b", "label": "3"}], "correct": "a"})
        nodes.append({"id": ids[-1], "type": "check", "kind": "understanding",
                      "title": "בדיקה", "body_he": "בדיקה",
                      "choices": [{"id": "a", "label": "2"}, {"id": "b", "label": "3"}], "correct": "a"})
    topics.append({"id": "alg_review", "titles": {"he": "חזרה מעורבת", "en": "Mixed review"},
                   "emoji": "🔁", "node_ids": [f"alg_rev_{i}" for i in range(1, 5)]})
    for i in range(1, 5):
        nodes.append({"id": f"alg_rev_{i}", "type": "practice", "kind": "review",
                      "title": f"חזרה {i}", "body_he": "חזרה",
                      "choices": [{"id": "a", "label": "2"}, {"id": "b", "label": "3"}], "correct": "a"})
    return _path(HOP, "אלגברה", topics, nodes)


def _plain_path() -> dict:
    topics = [
        {"id": "t_numbers", "titles": {"he": "מספרים", "en": "Numbers"}, "node_ids": ["n_learn", "n_p1", "n_p2"]},
        {"id": "t_add", "titles": {"he": "חיבור", "en": "Adding"}, "node_ids": ["a_learn", "a_p1"]},
    ]
    nodes = [
        {"id": "n_learn", "type": "learn", "title": "מספרים", "body_he": "הסבר"},
        {"id": "n_p1", "type": "practice", "title": "תרגיל 1", "body_he": "?",
         "choices": [{"id": "a", "label": "1"}, {"id": "b", "label": "2"}], "correct": "a"},
        {"id": "n_p2", "type": "practice", "title": "תרגיל 2", "body_he": "?",
         "choices": [{"id": "a", "label": "1"}, {"id": "b", "label": "2"}], "correct": "a"},
        {"id": "a_learn", "type": "learn", "title": "חיבור", "body_he": "הסבר"},
        {"id": "a_p1", "type": "practice", "title": "תרגיל", "body_he": "?",
         "choices": [{"id": "a", "label": "1"}, {"id": "b", "label": "2"}], "correct": "a"},
    ]
    return _path(PLAIN, "מאפס", topics, nodes)


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_level_path(), _plain_path()):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "hop.db"))
    application = create_learner_app(store=store, seed=False, seed_content=True)
    yield application
    store.close()


def _client(app, locale: str = "he") -> TestClient:
    c = TestClient(app)
    c.cookies.set("myroad_locale", locale)
    login_with_code(c, {"first_name": "Hop", "last_name": "User",
                        "email": f"hop-{locale}@example.com", "next": "/"})
    c.cookies.set("myroad_locale", locale)
    return c


def _journey(html: str) -> str:
    a = html.index('data-road-style-panel="journey"')
    try:
        b = html.index('data-road-style-panel="timeline"', a)
        # journey panel is after timeline in map.html
    except ValueError:
        b = len(html)
    # actually journey comes AFTER timeline, so take from journey marker to footer / end
    return html[a:]


def test_journey_html_has_rows_levels_and_no_global_bar(app) -> None:
    c = _client(app)
    html = c.get(f"/play/{HOP}?view=map").text
    jy = _journey(html)
    assert 'id="journey-track"' in jy
    assert "jy-meter-overall" not in jy
    assert "jy-progress" not in jy
    assert "מסע" not in jy
    # One block per שלב, current level only: "שלב 1 · אלגברה · רמה 1".
    # The next level is not a separate block and there is no level-up arch.
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", jy))
    assert "שלב 1 · אלגברה · רמה 1" in text
    assert "שלב 1 · אלגברה · רמה 2" not in text
    assert "שלב 1 · רמה 2" not in text
    assert "שלב 1 · רמה 3" not in text
    assert "שלב 1 · חזרה" not in text
    assert "jy-levelup" not in jy
    assert 'data-jy-level="1"' in jy
    assert 'data-jy-level="2"' not in jy
    # Rows exist, and a 3-stone row is present (6 practices → 3+3).
    assert 'class="jy-row"' in jy
    assert 'data-jy-cols="3"' in jy
    assert 'data-jy-cols="1"' in jy
    # Each block still has its own meter. No global bar.
    assert "jy-meter" in jy and "jy-meter-fill" in jy
    # Stones still post the same start form.
    assert jy.count('action="/play/' + HOP + '/start"') >= 1
    assert 'name="node"' in jy
    # Exactly one recommended stone, labelled "מומלץ לתרגל".
    assert jy.count('aria-current="step"') == 1
    assert jy.count('id="jy-here"') == 1
    assert jy.count("jy-recommend-flag") == 1
    assert "מומלץ לתרגל" in jy
    # Every stone has a visible title and a subject symbol. No blank stones.
    n_stones = jy.count('class="jy-stone"')
    assert n_stones >= 8
    assert jy.count('class="jy-short"') == n_stones
    assert "משוואה לינארית" in jy
    assert "חזקות" in jy
    assert "jy-mark" in jy
    # Algebra's subject symbol "=" appears on the stage and on equation stones.
    assert re.search(r'class="jy-mark"[^>]*>\s*=\s*<', jy)
    # No check-mark icon on done (or any) stones.
    assert "jy-level-badge" in _TPL  # present in the template for walked stones
    # Timeline panel is still in the page and still uses שלב numbers 1..4.
    tl = html[html.index('data-road-style-panel="timeline"'):html.index('data-road-style-panel="journey"')]
    assert "שלב 1" in tl and "שלב 4" in tl
    assert "jy-levelup" not in tl
    assert "jy-mark" not in tl


def test_plain_path_is_level_1_blocks_with_a_stage_boundary(app) -> None:
    c = _client(app)
    html = c.get(f"/play/{PLAIN}?view=map").text
    jy = _journey(html)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", jy))
    assert "שלב 1 · מספרים · רמה 1" in text
    assert "שלב 2 · חיבור · רמה 1" in text
    assert "שלב 2" in text and "חיבור" in text  # topic name on the stage boundary
    # Symbols on stones and on the stage label; no blank stones.
    n_stones = jy.count('class="jy-stone"')
    assert n_stones >= 5
    assert jy.count('class="jy-short"') == n_stones
    assert "jy-mark" in jy
    assert 'class="jy-stage-bound' in jy
    # No invented רמה 2 on a path without _lN data.
    assert "שלב 1 · רמה 2" not in text
    assert "מסע" not in jy


def test_css_locks_a_fixed_stone_size_and_centres_rows() -> None:
    assert "--jy-stone-size:" in _CSS
    assert "flex: 0 0 var(--jy-stone-size)" in _CSS
    assert "max-inline-size: var(--jy-stone-size)" in _CSS
    assert "column-reverse" in _CSS
    assert "justify-content: center" in _CSS
    # Old meander / absolute placement is gone.
    assert "display: contents" not in _CSS
    # Journey hides the shared goal meter; timeline is untouched.
    assert 'html[data-road-style="journey"] .goal-meter { display: none; }' in _CSS
    # Horizontal rotates rows into columns at 1024px.
    assert "@media (min-width: 1024px)" in _CSS
    assert 'html[data-road-orientation="horizontal"]' in _CSS
    assert "flex-direction: column; /* a hopscotch row is now a column" in _CSS or \
           "flex-direction: column;" in _CSS
    # Template has no global bar, no level-up arch, has rows, marks and titles.
    assert "jy-meter-overall" not in _TPL
    assert "jy-levelup" not in _TPL and "jy-rows" in _TPL
    assert "jy-mark" in _TPL and "jy-short" in _TPL
    assert "jy-level-badge" in _TPL and "jy_recommend" in _TPL
    assert "מסע" not in _TPL
    assert "jy-recommend-pulse" in _CSS
    assert "line-clamp: 2" in _CSS
    assert "--jy-stone-h" in _CSS
    # Locales: all three, no dashes, no מסע.
    for code, label in (("he", "שלב {n} · רמה {level}"),
                        ("en", "Stage {n} · Level {level}"),
                        ("ar", "المرحلة {n} · المستوى {level}")):
        j = json.loads((_CORE / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        assert j["jy_block_label"] == label
        for k in ("jy_block_label", "jy_block_review", "jy_level_n", "jy_level_up",
                  "jy_stage_bound", "jy_recommend"):
            assert j[k] and "—" not in j[k] and "–" not in j[k] and "מסע" not in j[k]
    assert json.loads((_CORE / "locales" / "he.json").read_text(encoding="utf-8"))["jy_recommend"] == "מומלץ לתרגל"


def test_orientation_js_still_sets_horizontal_on_wide_screens() -> None:
    assert "data-jy-orient" in _JS
    assert "myroad.roadOrientation" in _JS
    assert "is-horizontal" in _JS
    assert "min-width: 1024px" in _JS
    assert "myroadScrollJourneyHere" in _JS


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_rows_are_centred_on_the_midline_with_a_fixed_stone_size(app) -> None:
    """Geometry: same stone size across rows, each row centred, first stone at the bottom."""
    sync_api = pytest.importorskip("playwright.sync_api")
    uvicorn = pytest.importorskip("uvicorn")
    codes: list[str] = []
    app.state.login_code_sender = lambda email, code: codes.append(code)
    app.state.login_notice_sender = lambda email: None
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        with sync_api.sync_playwright() as p:
            chrome = os.environ.get("MYROAD_CHROME", "/usr/bin/google-chrome")
            try:
                br = p.chromium.launch(executable_path=chrome if Path(chrome).exists() else None,
                                       args=["--no-sandbox"])
            except Exception as exc:
                pytest.skip(f"no headless browser: {exc}")
            ctx = br.new_context(locale="he-IL", viewport={"width": 375, "height": 812})
            pg = ctx.new_page()
            pg.request.post(base + "/login", headers={"Origin": base}, form={
                "mode": "register", "first_name": "Noa", "last_name": "Levi",
                "email": "hop-geo@example.com", "next": "/"})
            assert codes, "no login code"
            pg.request.post(base + "/login/verify", headers={"Origin": base},
                            form={"code": codes[-1], "next": "/"})
            pg.goto(base + "/")
            pg.evaluate("() => localStorage.setItem('myroad.roadStyle','journey')")
            pg.goto(base + f"/play/{HOP}?view=map")
            pg.wait_for_load_state()
            pg.wait_for_selector(".road-jy.is-laid, .road-jy .jy-step", timeout=5000)
            pg.wait_for_timeout(300)
            geo = pg.evaluate("""() => {
              const field = document.querySelector('.jy-field');
              const fr = field.getBoundingClientRect();
              const mid = fr.left + fr.width / 2;
              const stages = [...document.querySelectorAll('.jy-stage')];
              const firstStage = stages[0];
              const rows = [...firstStage.querySelectorAll('.jy-row')];
              const rowInfo = rows.map(row => {
                const stones = [...row.querySelectorAll('.jy-step')];
                const boxes = stones.map(s => {
                  const r = s.getBoundingClientRect();
                  return {x: r.x, y: r.y, w: r.width, h: r.height, cx: r.left + r.width/2};
                });
                const left = Math.min(...boxes.map(b => b.x));
                const right = Math.max(...boxes.map(b => b.x + b.w));
                return {
                  n: stones.length,
                  cols: parseInt(row.getAttribute('data-jy-cols') || '0', 10),
                  cx: (left + right) / 2,
                  y: boxes[0].y,
                  sizes: boxes.map(b => [Math.round(b.w), Math.round(b.h)]),
                  sameY: boxes.every(b => Math.abs(b.y - boxes[0].y) < 2),
                };
              });
              const steps = [...document.querySelectorAll('.jy-step')];
              const a = steps[0].getBoundingClientRect();
              const b = steps[steps.length - 1].getBoundingClientRect();
              const labels = [...document.querySelectorAll('.jy-stage-label .jy-kicker')].map(el => el.innerText.trim());
              const hasLevelUp = !!document.querySelector('.jy-levelup');
              const shorts = [...document.querySelectorAll('.jy-short')].map(el => (el.textContent || '').trim());
              const marks = [...document.querySelectorAll('.jy-step .jy-mark')].map(el => (el.textContent || '').trim() || !!el.querySelector('svg'));
              const recommend = document.querySelectorAll('.jy-recommend-flag').length;
              const overall = !!document.querySelector('.jy-meter-overall');
              const goalHidden = (() => {
                const g = document.querySelector('.goal-meter');
                if (!g) return true;
                const s = getComputedStyle(g);
                return s.display === 'none' || s.visibility === 'hidden';
              })();
              return {
                mid, rowInfo,
                firstY: a.y, lastY: b.y, n: steps.length,
                labels, hasLevelUp, overall, goalHidden,
                shorts, marks, recommend,
                fieldW: fr.width,
              };
            }""")
            assert geo["n"] >= 8
            # Bottom to top: first stone (start) is below the last.
            assert geo["lastY"] < geo["firstY"]
            assert not geo["hasLevelUp"] and not geo["overall"] and geo["goalHidden"]
            assert any("רמה 1" in lb and "אלגברה" in lb for lb in geo["labels"])
            # Every stone shows a title and a mark; one recommended flag.
            assert len(geo["shorts"]) == geo["n"]
            assert all(geo["shorts"]), geo["shorts"]
            assert all(geo["marks"]), geo["marks"]
            assert geo["recommend"] == 1
            sizes = [s for row in geo["rowInfo"] for s in row["sizes"]]
            assert sizes, "no stones"
            # One fixed size (±2px) across every stone and every row.
            w0, h0 = sizes[0]
            assert w0 >= 44 and h0 >= 44
            for w, h in sizes:
                assert abs(w - w0) <= 2 and abs(h - h0) <= 2
            # Each row is centred on the field's vertical midline (±8px).
            for row in geo["rowInfo"]:
                assert row["sameY"]
                assert row["n"] == row["cols"]
                assert 1 <= row["n"] <= 3
                assert abs(row["cx"] - geo["mid"]) <= 8, row
            # There is both a 1-stone and a 3-stone row in the first level.
            ns = {row["n"] for row in geo["rowInfo"]}
            assert 1 in ns and 3 in ns
            br.close()
    finally:
        server.should_exit = True
        th.join(timeout=5)
