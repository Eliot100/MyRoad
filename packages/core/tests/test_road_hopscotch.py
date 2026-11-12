"""Hopscotch journey: row grouping, real levels, layout, no global bar."""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from pathlib import Path

import pytest

from myroad_core.ui.road_hopscotch import (
    MAX_ROW,
    chunk_rows,
    parse_topic,
    road_hopscotch,
    row_mates,
)
from myroad_core.ui.road_timeline import road_timeline

_CORE = Path(__file__).resolve().parents[1]
_UI = _CORE / "src" / "myroad_core" / "ui"


def _tiles(n: int, *, done: int = 0, here: int | None = None) -> list[dict]:
    out = []
    for i in range(n):
        if i < done:
            state = "done"
        elif here is not None and i == here:
            state = "here"
        else:
            state = "open"
        out.append({"id": f"t{i}", "title": f"s{i}", "titleLang": "he", "state": state,
                    "review": False, "check": i == n - 1 and n > 1})
    return out


def _stage(i: int, topic_id: str, title: str, n: int, **kw) -> dict:
    tiles = _tiles(n, **kw)
    done = sum(1 for t in tiles if t["state"] == "done")
    states = [t["state"] for t in tiles]
    if states and all(s == "done" for s in states):
        state = "done"
    elif "here" in states:
        state = "here"
    elif done:
        state = "started"
    else:
        state = "open"
    return {
        "n": i, "id": topic_id, "title": title, "titleLang": "he",
        "review": topic_id.endswith("_review") or topic_id.endswith("review"),
        "tiles": tiles, "done": done, "total": n, "pct": round(100 * done / n) if n else 0,
        "state": state, "walked": state == "done", "open": True,
    }


def test_chunk_rows_fills_threes_with_short_row_at_the_start():
    # Not a 1-2-3-2-1 diamond: a leftover 1 or 2 opens the block, then rows of 3.
    assert [len(r) for r in chunk_rows(_tiles(9))] == [3, 3, 3]
    assert [len(r) for r in chunk_rows(_tiles(16))] == [1, 3, 3, 3, 3, 3]
    assert [len(r) for r in chunk_rows(_tiles(6))] == [3, 3]
    assert [len(r) for r in chunk_rows(_tiles(1))] == [1]
    assert [len(r) for r in chunk_rows(_tiles(2))] == [2]
    assert [len(r) for r in chunk_rows(_tiles(4))] == [1, 3]
    assert [len(r) for r in chunk_rows(_tiles(5))] == [2, 3]
    assert [len(r) for r in chunk_rows([])] == []
    assert MAX_ROW == 3


def test_parse_topic_real_levels_only():
    assert parse_topic("alg_l1") == {"stem": "alg", "level": 1, "review": False, "real": True}
    assert parse_topic("alg_l2")["level"] == 2
    assert parse_topic("alg_review") == {"stem": "alg", "level": None, "review": True, "real": True}
    # Unleveled and look-alikes are not invented as levels.
    assert parse_topic("t_review_1")["real"] is False
    assert parse_topic("t_letters")["real"] is False
    assert parse_topic("t_numbers")["level"] is None


def test_algebra_shows_only_the_current_level_as_one_block():
    stages = [
        _stage(1, "alg_l1", "רמה 1, בסיס", 16, done=3, here=3),
        _stage(2, "alg_l2", "רמה 2, יישום", 16),
        _stage(3, "alg_l3", "רמה 3, שליטה", 16),
        _stage(4, "alg_review", "חזרה מעורבת", 6),
    ]
    tl = {"stages": stages, "stagesTotal": 4, "done": 3, "total": 54, "linear": True}
    hop = road_hopscotch(tl, path_title="אלגברה", path_title_lang="he")
    assert hop["hasRealLevels"] is True
    assert hop["stageCount"] == 1
    # Correction 2: one block for the whole stage, only the current (lowest unfinished) level.
    assert len(hop["blocks"]) == 1
    block = hop["blocks"][0]
    assert block["levelN"] == 1 and block["id"] == "alg_l1"
    assert block["kind"] == "level" and block["title"] == "אלגברה"
    assert block["total"] == 16 and block["done"] == 3
    assert block["boundary"] is None  # a later level is not a new stage
    assert all((b.get("boundary") or {}).get("kind") != "level-up" for b in hop["blocks"])
    assert [len(r) for r in block["rows"]] == [1, 3, 3, 3, 3, 3]
    assert block["ring"]["pct"] == block["pct"]
    # Done stones are leveled up with a level badge, no "finished-and-gone" check.
    leveled = [t for t in block["tiles"] if t["state"] == "done"]
    assert len(leveled) == 3
    assert all(t["leveled"] and t["levelBadge"] == 1 for t in leveled)
    recommended = [t for t in block["tiles"] if t["recommended"]]
    assert len(recommended) == 1 and recommended[0]["state"] == "here"


def test_algebra_advances_to_level_2_after_level_1_is_complete():
    stages = [
        _stage(1, "alg_l1", "רמה 1, בסיס", 16, done=16),
        _stage(2, "alg_l2", "רמה 2, יישום", 16, done=2, here=2),
        _stage(3, "alg_l3", "רמה 3, שליטה", 16),
        _stage(4, "alg_review", "חזרה מעורבת", 6),
    ]
    hop = road_hopscotch({"stages": stages, "stagesTotal": 4, "total": 54}, path_title="אלגברה")
    assert hop["stageCount"] == 1 and len(hop["blocks"]) == 1
    block = hop["blocks"][0]
    assert block["id"] == "alg_l2" and block["levelN"] == 2
    assert block["total"] == 16 and block["done"] == 2
    assert block["boundary"] is None
    assert all(t["levelBadge"] == 2 for t in block["tiles"] if t["leveled"])
    # The completed level 1 is not rendered as its own block or line.
    ids = [b["id"] for b in hop["blocks"]]
    assert "alg_l1" not in ids and "alg_l3" not in ids


def test_unleveled_path_is_level_1_blocks_with_stage_boundaries():
    stages = [
        _stage(1, "t_numbers", "מספרים", 4, done=4),
        _stage(2, "t_addsub", "חיבור", 5, done=1, here=1),
        _stage(3, "t_muldiv", "כפל", 3),
    ]
    hop = road_hopscotch({"stages": stages, "stagesTotal": 3, "total": 12}, path_title="מדרך")
    assert hop["hasRealLevels"] is False
    assert hop["stageCount"] == 3
    assert [b["stageN"] for b in hop["blocks"]] == [1, 2, 3]
    assert [b["levelN"] for b in hop["blocks"]] == [1, 1, 1]
    assert hop["blocks"][0]["title"] == "מספרים"  # topic name, not the path
    assert hop["blocks"][1]["boundary"]["kind"] == "stage"
    assert hop["blocks"][1]["boundary"]["title"] == "חיבור"
    assert hop["blocks"][1]["boundary"]["crossed"] is True
    assert hop["blocks"][2]["boundary"]["kind"] == "stage"
    assert hop["blocks"][2]["boundary"]["crossed"] is False


def test_road_hopscotch_uses_timeline_states_unchanged():
    topics = [
        {"id": "alg_l1", "title": "רמה 1", "titleLang": "he",
         "steps": [{"blockId": f"a{i}", "index": i, "title": f"s{i}", "titleLang": "he", "kind": "practice"}
                   for i in range(5)]},
        {"id": "alg_l2", "title": "רמה 2", "titleLang": "he",
         "steps": [{"blockId": f"b{i}", "index": 5 + i, "title": f"t{i}", "titleLang": "he", "kind": "practice"}
                   for i in range(5)]},
    ]
    tl = road_timeline(topics, mastered=["a0", "a1"], current_block="a2", linear=True)
    hop = road_hopscotch(tl, path_title="אלגברה")
    # Only the current level (l1, unfinished) is shown; l2 is not a second block.
    assert len(hop["blocks"]) == 1
    flat = [t["state"] for t in hop["blocks"][0]["tiles"]]
    assert flat[:3] == ["done", "done", "here"]
    assert all(s == "ahead" for s in flat[3:])
    assert hop["blocks"][0]["boundary"] is None
    assert hop["nextBlock"] is hop["blocks"][0] or hop["nextBlock"]["id"] == "alg_l1"
    assert hop["nextBlock"]["stageN"] == 1 and hop["nextBlock"]["levelN"] == 1
    # Timeline itself is untouched (still two stages, original titles).
    assert len(tl["stages"]) == 2
    assert tl["stages"][0]["title"] == "רמה 1"


def test_row_mates_for_any_order_documentation():
    tiles = _tiles(9)
    assert row_mates(tiles, "t0") == ["t0", "t1", "t2"]
    assert row_mates(tiles, "t1") == ["t0", "t1", "t2"]
    assert row_mates(tiles, "t3") == ["t3", "t4", "t5"]
    # Leftover of 1 or 2 opens the block as its own row.
    assert row_mates(_tiles(4), "t0") == ["t0"]
    assert row_mates(_tiles(4), "t3") == ["t1", "t2", "t3"]
    assert row_mates(_tiles(5), "t0") == ["t0", "t1"]
    assert row_mates(_tiles(5), "t3") == ["t2", "t3", "t4"]


def test_locale_keys_for_levels_in_all_three():
    for code in ("he", "en", "ar"):
        j = json.loads((_CORE / "locales" / f"{code}.json").read_text(encoding="utf-8"))
        for k in ("jy_stage_level", "jy_stage_review", "jy_level_up", "jy_stage_arrive",
                  "jy_stage_topic_level", "jy_stage_topic_review", "jy_level_badge", "jy_recommended"):
            assert j[k] and "—" not in j[k] and "–" not in j[k]
            assert "מסע" not in j[k]
        assert "{n}" in j["jy_stage_topic_level"] and "{level}" in j["jy_stage_topic_level"]
        assert "{topic}" in j["jy_stage_topic_level"]
        assert "{n}" in j["jy_level_badge"]
    he = json.loads((_CORE / "locales" / "he.json").read_text(encoding="utf-8"))
    assert "רמה" in he["jy_stage_topic_level"] and "רמה" in he["jy_level_badge"]
    assert "חזרה" in he["jy_stage_topic_review"]
    assert "מומלץ" in he["jy_recommended"]


def test_no_global_progress_bar_in_journey_template_or_css():
    html = (_UI / "templates" / "_road_journey.html").read_text(encoding="utf-8")
    css = (_UI / "static" / "road-journey.css").read_text(encoding="utf-8")
    assert "jy-meter-overall" not in html
    assert "jy-progress" not in html
    assert "jy-ring" in html and "jy-boundary" in html
    assert "road_hopscotch" in html
    assert "jy-badge" in html and "jy_recommended" in html
    assert "M5 13l4.5 4.5L19 7" not in html  # no check-mark on done stones
    assert "מסע" not in html
    assert ".jy-ring" in css and ".jy-badge" in css
    assert "jy-meter-overall" not in css
    assert "jy-recommend" in css
    assert "prefers-reduced-motion" in css
    assert 'data-jy-boundary="level-up"' not in html


@pytest.fixture
def app(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("jinja2")
    from fastapi.testclient import TestClient  # noqa: F401  (imported for side-effect readiness)
    from myroad_core.store import PathStore
    from myroad_core.ui.app import create_learner_app
    store = PathStore(str(tmp_path / "hop.db"))
    yield create_learner_app(store=store, seed=True, seed_content=True)
    store.close()


def test_journey_html_has_rows_rings_and_no_top_bar(app):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from auth_helpers import login
    with TestClient(app) as c:
        login(c, "hop-html@example.com", first_name="T", last_name="H")
        roads = c.get("/roads").text
        # Prefer a math5 path with real levels when the content pack has it.
        m = re.search(r'href="(/play/path_math_bagrut5_01_algebra[^"]*)"', roads) or \
            re.search(r'href="(/play/[^"]+)"', roads)
        assert m, "no road"
        href = m.group(1)
        if "view=map" not in href:
            href = href.split("?")[0] + "?view=map"
        html = c.get(href).text
        assert 'id="journey-track"' in html
        assert "jy-meter-overall" not in html
        assert 'class="jy-row"' in html or "jy-row" in html
        assert "jy-ring" in html
        assert "מסע" not in html
        # Level labels appear on a real-level path; level-1 labels on others.
        assert "רמה" in html or "שלב" in html
        if "path_math_bagrut5_01_algebra" in href:
            # Fresh learner: only level 1 of the one stage, no level-up line.
            assert 'data-jy-boundary="level-up"' not in html
            assert html.count('class="jy-block') >= 1
            assert 'data-jy-level="1"' in html
            assert 'data-jy-level="2"' not in html
            assert "אלגברה" in html and "רמה 1" in html
            assert 'data-jy-span="3"' in html
            # No check-mark icon on done stones (none are done yet, but the
            # template must not draw a check for the done state).
            assert "M5 13l4.5 4.5L19 7" not in html


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_hopscotch_layout_375_and_horizontal(app):
    """Centered 1-2-3 rows, bottom-to-top, horizontal is a 90° rotation."""
    sync_api = pytest.importorskip("playwright.sync_api")
    uvicorn = pytest.importorskip("uvicorn")
    from auth_helpers import login  # noqa: F401
    from fastapi.testclient import TestClient
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
                "email": "hop-pw@example.com", "next": "/"})
            assert codes, "no login code"
            pg.request.post(base + "/login/verify", headers={"Origin": base},
                            form={"code": codes[-1], "next": "/"})
            pg.goto(base + "/roads")
            # Prefer algebra so we can assert a row of 3 and a level-up line.
            href = pg.evaluate("""() => {
              const a = [...document.querySelectorAll('a[href^="/play/"]')];
              const alg = a.find(x => x.getAttribute('href').includes('path_math_bagrut5_01_algebra'));
              return (alg || a[0]).getAttribute('href');
            }""")
            assert href
            play = href if "view=map" in href else (href.split("?")[0] + "?view=map")
            pg.evaluate("localStorage.setItem('myroad.roadStyle','journey')")
            pg.goto(base + play)
            pg.wait_for_load_state()
            pg.wait_for_timeout(400)
            assert pg.locator(".road-jy").count() == 1
            assert pg.locator(".jy-meter-overall").count() == 0
            assert pg.locator(".jy-ring").count() >= 1
            geo = pg.evaluate("""() => {
              const steps = [...document.querySelectorAll('.jy-step')];
              if (steps.length < 2) return null;
              const first = steps[0].getBoundingClientRect();
              const last = steps[steps.length - 1].getBoundingClientRect();
              const field = document.querySelector('.jy-field').getBoundingClientRect();
              const mid = field.left + field.width / 2;
              const rows = [...document.querySelectorAll('.jy-row')];
              const spans = rows.map(r => Number(r.getAttribute('data-jy-span')));
              const sizes = steps.map(s => {
                const r = s.getBoundingClientRect();
                return { w: r.width, h: r.height };
              });
              const rowGeom = rows.map(row => {
                const stones = [...row.querySelectorAll('.jy-step')].map(s => s.getBoundingClientRect());
                if (!stones.length) return null;
                const left = Math.min(...stones.map(s => s.left));
                const right = Math.max(...stones.map(s => s.right));
                const gaps = [];
                const ordered = [...stones].sort((a, b) => a.left - b.left);
                for (let i = 1; i < ordered.length; i++) gaps.push(ordered[i].left - ordered[i-1].right);
                return {
                  n: stones.length,
                  aligned: Math.max(...stones.map(s => s.top)) - Math.min(...stones.map(s => s.top)) < 8,
                  centerOff: Math.abs((left + right) / 2 - mid),
                  widths: stones.map(s => s.width),
                  heights: stones.map(s => s.height),
                  gaps,
                  gapSpread: gaps.length ? Math.max(...gaps) - Math.min(...gaps) : 0,
                };
              }).filter(Boolean);
              const here = document.querySelector('.jy-step.is-here, #jy-here');
              const ws = sizes.map(s => s.w), hs = sizes.map(s => s.h);
              return {
                firstY: first.y, lastY: last.y, n: steps.length, spans,
                rowGeom,
                sizeSpread: Math.max(Math.max(...ws) - Math.min(...ws), Math.max(...hs) - Math.min(...hs)),
                meanW: ws.reduce((a,b)=>a+b,0)/ws.length,
                hasBoundary: !!document.querySelector('.jy-boundary'),
                hereOnScreen: here ? (here.getBoundingClientRect().bottom > 0 &&
                                      here.getBoundingClientRect().top < window.innerHeight) : null,
                minStone: Math.min(...ws, ...hs),
              };
            }""")
            assert geo and geo["n"] >= 2
            # Bottom to top: first stone is lower on the screen than the last.
            assert geo["firstY"] > geo["lastY"]
            assert geo["minStone"] >= 44
            # Fixed stone size across every row (a lone stone is not giant, a
            # 3-stone row is not tiny). A few px of sub-pixel variance is fine.
            assert geo["sizeSpread"] < 6, geo["sizeSpread"]
            for rg in geo["rowGeom"]:
                assert rg["aligned"] is True
                # Each row is centered on the vertical midline of the field.
                assert rg["centerOff"] < 16, rg
                if rg["n"] > 1:
                    assert rg["gapSpread"] < 4, rg["gaps"]
                # Stones in a row are the same size.
                assert max(rg["widths"]) - min(rg["widths"]) < 3
                assert max(rg["heights"]) - min(rg["heights"]) < 3
            if "algebra" in play:
                # One stage, current level only: no level-up line between levels.
                assert pg.locator('[data-jy-boundary="level-up"]').count() == 0
                assert "רמה" in pg.locator(".jy-kicker").first.inner_text()
            # Reduced motion: the recommended stone keeps a static lift, no pulse.
            # Horizontal on a wide screen: first stone is to the right (RTL).
            pg.set_viewport_size({"width": 1280, "height": 800})
            pg.evaluate("localStorage.setItem('myroad.roadOrientation','horizontal'); document.documentElement.setAttribute('data-road-orientation','horizontal')")
            pg.reload()
            pg.wait_for_load_state()
            pg.wait_for_timeout(400)
            assert pg.locator(".road-jy.is-horizontal").count() == 1
            boxes = pg.evaluate("""() => {
              const steps = [...document.querySelectorAll('.jy-step')];
              if (steps.length < 2) return null;
              const a = steps[0].getBoundingClientRect();
              const b = steps[steps.length - 1].getBoundingClientRect();
              const here = document.querySelector('.jy-step.is-here, #jy-here');
              const field = document.querySelector('.jy-field');
              const fr = field.getBoundingClientRect();
              const hr = here ? here.getBoundingClientRect() : null;
              const three = document.querySelector('.jy-row[data-jy-span="3"]');
              let col = null;
              if (three) {
                const ss = [...three.querySelectorAll('.jy-step')].map(s => s.getBoundingClientRect());
                col = {
                  stacked: Math.max(...ss.map(s => s.left)) - Math.min(...ss.map(s => s.left)) < 12,
                  firstLower: ss[0].y > ss[ss.length - 1].y - 2,
                };
              }
              return {
                firstX: a.x, lastX: b.x,
                hereInView: hr ? (hr.right > fr.left + 2 && hr.left < fr.right - 2) : null,
                col,
              };
            }""")
            assert boxes["firstX"] >= boxes["lastX"] - 2
            # A locked or finished road has no "here" stone; when one exists it stays in view.
            if boxes["hereInView"] is not None:
                assert boxes["hereInView"] is True
            if boxes["col"]:
                assert boxes["col"]["stacked"] is True
                assert boxes["col"]["firstLower"] is True
            br.close()
    finally:
        server.should_exit = True
        th.join(timeout=5)
