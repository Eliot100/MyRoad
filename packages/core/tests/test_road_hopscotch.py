"""Journey hopscotch road: centered rows, current-level blocks, titled stones.

Row grouping follows Eliot's 2026-11-12 correction: symmetry is around the
vertical center line, not a 1-2-3-2-1 diamond. Any-order peers share a row
of at most 3; stone size is fixed; each row is centered. Levels come only
from topic ids ending in ``_lN``. Correction 2: one current-level block per
stage, no gateways, done stones are leveled-up (no check). Correction 3:
every stone and stage label shows a real title and/or a subject symbol.
The timeline style and ``road_timeline`` are left untouched.
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
from myroad_core.ui.road_hopscotch import (
    current_level_block,
    hop_rows,
    pack_row_counts,
    road_hopscotch,
    short_title,
    stone_mark,
    title_initials,
    topic_level,
)
from myroad_core.ui.road_timeline import road_timeline

_CORE = Path(__file__).resolve().parents[1]
_UI = _CORE / "src" / "myroad_core" / "ui"
_LOCALES = _CORE / "locales"
LEVELED = "path_test_hop_leveled"
PLAIN = "path_test_hop_plain"


def _topics(spec: list[tuple[str, list[str]]], types: dict[str, str] | None = None,
            titles: dict[str, str] | None = None) -> list[dict]:
    out, ix = [], 0
    for tid, bids in spec:
        steps = []
        for bid in bids:
            steps.append({
                "blockId": bid, "index": ix, "title": f"T {bid}", "titleLang": "he",
                "kind": "review" if "review" in tid else "understanding",
                "type": (types or {}).get(bid, "practice"),
            })
            ix += 1
        out.append({
            "id": tid, "title": (titles or {}).get(tid, f"S {tid}"), "titleLang": "he",
            "steps": steps, "isReview": "review" in tid,
        })
    return out


# --- unit: rows and levels ---------------------------------------------------

def test_pack_row_counts_balances_remainders() -> None:
    assert pack_row_counts(0) == []
    assert pack_row_counts(1) == [1]
    assert pack_row_counts(2) == [2]
    assert pack_row_counts(3) == [3]
    assert pack_row_counts(4) == [2, 2]  # not 3+1
    assert pack_row_counts(5) == [3, 2]
    assert pack_row_counts(7) == [3, 2, 2]
    assert pack_row_counts(14) == [3, 3, 3, 3, 2]
    # Not a 1-2-3-2-1 diamond.
    assert pack_row_counts(9) != [1, 2, 3, 2, 1]


def test_hop_rows_groups_any_order_peers_and_splits_on_type() -> None:
    peers = [{"id": f"p{i}", "type": "practice"} for i in range(14)]
    assert [len(r) for r in hop_rows(peers)] == [3, 3, 3, 3, 2]
    mixed = (
        [{"id": "L", "type": "learn"}]
        + [{"id": f"p{i}", "type": "practice"} for i in range(14)]
        + [{"id": "C", "type": "check", "check": True}]
    )
    rows = hop_rows(mixed)
    assert [len(r) for r in rows] == [1, 3, 3, 3, 3, 2, 1]
    assert rows[0][0]["id"] == "L" and rows[-1][0]["id"] == "C"
    assert [t["id"] for r in rows for t in r] == [t["id"] for t in mixed]
    assert hop_rows([]) == []
    assert hop_rows([{"id": "only"}]) == [[{"id": "only"}]]


def test_topic_level_parses_real_convention_only() -> None:
    assert topic_level("alg_l1") == ("alg", 1)
    assert topic_level("alg_l12") == ("alg", 12)
    assert topic_level("alg_review") == (None, None)
    assert topic_level("t_vocab") == (None, None)
    assert topic_level("ext_l1_learn") == (None, None)  # node id, not a topic


def test_road_hopscotch_uses_real_levels_and_does_not_invent() -> None:
    titles = {
        "alg_l1": "רמה 1, בסיס", "alg_l2": "רמה 2, יישום",
        "alg_l3": "רמה 3, שליטה", "alg_review": "חזרה מעורבת",
    }
    types = {}
    spec = []
    for tid, n, start_type in (
        ("alg_l1", 5, "learn"), ("alg_l2", 5, "learn"),
        ("alg_l3", 3, "learn"), ("alg_review", 4, "practice"),
    ):
        bids = [f"{tid}_{i}" for i in range(n)]
        spec.append((tid, bids))
        for i, bid in enumerate(bids):
            if tid == "alg_review":
                types[bid] = "practice"
            elif i == 0:
                types[bid] = "learn"
            elif i == n - 1:
                types[bid] = "check"
            else:
                types[bid] = "practice"
    topics = _topics(spec, types=types, titles=titles)
    hop = road_hopscotch(
        topics, mastered={"alg_l1_0", "alg_l1_1"}, current_block="alg_l1_2",
        path_title="אלגברה", subject="math",
    )
    assert hop["hasLevels"] is True
    assert hop["stagesTotal"] == 1
    stage = hop["stages"][0]
    assert stage["id"] == "alg" and stage["title"] == "אלגברה" and stage["n"] == 1
    # One block: the current (lowest unfinished) level. No gateways.
    assert [b["kind"] for b in stage["blocks"]] == ["level"]
    assert stage["blocks"][0]["level"] == 1
    assert stage["blocks"][0]["gateway"] is None
    assert stage["currentLevel"] == 1
    assert hop["hereStage"] == 1 and hop["hereLevel"] == 1
    assert "מסע" not in (stage["title"] or "")
    # Done stones of the current level are "leveled", with a level badge, no check.
    done_tiles = [t for t in stage["blocks"][0]["tiles"] if t["state"] == "done"]
    assert done_tiles and all(t["leveled"] and t["badgeLevel"] == 1 for t in done_tiles)
    # Every visible stone has a short title and a mark (never blank).
    for t in stage["blocks"][0]["tiles"]:
        assert t["shortTitle"] and t["mark"] and t["fullTitle"]
        assert t["markKind"] in ("text", "book", "speech")

    # Finishing level 1 shows level 2 in place (not as the next stage).
    done = {f"alg_l1_{i}" for i in range(5)}
    opened = road_hopscotch(
        topics, mastered=done, current_block="alg_l2_0",
        path_title="אלגברה", subject="math",
    )
    assert opened["hereLevel"] == 2
    assert opened["stages"][0]["currentLevel"] == 2
    vis = opened["stages"][0]["blocks"]
    assert len(vis) == 1 and vis[0]["level"] == 2 and vis[0]["gateway"] is None
    assert all(t["id"].startswith("alg_l2_") for t in vis[0]["tiles"])
    assert vis[0]["tiles"][0]["badgeLevel"] == 2

    # A road with no _lN data: one level-1 block per topic, never a fake level 2.
    plain = _topics(
        [("vocab", ["v1", "v2", "v3"]), ("sent", ["s1"])],
        types={"v1": "learn", "v2": "practice", "v3": "practice", "s1": "learn"},
        titles={"vocab": "אוצר מילים", "sent": "השלמת משפטים"},
    )
    hop2 = road_hopscotch(plain, mastered=set(), current_block="v1", subject="english")
    assert hop2["hasLevels"] is False
    assert hop2["stagesTotal"] == 2
    assert all(b["level"] == 1 and b["kind"] == "level" for s in hop2["stages"] for b in s["blocks"])
    assert hop2["stages"][0]["boundary"]["toStage"] == 2
    assert hop2["stages"][0]["boundary"]["title"] == "השלמת משפטים"
    assert hop2["stages"][0]["title"] == "אוצר מילים"


def test_hopscotch_states_match_the_untouched_timeline() -> None:
    topics = _topics([("a", ["a1", "a2"]), ("b", ["b1", "b2"])])
    kwargs = dict(mastered={"a1"}, current_block="a2", linear=True)
    tl = road_timeline(topics, **kwargs)
    hop = road_hopscotch(topics, **kwargs)
    tl_states = [t["state"] for s in tl["stages"] for t in s["tiles"]]
    hop_states = [t["state"] for s in hop["stages"] for b in s["blocks"] for t in b["tiles"]]
    assert tl_states == hop_states
    assert hop["linear"] is True and hop["done"] == tl["done"]



def test_current_level_block_picks_lowest_unfinished() -> None:
    blocks = [
        {"kind": "level", "level": 1, "state": "done", "tiles": []},
        {"kind": "level", "level": 2, "state": "here", "tiles": []},
        {"kind": "level", "level": 3, "state": "ahead", "tiles": []},
        {"kind": "review", "level": None, "state": "ahead", "tiles": []},
    ]
    assert current_level_block(blocks)["level"] == 2
    blocks[1]["state"] = "done"
    assert current_level_block(blocks)["level"] == 3
    blocks[2]["state"] = "done"
    assert current_level_block(blocks)["kind"] == "review"
    blocks[3]["state"] = "done"
    assert current_level_block(blocks)["kind"] == "review"  # last, all done


def test_stone_mark_maps_real_titles_deterministically() -> None:
    def m(**kw):
        defaults = dict(subject="", topic_id="", topic_title="", session_id="", session_title="", session_type="")
        defaults.update(kw)
        return stone_mark(**defaults)

    assert m(subject="math", topic_id="alg_l1", session_id="alg_l1_learn",
             session_title="משוואה לינארית", session_type="learn") == ("x", "text")
    assert m(subject="math", session_title="משוואה ריבועית 1") == ("x²", "text")
    assert m(subject="math", session_title="הפרש ריבועים") == ("x²", "text")
    assert m(subject="math", session_title="חזקות") == ("xⁿ", "text")
    assert m(subject="math", session_title="מקדם לשוויון שורשים") == ("√", "text")
    assert m(subject="math", session_title="היקף מלבן") == ("□", "text")
    assert m(subject="math", session_title="חזרה, אי שוויון") == ("<", "text")
    assert m(subject="math", session_title="חיבור עם העברה") == ("+", "text")
    assert m(subject="math", session_title="לוח הכפל") == ("×", "text")
    assert m(subject="math", session_title="חילוק עם שארית") == ("÷", "text")
    assert m(subject="math", topic_title="הסתברות") == ("%", "text")
    assert m(subject="math", session_title="בלונים בפארק") == ("x", "text")  # subject default
    assert m(subject="english", topic_title="אוצר מילים אקדמי",
             session_title="מילים בהקשר, לא ברשימה") == ("Aa", "text")
    assert m(subject="english", topic_title="הבנת הנקרא", session_title="קטע קצר") == ("book", "book")
    assert m(subject="english", session_type="speak", session_title="אמרו תודה") == ("speech", "speech")
    assert m(subject="english", topic_title="אותיות", session_title="אותיות") == ("Aa", "text")
    assert m(subject="arabic", topic_title="שש אותיות ראשונות", session_title="איזו אות?") == ("ع", "text")
    # Fallback: first letters of the real title, never blank, never invented.
    mark, kind = m(subject="history", session_title="מלחמת העולם")
    assert mark == "מה" and kind == "text"
    empty, ekind = m()
    assert empty == "·" and ekind == "text"
    # Deterministic: same inputs, same output.
    a = m(subject="math", session_title="משוואה ריבועית 1")
    b = m(subject="math", session_title="משוואה ריבועית 1")
    assert a == b == ("x²", "text")


def test_short_title_truncates_cleanly_and_strips_level_prefix() -> None:
    assert short_title("משוואה לינארית") == "משוואה לינארית"
    assert short_title("רמה 1, בסיס") == "בסיס"
    long = short_title("ריבועיות, מערכות ואי שוויון")
    assert long and len(long) <= 18
    assert long[-1] not in " ,،:"
    assert "ואי שוויון" not in long or len("ריבועיות, מערכות ואי שוויון") <= 18
    assert title_initials("מלחמת העולם") == "מה"
    assert title_initials("") == "·"
    assert title_initials("רמה 2, יישום") == "יי" or title_initials("רמה 2, יישום")[0] == "י"


# --- rendered page -----------------------------------------------------------

def _leveled_doc() -> dict:
    topics, nodes = [], []
    for lvl, n_mid in ((1, 4), (2, 4), (3, 2)):
        ids = [f"alg_l{lvl}_learn"] + [f"alg_l{lvl}_p{i}" for i in range(n_mid)] + [f"alg_l{lvl}_check"]
        topics.append({
            "id": f"alg_l{lvl}",
            "titles": {"he": f"רמה {lvl}, בסיס", "en": f"Level {lvl}", "ar": f"المستوى {lvl}"},
            "node_ids": ids,
        })
        learn_titles = {1: "משוואה לינארית", 2: "ריבועיות, מערכות ואי שוויון", 3: "מילה, פרמטר ותחום"}
        practice_base = {1: "משוואה לינארית", 2: "משוואה ריבועית", 3: "תרגול"}
        nodes.append({"id": ids[0], "type": "learn", "title": learn_titles[lvl], "body_he": "הסבר"})
        mid = ids[1:-1]
        for i, pid in enumerate(mid, start=1):
            nodes.append({
                "id": pid, "type": "practice", "title": f"{practice_base[lvl]} {i}", "body_he": "כמה זה 2+2?",
                "choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "5"}], "correct": "a",
            })
        nodes.append({
            "id": ids[-1], "type": "practice", "title": f"בדיקה {lvl}", "body_he": "כמה זה 2+2?",
            "choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "5"}], "correct": "a",
        })
    topics.append({
        "id": "alg_review",
        "titles": {"he": "חזרה מעורבת", "en": "Mixed review", "ar": "مراجعة"},
        "node_ids": ["alg_r1", "alg_r2"],
    })
    nodes.append({"id": "alg_r1", "type": "practice", "kind": "review", "review_topic_ids": ["alg_l1"],
                  "title": "חזרה 1", "body_he": "כמה זה 2+2?",
                  "choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "5"}], "correct": "a"})
    nodes.append({"id": "alg_r2", "type": "practice", "kind": "review", "review_topic_ids": ["alg_l2"],
                  "title": "חזרה 2", "body_he": "כמה זה 2+2?",
                  "choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "5"}], "correct": "a"})
    return {
        "id": LEVELED, "subject": "math", "group_ids": ["adult"], "emoji": "∑",
        "estimated_minutes": 80,
        "titles": {"he": "אלגברה", "en": "Algebra", "ar": "الجبر"},
        "blurbs": {"he": "בדיקה.", "en": "Test.", "ar": "اختبار."},
        "topics": topics, "nodes": nodes,
    }


def _plain_doc() -> dict:
    return {
        "id": PLAIN, "subject": "english", "group_ids": ["adult"], "emoji": "E",
        "estimated_minutes": 20,
        "titles": {"he": "אוצר מילים", "en": "Vocab", "ar": "مفردات"},
        "blurbs": {"he": "קצר.", "en": "Short.", "ar": "قصير."},
        "topics": [
            {"id": "t_vocab", "titles": {"he": "מילים", "en": "Words"}, "node_ids": ["v1", "v2", "v3"]},
            {"id": "t_sent", "titles": {"he": "משפטים", "en": "Sentences"}, "node_ids": ["s1", "s2"]},
        ],
        "nodes": [
            {"id": "v1", "type": "learn", "title": "הסבר", "body_he": "הסבר"},
            {"id": "v2", "type": "practice", "title": "תרגול 1", "body_he": "כמה זה 2+2?",
             "choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "5"}], "correct": "a"},
            {"id": "v3", "type": "practice", "title": "תרגול 2", "body_he": "כמה זה 2+2?",
             "choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "5"}], "correct": "a"},
            {"id": "s1", "type": "learn", "title": "משפט", "body_he": "הסבר"},
            {"id": "s2", "type": "practice", "title": "תרגול", "body_he": "כמה זה 2+2?",
             "choices": [{"id": "a", "label": "4"}, {"id": "b", "label": "5"}], "correct": "a"},
        ],
    }


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content = tmp_path / "content" / "adult"
    content.mkdir(parents=True)
    for doc in (_leveled_doc(), _plain_doc()):
        (content / f"{doc['id']}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    store = PathStore(str(tmp_path / "hop.db"))
    application = create_learner_app(store=store, seed=False, seed_content=True)
    yield application
    store.close()


def _client(app, email: str = "hop@example.com") -> TestClient:
    c = TestClient(app)
    c.cookies.set("myroad_locale", "he")
    login_with_code(c, {"first_name": "Hop", "last_name": "User", "email": email, "next": "/"})
    c.cookies.set("myroad_locale", "he")
    return c


def test_journey_html_has_levels_rows_and_no_global_bar(app) -> None:
    c = _client(app)
    html = c.get(f"/play/{LEVELED}?view=map").text
    # Both styles are in the DOM; journey is the one we inspect.
    jy = html[html.index('data-road-style-panel="journey"'):]
    assert 'id="journey-track"' in jy
    assert 'class="jy-meter-overall"' not in jy  # no global top bar
    # One current-level block: שלב N · topic · רמה X. Level 2 is not a separate block.
    assert "אלגברה" in jy
    assert "שלב 1" in jy and "רמה 1" in jy
    assert "רמה 2" not in jy and "רמה 3" not in jy
    assert 'data-jy-levelup' not in jy
    assert 'data-jy-tier="1"' in jy
    assert 'data-jy-tier="2"' not in jy
    assert 'data-has-levels="1"' in jy
    assert 'data-jy-kind="review"' not in jy  # review waits until every level is done
    assert "מסע" not in jy
    # No check marks, no generic numbers. Every stone has a title and/or a mark.
    assert "jy-check" not in jy
    assert 'class="jy-num"' not in jy
    assert "משוואה לינארית" in jy
    assert 'class="jy-mark"' in jy and 'class="jy-short"' in jy
    assert 'class="jy-block-mark"' in jy
    assert jy.count('class="jy-identity"') >= 5
    assert 'data-jy-mark="' in jy
    # Recommended stone is marked once.
    assert jy.count('is-recommended') == 1 or jy.count('id="jy-here"') == 1
    # Rows exist and are marked with their stone count (1-3).
    counts = [int(x) for x in re.findall(r'data-jy-count="(\d+)"', jy)]
    assert counts and all(1 <= n <= 3 for n in counts)
    # Start forms are the same as the timeline (POST /play/.../start with node=).
    assert f'action="/play/{LEVELED}/start"' in jy
    assert 'name="node"' in jy
    # Timeline panel is still present and unchanged in structure.
    assert 'data-road-style-panel="timeline"' in html
    assert 'class="card road-tl' in html
    assert 'id="track"' in html


def test_plain_road_is_level_1_only_with_a_stage_boundary(app) -> None:
    c = _client(app, email="hop-plain@example.com")
    html = c.get(f"/play/{PLAIN}?view=map").text
    jy = html[html.index('data-road-style-panel="journey"'):]
    assert 'data-has-levels="0"' in jy
    assert "שלב 1" in jy and "רמה 1" in jy
    assert "שלב 2" in jy and "משפטים" in jy
    assert 'data-jy-boundary="2"' in jy
    assert 'data-jy-levelup=' not in jy  # no invented level-up
    assert "מסע" not in jy
    assert 'class="jy-mark"' in jy and 'class="jy-short"' in jy
    assert "תרגול" in jy or "הסבר" in jy or "מילים" in jy
    assert 'class="jy-block-mark"' in jy


def test_new_locale_keys_have_no_dashes_and_no_masa() -> None:
    for code in ("he", "en", "ar"):
        j = json.loads((_LOCALES / f"{code}.json").read_text(encoding="utf-8"))
        for k in ("jy_stage_level", "jy_level_n", "jy_levelup_aria", "jy_stage_start"):
            assert j[k] and "—" not in j[k] and "–" not in j[k]
            assert "מסע" not in j[k]


def test_css_keeps_fixed_stone_size_and_centered_rows() -> None:
    css = (_UI / "static" / "road-journey.css").read_text(encoding="utf-8")
    assert "--jy-stone-size:" in css
    assert "justify-content: center" in css
    assert ".road-jy .jy-row" in css
    # Horizontal rotation is gated at 1024px and honors the stored preference.
    assert "@media (min-width: 1024px)" in css
    assert 'html[data-road-orientation="horizontal"]' in css
    dark_at = css.index(':root[data-theme="dark"] .road-jy')
    assert "--jy-lawn:" in css[dark_at:dark_at + 900]
    assert "--jy-stone:" in css[dark_at:dark_at + 900]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_rows_are_centered_with_equal_stone_size(app) -> None:
    """Each row is centered on the vertical midline; stone size is nearly constant."""
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
                br = p.chromium.launch(
                    executable_path=chrome if Path(chrome).exists() else None,
                    args=["--no-sandbox"],
                )
            except Exception as exc:
                pytest.skip(f"no headless browser: {exc}")
            ctx = br.new_context(locale="he-IL", viewport={"width": 375, "height": 812})
            pg = ctx.new_page()
            pg.request.post(base + "/login", headers={"Origin": base}, form={
                "mode": "register", "first_name": "Noa", "last_name": "Levi",
                "email": "hop-layout@example.com", "next": "/",
            })
            assert codes, "no login code"
            pg.request.post(base + "/login/verify", headers={"Origin": base},
                            form={"code": codes[-1], "next": "/"})
            pg.goto(base + "/")
            pg.wait_for_load_state()
            pg.evaluate("() => localStorage.setItem('myroad.roadStyle','journey')")
            pg.goto(base + f"/play/{LEVELED}?view=map")
            pg.wait_for_load_state()
            pg.wait_for_selector(".road-jy.is-laid", timeout=5000)
            pg.wait_for_timeout(300)
            assert pg.locator(".road-jy").first.is_visible()
            assert pg.locator(".jy-meter-overall").count() == 0
            assert pg.locator("[data-jy-levelup]").count() == 0
            label = pg.locator(".jy-block-label").first.inner_text() or ""
            assert "שלב 1" in label and "אלגברה" in label and "רמה 1" in label
            # Every stone shows a title and/or a symbol; none are blank or a bare number.
            identities = pg.evaluate("""() => {
              return [...document.querySelectorAll('.jy-stone')].map(s => {
                const short = (s.querySelector('.jy-short')||{}).textContent || '';
                const mark = s.querySelector('.jy-mark');
                const markText = (mark||{}).textContent || '';
                const hasSvg = !!(mark && mark.querySelector('svg'));
                return {short: short.trim(), mark: markText.trim(), hasSvg, title: s.getAttribute('title') || ''};
              });
            }""")
            assert identities and all(
                (i["short"] or i["mark"] or i["hasSvg"]) and i["title"]
                for i in identities
            ), identities
            assert pg.locator(".jy-num").count() == 0
            assert pg.locator(".jy-block-mark").count() >= 1
            metrics = pg.evaluate("""() => {
              const field = document.querySelector('.jy-field');
              const fr = field.getBoundingClientRect();
              const mid = fr.left + fr.width / 2;
              const rows = [...document.querySelectorAll('.jy-row')];
              const sizes = [];
              const centers = [];
              for (const row of rows) {
                const els = [...row.querySelectorAll('.jy-stone')];
                if (!els.length) continue;
                const boxes = els.map(s => s.getBoundingClientRect());
                // Layout size (offsetWidth) is equal across stones; visual
                // getBoundingClientRect includes the recommended stone's scale.
                const widths = els.map(s => s.offsetWidth);
                const leftmost = Math.min(...boxes.map(s => s.left));
                const rightmost = Math.max(...boxes.map(s => s.right));
                centers.push((leftmost + rightmost) / 2);
                sizes.push(...widths);
              }
              const steps = [...document.querySelectorAll('.jy-step')];
              const first = steps[0].getBoundingClientRect();
              const last = steps[steps.length - 1].getBoundingClientRect();
              return {
                mid, centers, sizes,
                firstY: first.y, lastY: last.y,
                nRows: centers.length, nStones: sizes.length,
              };
            }""")
            assert metrics["nRows"] >= 3 and metrics["nStones"] >= 6
            # Every row is centered on the field's vertical midline (tolerance for
            # a side plaque or scrollbar: 12px).
            for c in metrics["centers"]:
                assert abs(c - metrics["mid"]) < 12, (c, metrics["mid"], metrics)
            # Stone size is nearly the same across rows (within 2px).
            assert max(metrics["sizes"]) - min(metrics["sizes"]) <= 2
            # A single-stone row is not giant: its stone matches a 3-stone row.
            assert min(metrics["sizes"]) >= 44
            # Bottom to top: the first stone (start) sits below the last.
            assert metrics["firstY"] > metrics["lastY"]
            # Labels stay inside the frame at 375.
            clip = pg.evaluate("""() => {
              const w = window.innerWidth;
              const labels = [...document.querySelectorAll('.jy-block-head, .jy-rule-tag, .jy-gate-label, .jy-here-flag')];
              return labels.map(el => {
                const r = el.getBoundingClientRect();
                return {t: (el.textContent||'').slice(0,40), left: r.left, right: r.right, w};
              });
            }""")
            for lab in clip:
                assert lab["left"] >= -1, lab
                assert lab["right"] <= lab["w"] + 1, lab
            br.close()
    finally:
        server.should_exit = True
        th.join(timeout=5)
