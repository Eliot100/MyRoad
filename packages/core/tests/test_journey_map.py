"""Road screen journey map (arena c2): one template for every road shape.

Pure view model checks (few/many stations, a 97 משבצות road, finished, read-only, linear
gap) plus the rendered page: one station and one road segment per שלב, the mini map of the
whole road, the end milestone, the named next step, and RTL-safe, calm CSS.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from test_adult_learner_flow import LONG, N_TOPICS, _client, adult_app  # noqa: F401

from myroad_core.ui.journey_view import LANES, journey_view, lane_x

_CORE = Path(__file__).resolve().parents[1]
_STATIC = _CORE / "src" / "myroad_core" / "ui" / "static"
_TPL = _CORE / "src" / "myroad_core" / "ui" / "templates"


def _topics(sizes: list[int], done: int = 0, review_every: int = 0) -> list[dict]:
    """Topics shaped like the map route's: steps with index/done/current, counts per topic."""
    out, ix = [], 0
    cur_ix = done  # the first unmastered step is the current one
    for t, n in enumerate(sizes):
        steps = []
        for _ in range(n):
            steps.append({"blockId": f"b{ix}", "index": ix, "title": f"משבצת {ix}", "titleLang": "he",
                          "kind": "review" if review_every and (t + 1) % review_every == 0 else "understanding",
                          "done": ix < done, "current": ix == cur_ix})
            ix += 1
        d = sum(1 for s in steps if s["done"])
        out.append({"id": f"t{t}", "title": f"שלב {t}", "titleLang": "he", "steps": steps, "stepCount": n,
                    "doneCount": d, "complete": n > 0 and d == n, "current": any(s["current"] for s in steps),
                    "isReview": bool(review_every) and (t + 1) % review_every == 0})
    return out


def test_long_road_like_amirnet_counts_and_finds_the_next_step() -> None:
    sizes = [3] + [7] * 13 + [3]  # 15 stations, 97 steps, the AMIRNET road shape
    assert sum(sizes) == 97
    jv = journey_view(_topics(sizes, done=31, review_every=4))
    assert jv["stages_total"] == 15 and jv["cells_total"] == 97 and jv["cells_done"] == 31
    assert jv["here_n"] == 6 and jv["stages_done"] == 5 and not jv["finished"]
    assert jv["next"]["blockId"] == "b31" and jv["next"]["stageN"] == 6
    states = [s["state"] for s in jv["stations"]]
    assert states[:5] == ["done"] * 5 and states[5] == "here" and set(states[6:]) == {"open"}
    assert [s["review"] for s in jv["stations"]][3] is True
    # Only the road behind the learner is drawn as travelled.
    assert [s["travelled"] for s in jv["stations"]] == [True] * 5 + [False] * 10


def test_lanes_wind_without_jumping_and_connect() -> None:
    xs = [lane_x(i) for i in range(12)]
    assert set(xs) <= set(LANES)
    assert all(abs(LANES.index(a) - LANES.index(b)) == 1 for a, b in zip(xs, xs[1:]))
    jv = journey_view(_topics([2, 2, 2]))
    st = jv["stations"]
    assert [s["nextX"] for s in st[:-1]] == [s["x"] for s in st[1:]]


def test_empty_single_and_finished_roads() -> None:
    empty = journey_view([])
    assert empty["stations"] == [] and empty["cells_total"] == 0 and not empty["finished"] and empty["next"] is None
    one = journey_view(_topics([1]))
    assert one["stages_total"] == 1 and one["here_n"] == 1 and one["next"]["blockId"] == "b0"
    done = journey_view(_topics([2, 3], done=5))
    assert done["finished"] and done["next"] is None and done["here_n"] == 0


def test_read_only_has_no_here_and_linear_locks_past_the_gap() -> None:
    ro = journey_view(_topics([2, 2], done=1), read_only=True)
    assert ro["here_n"] == 0 and all(s["state"] != "here" for s in ro["stations"])
    assert all(st["state"] != "here" for s in ro["stations"] for st in s["steps"])
    lin = journey_view(_topics([2, 2, 2], done=2), linear=True, gap=2)
    assert [s["state"] for s in lin["stations"]] == ["done", "here", "lock"]
    assert [st["state"] for st in lin["stations"][1]["steps"]] == ["here", "lock"]


def test_page_draws_one_station_and_segment_per_stage_and_the_end(adult_app) -> None:  # noqa: F811
    app, _store = adult_app
    html = _client(app).get(f"/play/{LONG}").text
    journey = html[html.index('<ol class="journey"'):html.rindex('class="jr-end')]
    assert journey.count('<li class="station ') == N_TOPICS
    assert journey.count('<svg class="jr-seg') == N_TOPICS
    assert "End of the road" in html[html.rindex('class="jr-end'):]
    bar = html[html.index('<ol class="jr-ov-bar"'):html.index("</ol>", html.index('<ol class="jr-ov-bar"'))]
    assert bar.count("<li class=\"is-") == N_TOPICS and 'aria-hidden="true"' in html[html.index('<ol class="jr-ov-bar"') - 5:][:60]
    assert html.count('aria-current="step"') == 1 and html.count('id="here"') == 1
    assert "/static/journey.css" in html and "worldmap.js" not in html


def test_one_primary_action_names_the_next_step(adult_app) -> None:  # noqa: F811
    app, _store = adult_app
    c = _client(app)
    c.post(f"/play/{LONG}/start")
    c.post(f"/play/{LONG}/ack")
    html = c.get(f"/play/{LONG}?view=map").text
    card = html[html.index('<section class="card map-card">'):html.index("</section>", html.index('<section class="card map-card">'))]
    assert card.count('class="primary') == 1
    action = card[card.index('class="row map-actions"'):]
    assert "jr-next-title" in action and "Continue the track" in action


def test_journey_css_is_logical_calm_and_reduced_motion_safe() -> None:
    css = (_STATIC / "journey.css").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert not re.search(r"(margin|padding|border)-(left|right)\b|(?<![-\w])(left|right)\s*:", code)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", code), "colors come from theme tokens"
    assert "@container journey (max-width: 26rem)" in code and "@container journey (min-width: 40rem)" in code
    assert '[dir="rtl"] .jr-seg { transform: scaleX(-1); }' in code
    assert "prefers-reduced-motion: no-preference" in code and "min-block-size: 44px" in code
    assert "position: sticky" in code  # the mini map stays in view on long roads


def test_journey_has_no_game_mechanics_and_copy_is_dashless() -> None:
    tpl = (_TPL / "_journey.html").read_text(encoding="utf-8").lower()
    for word in ("streak", "leaderboard", "achievement", "points", "badge-gold", "confetti"):
        assert word not in tpl, word
    for loc in ("he", "ar", "en"):
        d = json.loads((_CORE / "locales" / f"{loc}.json").read_text(encoding="utf-8"))
        for k, v in d.items():
            if k.startswith(("journey_", "world_")):
                assert "—" not in v and "–" not in v and " - " not in v, (loc, k)
    he = json.loads((_CORE / "locales" / "he.json").read_text(encoding="utf-8"))
    assert he["world_here"] == "כאן עכשיו" and "אתה" not in he["world_here"]
    assert he["station_of"].startswith("שלב") and he["progress_label"].startswith("משבצת")
    assert "נושא" not in he["journey_enter"] and he["journey_enter"].endswith("שלב")
