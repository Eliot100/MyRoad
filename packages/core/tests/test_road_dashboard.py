"""Road dashboard (arena c3): one view model + one template for every road shape.

road_view.road_dashboard is pure, so the shapes the content schema allows are tested directly:
no stages, one stage, many stages with long tile lists (AMIRNET 15 / 97), linear locks,
read-only, a finished road, and a resume tile that is already done.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2")

from myroad_core.ui.engagement_view import derive_engagement
from myroad_core.ui.i18n import content_lang, t
from myroad_core.ui.road_view import road_dashboard

_TPL = Path(__file__).resolve().parents[1] / "src" / "myroad_core" / "ui" / "templates"


def _road(sizes: list[int], review_every: int = 0) -> list[dict]:
    """Topics shaped like _topics_for_ui output: steps carry blockId, index and kind."""
    out, ix = [], 0
    for s, n in enumerate(sizes):
        steps = []
        for k in range(n):
            steps.append({"blockId": f"b{ix}", "index": ix, "title": f"משבצת {ix + 1}", "titleLang": "he",
                          "kind": "review" if review_every and (s + 1) % review_every == 0 else "understanding",
                          "type": "check" if k == n - 1 and n > 1 else "learn"})
            ix += 1
        out.append({"id": f"t{s}", "title": f"שלב {s + 1}", "titleLang": "he", "steps": steps,
                    "isReview": bool(review_every and (s + 1) % review_every == 0)})
    return out


def _ids(n: int) -> set[str]:
    return {f"b{i}" for i in range(n)}


def test_fresh_road_points_at_the_first_tile() -> None:
    r = road_dashboard(_road([3, 4]), set(), current_block="b0")
    assert r["next"]["blockId"] == "b0" and r["next"]["fresh"] and r["next"]["stageN"] == 1
    assert (r["done"], r["total"], r["stages_done"], r["stages_total"]) == (0, 7, 0, 2)
    assert [s["state"] for s in r["stages"]] == ["here", "open"]
    assert [s["expanded"] for s in r["stages"]] == [True, False]


def test_amirnet_shape_15_stages_97_tiles() -> None:
    sizes = [3, 8, 7, 7, 7, 7, 7, 7, 7, 6, 6, 8, 6, 9, 2]
    assert sum(sizes) == 97
    r = road_dashboard(_road(sizes, review_every=4), _ids(23), current_block="b23")
    assert r["total"] == 97 and r["done"] == 23 and r["stages_total"] == 15
    assert r["next"]["n"] == 24 and r["next"]["stageN"] == 4 and not r["next"]["fresh"]
    assert r["stages_done"] == 3 and r["here_stage"] == 4
    assert sum(1 for s in r["stages"] if s["expanded"]) == 1
    assert sum(1 for s in r["stages"] for st in s["steps"] if st["state"] == "here") == 1
    assert r["stages"][3]["review"] and r["stages"][3]["steps"][-1]["check"]


def test_resume_on_a_done_tile_moves_to_the_first_gap() -> None:
    r = road_dashboard(_road([2, 2]), {"b0", "b1"}, current_block="b1")
    assert r["next"]["blockId"] == "b2" and r["stages"][0]["state"] == "done"


def test_non_linear_road_keeps_a_skipped_tile_open_and_resumes_where_the_learner_is() -> None:
    r = road_dashboard(_road([2, 2]), {"b0", "b2"}, current_block="b3")
    assert r["next"]["blockId"] == "b3"
    assert r["stages"][0]["steps"][1]["state"] == "open" and r["stages"][0]["state"] == "started"


def test_linear_road_marks_tiles_past_the_gap_ahead_and_never_jumps_past_it() -> None:
    r = road_dashboard(_road([2, 3]), {"b0"}, current_block="b4", linear=True)
    assert r["next"]["blockId"] == "b1"
    assert [st["state"] for st in r["stages"][1]["steps"]] == ["ahead", "ahead", "ahead"]
    assert r["stages"][1]["state"] == "ahead" and r["linear"]


def test_read_only_road_has_no_here_marker() -> None:
    r = road_dashboard(_road([2, 2]), set(), current_block="b0", linear=True, read_only=True)
    assert r["here_stage"] is None and r["read_only"]
    assert all(st["state"] != "here" and st["state"] != "ahead" for s in r["stages"] for st in s["steps"])


def test_finished_road_has_no_next_tile() -> None:
    r = road_dashboard(_road([2, 1]), _ids(3), current_block="b2")
    assert r["finished"] and r["next"] is None and r["stages_done"] == 2 and r["first"] == "b0"


@pytest.mark.parametrize("topics", [None, [], [{"id": "x", "title": "ריק", "steps": []}]])
def test_empty_shapes_never_raise(topics) -> None:
    r = road_dashboard(topics, None)
    assert r["next"] is None and r["total"] == 0 and not r["finished"]


# --- template: the same macros render every shape -------------------------------------------

def _render(topics: list[dict], mastered: set[str], current: str | None, **kw) -> str:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(_TPL)), autoescape=True)
    env.filters["content_lang"] = content_lang
    tpl = env.from_string('{% from "_road_dashboard.html" import road_hero, stage_grid with context %}'
                          '{{ road_hero(road, eng, "p", "he") }}{{ stage_grid(road, "p", "he") }}')
    road = road_dashboard(topics, mastered, current_block=current, **kw)
    return tpl.render(road=road, eng=derive_engagement(topics, mastered), t=lambda k, **a: t("he", k, **a))


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


@pytest.mark.parametrize("sizes", [[1], [3, 4], [13, 13, 14, 14], [3, 8, 7, 7, 7, 7, 7, 7, 7, 6, 6, 8, 6, 9, 2]])
def test_every_shape_renders_one_primary_action_and_every_tile(sizes) -> None:
    topics = _road(sizes)
    html = _render(topics, _ids(min(2, sum(sizes) - 1)), "b2" if sum(sizes) > 2 else "b0")
    assert html.count('class="primary big continue-btn"') == 1
    assert html.count('<li class="stage-card ') == len(sizes)
    assert html.count('class="tile-item"') == sum(sizes)
    assert html.count('aria-current="step"') == 1 and html.count('id="here"') == 1
    assert "%" not in _text(html)  # counts in words, never a percent badge
    assert not re.search(r"[\u2013\u2014]", _text(html))


def test_hero_names_the_next_tile_its_stage_and_position() -> None:
    html = _render(_road([3, 4]), _ids(3), "b3")
    hero = html[:html.index("road-stages")]
    assert "המשבצת הבאה" in hero and "משבצת 4" in hero and "שלב <bdi>2</bdi>" in hero
    assert "משבצת <bdi>4</bdi> מתוך <bdi>7</bdi>" in hero and "המשך למשבצת הזאת" in hero
    assert 'name="node" value="b3"' in hero  # the button opens exactly the tile it names


def test_finished_and_read_only_heroes_have_no_primary_button() -> None:
    done = _render(_road([2]), _ids(2), "b1")
    assert "הדרך הושלמה" in done and 'class="primary' not in done and 'value="b0"' in done
    peek = _render(_road([2]), set(), "b0", read_only=True)
    assert 'class="primary' not in peek and "/start" not in peek and 'href="/p?topic=t0"' not in peek
    assert 'href="/play/p?view=learn"' in peek and 'href="/play/p?topic=t0"' in peek


def test_linear_ahead_tiles_are_not_buttons() -> None:
    html = _render(_road([2, 2]), {"b0"}, "b1", linear=True)
    assert html.count('class="tile-row is-ahead"') == 2 and html.count('aria-disabled="true"') == 2
    assert 'data-map="linear"' in html
